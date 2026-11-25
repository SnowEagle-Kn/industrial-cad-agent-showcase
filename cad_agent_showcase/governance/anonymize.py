# -*- coding: utf-8 -*-
"""送评包去标识（F02 整改）。

只做字段剔除，不证明会话隔离或文件权限隔离。

F02 缺陷：旧版 `_strip` 对每一层都用同一个顶层 WHITELIST，把
`quality/Q1`、`parameters/0/value`、`mechanism_signature/basis` 一起删掉，
正式模板的 11 项 quality 变成 11 个空对象，却仍返回 REDACTED。

整改要点：
1. 顶层白名单只约束**顶层**键；工程子结构与数组元素按各自 schema 保留。
2. 只删除明确的**身份路径**。
3. 遇不识别的工程结构 → 报错，不静默清空。
4. 脱敏后比较全部剩余字段（含顶层业务字段、容器与类型）；不通过即拒绝。
"""

import argparse
import copy
import json
import re

from .envelope import InputError, load_json

SCHEMA_VERSION = "wishcad.anonymize.v1.2"
LEGACY_SCHEMA_VERSION = "wishcad.anonymize.v1.1"

# 明确的身份路径：从“任意层级按键名删”改为**路径**判定（独立审查 P2-01）。
# `role`、`designer` 等在合同里同时是参数用途词与结构签名语境词，
# 按键名全局删会误删工程量。
#
# 规则：
#   * 顶层 `author_session` 置 null（合同要求字段存在且为 null）；
#   * 顶层其他身份键删除；
#   * 深层只删**明确属于身份**的键名（会话/身份专用词），
#     不含 `role`/`designer` 这类会与工程语义冲突的通用词；
#   * `role` 只在顶层且取值像席位标签（D0–D4/P/J0）时才删。
IDENTITY_FIELDS = {
    "author_session", "session_id", "parent_session", "started_by", "startedBy",
    "d_seat", "author_name", "chat_ref", "parent_preference",
    "source_executor_ref", "private_identity_map", "author_chat_ref",
    # 会话/身份专用词，深层出现也是身份（P2-01 改按路径后仍需覆盖）
    "designer_session", "design_session", "seat_id", "seat_label",
    "author_id", "author_ref", "author_chat", "window_id", "session_ref",
    "private_map_ref", "identity_map", "identity_map_ref",
}
# 只在顶层身份、深层可能承载工程语义的通用词。
# `role`（§5.1 参数用途 interface/envelope/free_design/process；§6.3 结构签名
# 语境）、`designer`、`source_executor`（合同对象自带字段，不是个人身份）。
TOP_LEVEL_ONLY_IDENTITY = {"role", "designer", "author", "session"}
QUALITY_IDENTITY_KEYS = {"author", "session"}
# 只有这些带席位含义的键才会把 D0-D4/P/J0 值视为身份；工程文本、
# parameter_id、symbol、required 等字段中的同样字符串一律保留。
SEAT_IDENTITY_KEYS = {"owner", "reviewer", "created_by", "updated_by",
                      "by", "seat", "author", "session", "role"}
# `role` 在顶层只有像席位标签时才当身份。
SEAT_LABEL_RE = re.compile(r"^(D[0-4]|P|J0|D席|设计席\d*|裁判)$")

# 只在顶层生效：顶层键若不在白名单且不是身份字段，视为未知结构。
TOP_LEVEL_WHITELIST = (
    "schema", "version", "run_id", "author_session", "source_executor", "scope",
    "template_state", "candidate_id", "anonymous_id", "brief_version",
    "brief_sha256", "rubric_sha256", "mode", "endpoint",
    "quality", "parameters", "mechanism_signature", "scenario_analysis",
    "failure_modes", "first_draft_receipt", "critique_received_ref", "replies",
    "revision_parent_sha256", "freeze", "release_authority_ref",
    "uses_recorded_decisions_from", "text", "evidence_refs",
    "design_answer_in_public_packet", "redacted_for_judge",
)

# 工程子结构：按 schema 保留，不做白名单裁剪。
ENGINEERING_KEYS = (
    "quality", "parameters", "mechanism_signature", "scenario_analysis",
    "failure_modes", "evidence_refs", "replies",
)

MECHANISM_DIMENSIONS = ("basis", "topology", "load_path", "adjust_lock",
                        "maintenance", "unknown_handling")
QUALITY_IDS = tuple("Q%d" % index for index in range(1, 12))

# 工程子树里必须保留的字段（用于脱敏后证据完整性校验）。
REQUIRED_PARAMETER_FIELDS = ("parameter_id", "value", "unit", "evidence_status",
                             "source_ref")


class RedactionError(Exception):
    """剔除后仍有身份字段。"""


def _is_identity_key(key, value, path):
    """Return true only for identity fields at an identity-bearing path.

    Seat labels are data by themselves. A value such as D1/P is removed only
    when it is the top-level role marker; it is preserved in parameter IDs,
    symbols, quality prose and mechanism evidence. Quality author/session
    fields are identity paths by contract.
    """
    if key in IDENTITY_FIELDS:
        return True
    if key in QUALITY_IDENTITY_KEYS and path and path[0] == "quality":
        return True
    if isinstance(value, str) and key in SEAT_IDENTITY_KEYS and \
            SEAT_LABEL_RE.fullmatch(value.strip()) is not None:
        return True
    if not path and key == "role":
        return isinstance(value, str) and SEAT_LABEL_RE.fullmatch(value.strip()) is not None
    if not path and key in {"designer", "author", "session"}:
        return True
    return False

def _path_text(path):
    """JSON Pointer 转义路径分量，避免键中的 / 或 ~ 与层级路径混同。"""
    return "/".join(str(part).replace("~", "~0").replace("/", "~1")
                    for part in path)


def _strip_identity(node, removed, path):
    """递归删除**身份路径**；其余原样保留（不套顶层白名单）。

    只按 `_is_identity_key` 判定，不按键名一刀切：工程子树里的
    `"role": "interface"`、`"role": "主承力路径"` 必须保留（独立审查 P2-01）。
    """
    if isinstance(node, dict):
        kept = {}
        for key, value in node.items():
            here = _path_text(path + [key])
            if _is_identity_key(key, value, path):
                removed.append(here)
                continue
            kept[key] = _strip_identity(value, removed, path + [key])
        return kept
    if isinstance(node, list):
        return [_strip_identity(item, removed, path + [str(index)])
                for index, item in enumerate(node)]
    return node


def _check_top_level(candidate):
    """顶层未知键 → 报错，不静默清空。

    顶层既有身份键（含 `role`/`designer` 这类只在顶层算身份的通用词）
    也有工程键；先排除身份类，再看是否还有真正未声明的结构键。
    """
    unknown = [key for key in candidate
               if key not in TOP_LEVEL_WHITELIST
               and key not in IDENTITY_FIELDS
               and key not in TOP_LEVEL_ONLY_IDENTITY]
    if unknown:
        raise RedactionError(
            "顶层含未识别的工程结构键 %s；请先在 schema 中声明，"
            "本模块不做静默剔除" % ",".join(sorted(unknown)))


def _check_engineering_structure(candidate):
    """工程子树结构自检：形状不对就报错，不静默丢字段。

    quality 允许两种写法：正式模板的数组（每项必须带 id），以及早期
    内部用例的 {Q1: 正文} 映射。两种都原样保留，不做白名单裁剪。
    """
    quality = candidate.get("quality")
    if quality is not None:
        if isinstance(quality, dict):
            for key in quality:
                if not str(key).startswith("Q"):
                    raise RedactionError("quality 映射键 %r 不是 Q 项" % (key,))
        elif isinstance(quality, list):
            for index, item in enumerate(quality):
                if not isinstance(item, dict):
                    raise RedactionError("quality[%d] 必须是对象" % index)
                if "id" not in item:
                    raise RedactionError("quality[%d] 缺少 id" % index)
        else:
            raise RedactionError("quality 必须是数组或 Q 项映射")
    parameters = candidate.get("parameters")
    if parameters is not None:
        if not isinstance(parameters, list):
            raise RedactionError("parameters 必须是数组")
        for index, item in enumerate(parameters):
            if not isinstance(item, dict):
                raise RedactionError("parameters[%d] 必须是对象" % index)
            if not item:
                # 空参数对象是“静默清空”的形状；不能原样进送评包。
                raise RedactionError(
                    "parameters[%d] 是空对象；参数必须带 parameter_id 等字段，"
                    "不接受空壳" % index)
            if "parameter_id" not in item and "id" not in item:
                raise RedactionError(
                    "parameters[%d] 缺少 parameter_id" % index)
    signature = candidate.get("mechanism_signature")
    if signature is not None and not isinstance(signature, dict):
        raise RedactionError("mechanism_signature 必须是对象")
    failure_modes = candidate.get("failure_modes")
    if failure_modes is not None and not isinstance(failure_modes, list):
        raise RedactionError("failure_modes 必须是数组")


def _residual_identity(node):
    found = []

    def walk(current, path):
        if isinstance(current, dict):
            for key, value in current.items():
                if _is_identity_key(key, value, path) and value not in (None, ""):
                    found.append("/".join(path + [key]))
                walk(value, path + [key])
        elif isinstance(current, list):
            for index, value in enumerate(current):
                walk(value, path + [str(index)])

    walk(node, [])
    return found

def _collect_removed(original):
    """独立实现：只收集“按规则应当删”的路径集合，不构造期望值。

    与 `_strip_identity` 分开写，避免“自己删的东西自己认为应当删”的自证循环
    （独立审查 P2-01）。这里不调用 `_strip_identity`，只回答“哪些路径是身份”。
    """
    removed = []

    def walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                here = path + [key]
                if _is_identity_key(key, value, path):
                    removed.append(_path_text(here))
                    continue
                walk(value, here)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path + [str(index)])

    walk(original, [])
    return removed


def _drop_paths(node, paths):
    """按转义后的精确路径删除，用于独立构造完整性基线。"""
    def walk(current, prefix):
        if isinstance(current, dict):
            out = {}
            for key, value in current.items():
                here = prefix + [key]
                if _path_text(here) in paths:
                    continue
                out[key] = walk(value, here)
            return out
        if isinstance(current, list):
            return [walk(item, prefix + [str(index)])
                    for index, item in enumerate(current)]
        return current

    return walk(node, [])


def _same_json(left, right):
    """比较完整 JSON 结构；不让 True == 1 或空容器差异蒙混过关。"""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return (left.keys() == right.keys()
                and all(_same_json(value, right[key])
                        for key, value in left.items()))
    if isinstance(left, list):
        return (len(left) == len(right)
                and all(_same_json(a, b) for a, b in zip(left, right)))
    return left == right


def _evidence_integrity(original, packet):
    """仅排除合法身份路径，再比较全部剩余字段，含顶层业务信息。

    基线由 _collect_removed + _drop_paths 独立构造，绝不调用
    _strip_identity。仅 author_session=null、redacted_for_judge=true
    两个确切的根路径允许规范化；同名深层字段没有豁免。
    """
    checks = []
    identity_paths = set(_collect_removed(original))
    expected = _drop_paths(original, identity_paths)
    expected["author_session"] = None
    expected["redacted_for_judge"] = True

    def add(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    for key, value in expected.items():
        same = key in packet and _same_json(packet[key], value)
        add("kept:%s" % key, same,
            "除身份路径及两个根标记外逐字段保持" if same
            else "字段缺失、内容、类型或容器结构超出合法变更范围")
    add("all_fields_preserved", _same_json(expected, packet),
        "完整对象比较（字段、值、类型、数组顺序与空容器）")

    # 所有节点都计入路径集，空对象/数组也不可静默新增。
    def flat(node, prefix, out):
        out.add(_path_text(prefix))
        if isinstance(node, dict):
            for key, value in node.items():
                flat(value, prefix + [key], out)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                flat(value, prefix + [str(index)], out)

    expected_paths = set()
    packet_paths = set()
    flat(expected, [], expected_paths)
    flat(packet, [], packet_paths)
    extra = sorted(packet_paths - expected_paths)
    add("no_unexpected_paths", not extra,
        "多出未声明路径 %s" % extra[:5] if extra else "无多出路径")

    quality = packet.get("quality") or []
    if isinstance(quality, dict):
        ids = sorted(quality)
        non_empty = all(bool(value) for value in quality.values())
    else:
        ids = [item.get("id") for item in quality if isinstance(item, dict)]
        non_empty = all(item for item in quality if isinstance(item, dict))
    if "quality" in original:
        add("quality_not_emptied", non_empty,
            "quality 项均非空" if non_empty else "出现空对象或空项")
        if isinstance(original["quality"], dict):
            add("quality_keys", ids == sorted(original["quality"]),
                "Q 项键 %s" % (ids,))
        else:
            add("quality_ids",
                ids == [item.get("id") for item in original["quality"]],
                "Q 项 id 序列 %s" % (ids,))

    params = packet.get("parameters") or []
    if "parameters" in original:
        kept_fields = True
        empty_items = []
        for index, item in enumerate(expected.get("parameters") or []):
            if not isinstance(item, dict):
                continue
            if not item:
                # 原稿就是空对象：这正是 F02 要拦的“静默清空”形态。
                empty_items.append(index)
                continue
            mirrored = params[index] if index < len(params) else {}
            for field in REQUIRED_PARAMETER_FIELDS:
                if field in item and field not in mirrored:
                    kept_fields = False
        add("parameters_not_emptied", not empty_items,
            "空参数对象 %s" % empty_items if empty_items else "无空参数对象")
        add("parameters_fields", kept_fields, "value/unit/evidence_status/source_ref 保留")

    signature = packet.get("mechanism_signature")
    if isinstance(original.get("mechanism_signature"), dict):
        # 只校验“原稿有的维度都保留”。原稿本身缺维是候选质量问题，
        # 由差异检查/裁判判，不由匿名化原地补全或拒绝。
        declared = [name for name in MECHANISM_DIMENSIONS
                    if name in original["mechanism_signature"]]
        missing = [name for name in declared if name not in (signature or {})]
        add("mechanism_dimensions_kept", not missing,
            "缺失原有维度 %s" % missing if missing
            else "原有 %d 维全部保留" % len(declared))

    if "failure_modes" in original:
        add("failure_modes_kept",
            packet.get("failure_modes") == expected.get("failure_modes"),
            "失效与处理保持")

    residual = _residual_identity({key: value for key, value in packet.items()
                                  if key != "author_session"})
    add("identity_residual", not residual, "残留 %s" % residual if residual
        else "无残留身份字段")
    add("author_session_null", "author_session" in packet
        and packet["author_session"] is None,
        "作者会话置 null")
    return checks


def _anonymize_legacy(candidate):
    """返回脱敏包。身份字段置 null 或删除，redacted_for_judge 置 true。"""
    if not isinstance(candidate, dict):
        raise InputError("CANDIDATE_NOT_OBJECT", "candidate 必须是对象")
    _check_top_level(candidate)
    _check_engineering_structure(candidate)
    removed = []
    stripped = _strip_identity(candidate, removed, [])
    stripped["author_session"] = None
    stripped["redacted_for_judge"] = True

    residual = _residual_identity(
        {key: value for key, value in stripped.items() if key != "author_session"})
    checks = _evidence_integrity(candidate, stripped)
    failed = [item for item in checks if not item["pass"]]
    if residual or failed:
        detail = []
        if residual:
            detail.append("残留身份字段: %s" % ",".join(residual))
        for item in failed:
            detail.append("%s: %s" % (item["check"], item["detail"]))
        raise RedactionError("脱敏后校验不通过；%s" % "；".join(detail))

    return {
        "packet": stripped,
        "removed_fields": removed,
        "status": "REDACTED",
        "schema_version": LEGACY_SCHEMA_VERSION,
        "evidence_integrity": checks,
        "identity_paths_only": True,
        "semantic_preserved": True,
    }


def _new_identity_paths(candidate):
    from .schema_runtime import read_anonymization_policy
    policy = read_anonymization_policy()
    identity = policy["identity_paths"]
    top = {path[1:] for path in identity["top_level_remove"]
           + identity["top_level_null"]}
    result = set()
    for key in candidate:
        if key in top:
            if key == "role" and not (isinstance(candidate[key], str)
                    and SEAT_LABEL_RE.fullmatch(candidate[key].strip())):
                continue
            result.add(_path_text([key]))
    # Only direct metadata on legacy records is an identity-bearing path.
    # Cognition objects are closed by their schema; engineering role is data.
    for name in ("quality", "parameters", "scenario_analysis", "failure_modes", "replies"):
        node = candidate.get(name)
        if isinstance(node, dict):
            records = node.items()
        elif isinstance(node, list):
            records = enumerate(node)
        else:
            continue
        for index, record in records:
            if not isinstance(record, dict):
                continue
            for key in record:
                if key in IDENTITY_FIELDS or (name == "quality" and key in QUALITY_IDENTITY_KEYS):
                    result.add(_path_text([name, index, key]))
    signature = candidate.get("mechanism_signature")
    if isinstance(signature, dict):
        for dimension, record in signature.items():
            if isinstance(record, dict):
                for key in record:
                    if key in IDENTITY_FIELDS:
                        result.add(_path_text(["mechanism_signature", dimension, key]))
    return result


def _strip_new_identity(node, paths, prefix=()):
    if isinstance(node, dict):
        return {key: _strip_new_identity(value, paths, prefix + (key,))
                for key, value in node.items()
                if _path_text(list(prefix) + [key]) not in paths}
    if isinstance(node, list):
        return [_strip_new_identity(value, paths, prefix + (index,))
                for index, value in enumerate(node)]
    return node


def _check_new_legacy_refs(candidate):
    from .schema_runtime import validate_schema
    # Parameter source_ref objects also use the exact K01 source-ref contract.
    # String/null legacy references are preserved, never rewritten by text match.
    for parameter in candidate.get("parameters") or []:
        ref = parameter.get("source_ref")
        if isinstance(ref, dict):
            validate_schema("neutral-evidence-map", {
                "schema": "wishcad.neutral-evidence-map.v1", "run_id": "validation",
                "revision": "validation", "coordinator_only": True, "mappings": [{
                    "evidence_id": "EValidation", "private_source": ref,
                    "public_evidence": copy.deepcopy(ref), "content_transform": "NONE",
                    "purpose": "Validate declared parameter source_ref"}]})


def _new_integrity(original, packet, identity_paths, changes, anonymous_id):
    """Compare independently from the original tree, allowing exact leaf deltas."""
    expected = _drop_paths(original, identity_paths)
    expected["author_session"] = None
    expected["redacted_for_judge"] = True
    if anonymous_id is not None:
        expected["candidate_id"] = anonymous_id
        if "anonymous_id" in original:
            expected["anonymous_id"] = anonymous_id
    for pointer, before, after in changes:
        node = expected
        for part in pointer[:-1]:
            node = node[part]
        if not _same_json(node[pointer[-1]], before):
            raise RedactionError("Reference leaf is outside the original nonidentity tree")
        node[pointer[-1]] = after
    checks = [{"check": "kept:" + key,
               "pass": key in packet and _same_json(value, packet[key]),
               "detail": "Exact nonidentity values, types, order and containers"}
              for key, value in expected.items()]
    checks.append({"check": "all_fields_preserved", "pass": _same_json(expected, packet),
                   "detail": "Only declared identity, root markers, neutral ID and exact reference leaves changed"})
    checks.append({"check": "author_session_null",
                   "pass": "author_session" in packet and packet["author_session"] is None,
                   "detail": "Author session removed from public packet"})
    return checks


def anonymize(candidate, *, evidence_map=None, source_root=None, public_root=None,
              media_inspector=None, anonymous_id=None):
    """Anonymize an original carrier; maps are private and never returned.

    New carriers require their complete cognition projection. Legacy carriers
    retain their existing result version and cannot gain cognition completeness.
    """
    if not isinstance(candidate, dict):
        raise InputError("CANDIDATE_NOT_OBJECT", "candidate must be an object")
    if candidate.get("schema") != "wishcad.candidate.v1.1":
        if candidate.get("schema") not in (None, "wishcad.candidate.v1.0") or any(
                key in candidate for key in ("consumed_feature_ids", "decision_records", "critical_unknowns")):
            raise InputError("COGNITION_UPGRADE_REQUIRED", "A complete candidate v1.1 is required")
        if evidence_map is not None:
            raise RedactionError("Legacy evidence cannot receive a new cognition map")
        result = _anonymize_legacy(candidate)
        if anonymous_id is not None:
            if anonymous_id not in tuple("K%02d" % index for index in range(1, 6)):
                raise RedactionError("Anonymous ID must be K01-K05")
            result["packet"]["candidate_id"] = anonymous_id
        return result
    from .schema_runtime import validate_projection
    from .neutral_evidence import (ANONYMOUS_IDS, apply_evidence_map,
                                   reference_leaves, _secrets, _safe_bytes)
    validate_projection("candidate", candidate)
    _check_engineering_structure(candidate)
    _check_new_legacy_refs(candidate)
    chosen = anonymous_id if anonymous_id is not None else candidate.get("anonymous_id")
    if chosen is None and candidate.get("candidate_id") in ANONYMOUS_IDS:
        chosen = candidate["candidate_id"]
    if chosen not in ANONYMOUS_IDS:
        raise RedactionError("New candidate requires an explicit K01-K05 anonymous ID")
    if candidate.get("anonymous_id") is not None and candidate["anonymous_id"] != chosen:
        raise RedactionError("Anonymous ID conflicts with the original candidate")
    leaves = reference_leaves(candidate)
    if evidence_map is None:
        if leaves:
            raise RedactionError("Referenced evidence requires an exact private map and controlled copies")
        mapped = copy.deepcopy(candidate)
    else:
        mapped = apply_evidence_map(candidate, evidence_map, source_root, public_root, chosen,
                                    media_inspector=media_inspector)
    paths = _new_identity_paths(candidate)
    stripped = _strip_new_identity(mapped, paths)
    stripped["author_session"] = None
    stripped["redacted_for_judge"] = True
    stripped["candidate_id"] = chosen
    if "anonymous_id" in candidate:
        stripped["anonymous_id"] = chosen
    changes = []
    exact_paths = {json.dumps(item["private_source"], sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False): item["public_evidence"]["path"]
                   for item in evidence_map["mappings"]} if evidence_map is not None else {}
    for pointer, ref in leaves:
        key = json.dumps(ref, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False)
        if key not in exact_paths:
            raise RedactionError("An original reference has no exact private-map binding")
        changes.append((pointer, ref["path"], exact_paths[key]))
    checks = _new_integrity(candidate, stripped, paths, changes, chosen)
    if any(not item["pass"] for item in checks):
        raise RedactionError("Nonidentity candidate data changed during anonymization")
    if _private_map_residual(stripped):
        raise RedactionError("Private evidence-map paths cannot appear in public candidate")
    _safe_bytes(json.dumps(stripped, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                _secrets(candidate))
    validate_projection("candidate", stripped)
    return {"packet": stripped, "removed_fields": sorted(paths), "status": "REDACTED",
            "schema_version": SCHEMA_VERSION, "evidence_integrity": checks,
            "identity_paths_only": True, "semantic_preserved": True}


def _private_map_residual(node):
    if isinstance(node, dict):
        return any(_private_map_residual(value) for value in node.values())
    if isinstance(node, list):
        return any(_private_map_residual(value) for value in node)
    if isinstance(node, str):
        from .neutral_evidence import _private_path
        normalized = node.replace("\\", "/").casefold()
        return (_private_path(normalized) or "neutral-evidence-map" in normalized
                or bool(re.search(r"(?:^|/|\s)k0[1-5]-evidence-map\.json", normalized)))
    return False


def _parser():
    parser = argparse.ArgumentParser(
        prog="python -m cad_agent_showcase.governance.anonymize",
        description="送评包去标识：只删身份路径，工程证据原样保留")
    parser.add_argument("path", help="候选 JSON 文件")
    return parser


def cli(argv=None):
    args = _parser().parse_args(argv)
    from .envelope import run_cli

    def runner(payload):
        if not isinstance(payload, dict):
            raise InputError("CANDIDATE_NOT_OBJECT", "顶层必须是对象")
        target = payload.get("candidate", payload)
        try:
            return anonymize(target)
        except RedactionError as exc:
            from .envelope import RuleRejection
            raise RuleRejection("REDACTION_INTEGRITY_FAILED", str(exc))

    return run_cli("anonymize", runner, args)


if __name__ == "__main__":
    import sys
    sys.exit(cli(sys.argv[1:]))
