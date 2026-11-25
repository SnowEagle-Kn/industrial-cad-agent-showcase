# -*- coding: utf-8 -*-
"""确认绑定与失效（F05/F06 整改）。

语义对齐现行确认适配器的 archive_invalidation：对象变更后返回新记录，
旧确认转 INVALIDATED，不改原记录。本模块不 import 该适配器。

F05 缺陷：旧版只要求 `user_event_ref` 非空就 RECORDED，`event=None` 与
`event.action=DEFER` 都能通过。整改后必须：事件结构完整、动作在允许集内、
选中候选/版本/mode 与绑定一致、且具备两条取证路径之一。

F06 缺陷：旧版 BINDING_FIELDS 缺 candidate_sha256 / cad_scope_sha256 /
event_sha256 / source_manifest_sha256，实质变化不失效。整改后绑定字段集
与正式合同 bound_objects 对齐，并存总摘要 `binding_sha256` 参与比较。

边界：本模块只做结构校验，不能证明事件由用户真实产生，故结果显式给
`identity_assurance` 与 `assurance_note`；不写“已验证用户身份”。
"""

import argparse
import copy
import re

from .envelope import InputError
from .binding import (BINDING_FIELDS, BOUND_FIELDS, CANONICAL_BINDING_VERSION,
                      DECLARED_OPTIONAL_FIELDS, EXCLUDED_METADATA,
                      IDENTITY_FIELDS as LOCALIZING_FIELDS,
                      compute_binding_sha256, diff_bindings,
                      rebind_from_objects, sha256_object, unexpected_fields)

ACTION_ACCEPT = "ACCEPT"
ACTION_OVERRIDE = "OVERRIDE"
ACTION_DEFER = "DEFER"
ACTION_REJECT = "REJECT"
ACTION_REVISE = "REVISE"
ACTION_REJUDGE = "REJUDGE"

RECORDING_ACTIONS = (ACTION_ACCEPT, ACTION_OVERRIDE)
NON_RECORDING_ACTIONS = (ACTION_DEFER, ACTION_REJECT, ACTION_REVISE, ACTION_REJUDGE)
ALL_ACTIONS = RECORDING_ACTIONS + NON_RECORDING_ACTIONS

ASSURANCE_HOST = "host_receipt"
ASSURANCE_LOCAL = "locally_recorded"
ASSURANCE_INSUFFICIENT = "insufficient"

PRIMITIVE_NOTE = ("本入口仅为事件/绑定登记原语，未执行确认卡检查；"
                  "正式确认须经独立确认卡门控。")

ASSURANCE_NOTE = ("本函数只校验事件结构与取证字段，不能证明事件由用户真实产生；"
                  "真实身份须由宿主回执或采集者本地记录另行核对。")

# 兼容 V1.0 公开名：现在指向 binding.BINDING_FIELDS（15 项必需字段）。
__all__ = [
    "BINDING_FIELDS", "BOUND_FIELDS", "DECLARED_OPTIONAL_FIELDS",
    "EXCLUDED_METADATA", "record_confirmation", "invalidate",
    "selection_record", "classify_event", "cli", "ALL_ACTIONS",
    "CANONICAL_BINDING_VERSION", "ASSURANCE_NOTE",
]


MODE_ENDPOINTS = {
    "NO_DRAWING_CONCEPT": "CONCEPT_CAD",
    "DRAWING_TO_MANUFACTURING": "MANUFACTURING_CAD",
}


def _check_binding_values(binding):
    """绑定的取值域：mode 必须是已知模式，endpoint 必须与 mode 对应。

    只做取值校验，不猜缺失值（缺失由 BINDING_FIELDS_MISSING 负责）。
    """
    mode = binding.get("mode")
    if isinstance(mode, str) and mode and mode not in MODE_ENDPOINTS:
        raise InputError("BINDING_MODE_UNKNOWN",
                         "mode 必须是 %s 之一，收到 %r"
                         % ("/".join(sorted(MODE_ENDPOINTS)), mode),
                         "binding/mode")
    endpoint = binding.get("endpoint")
    if isinstance(mode, str) and mode in MODE_ENDPOINTS \
            and isinstance(endpoint, str) and endpoint \
            and endpoint != MODE_ENDPOINTS[mode]:
        raise InputError("BINDING_ENDPOINT_MODE_MISMATCH",
                         "mode=%s 对应 endpoint=%s，收到 %r"
                         % (mode, MODE_ENDPOINTS[mode], endpoint),
                         "binding/endpoint")
    for field in BOUND_FIELDS:
        if not field.endswith("_sha256"):
            continue
        value = binding.get(field)
        if field in DECLARED_OPTIONAL_FIELDS and field not in binding:
            continue
        if not _sha_like(value):
            raise InputError("BINDING_SHA256_INVALID",
                             "%s 必须是 64 位十六进制 SHA-256 字符串" % field,
                             "binding/%s" % field)


def _sha_like(value):
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value.lower())


_ISO_LIKE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def _iso_like(value):
    """事件时间必须像 ISO-8601；空串与自由文本不算取证。"""
    return isinstance(value, str) and bool(_ISO_LIKE.match(value.strip()))


def classify_event(event):
    """判断取证路径。返回 (assurance, reasons)。"""
    reasons = []
    if not isinstance(event, dict):
        return ASSURANCE_INSUFFICIENT, ["EVENT_NOT_OBJECT"]
    host_ok = bool(event.get("host_event_id")) and bool(event.get("session_id")) \
        and _iso_like(event.get("observed_at"))
    local_ok = event.get("locally_recorded") is True \
        and _sha_like(event.get("capture_sha256")) \
        and bool(event.get("captured_by"))
    if host_ok:
        return ASSURANCE_HOST, reasons
    if local_ok:
        return ASSURANCE_LOCAL, reasons
    if not event.get("host_event_id") and not event.get("locally_recorded") is True:
        reasons.append("NO_HOST_RECEIPT_AND_NOT_LOCALLY_RECORDED")
    if event.get("host_event_id") and not event.get("session_id"):
        reasons.append("HOST_RECEIPT_MISSING_SESSION")
    if event.get("host_event_id") and not _iso_like(event.get("observed_at")):
        reasons.append("HOST_RECEIPT_MISSING_OR_INVALID_TIME")
    if event.get("locally_recorded") is True and not _sha_like(event.get("capture_sha256")):
        reasons.append("LOCAL_CAPTURE_SHA_INVALID")
    if event.get("locally_recorded") is True and not event.get("captured_by"):
        reasons.append("LOCAL_CAPTURE_RECORDER_MISSING")
    return ASSURANCE_INSUFFICIENT, reasons


def _check_event_matches_binding(event, binding):
    problems = []
    action = event.get("action")
    if action not in ALL_ACTIONS:
        problems.append({"code": "ACTION_UNKNOWN", "detail": str(action)})
    if action in NON_RECORDING_ACTIONS:
        problems.append({"code": "ACTION_NOT_A_CONFIRMATION", "detail": action})
    selected = event.get("selected_candidate_id")
    if selected is None:
        problems.append({"code": "SELECTED_CANDIDATE_MISSING", "detail": None})
    elif selected != binding.get("candidate_id"):
        problems.append({"code": "SELECTED_CANDIDATE_MISMATCH",
                         "detail": {"event": selected,
                                    "binding": binding.get("candidate_id")}})
    version = event.get("candidate_version")
    if version is None:
        problems.append({"code": "CANDIDATE_VERSION_MISSING", "detail": None})
    elif version != binding.get("candidate_version"):
        problems.append({"code": "CANDIDATE_VERSION_MISMATCH",
                         "detail": {"event": version,
                                    "binding": binding.get("candidate_version")}})
    mode = event.get("mode")
    if mode is None:
        problems.append({"code": "MODE_MISSING", "detail": None})
    elif mode != binding.get("mode"):
        problems.append({"code": "MODE_MISMATCH",
                         "detail": {"event": mode, "binding": binding.get("mode")}})
    # 旧合同/既有调用可能不带 event.run_id；缺省保留兼容，
    # 但一旦宿主明确提供，必须与当前 binding 的任务运行一致。
    if "run_id" in event and event.get("run_id") != binding.get("run_id"):
        problems.append({"code": "EVENT_RUN_ID_MISMATCH",
                         "detail": {"event": event.get("run_id"),
                                    "binding": binding.get("run_id")}})
    return problems


def record_confirmation(binding, user_event_ref, event=None):
    """底层登记原语；只校验结构/事件/摘要，不证明确认卡已放行。

    确认卡由工作流校验；直接调用仍兼容登记和失效消费者。
    """
    if not isinstance(binding, dict):
        raise InputError("BINDING_NOT_OBJECT", "binding 必须是对象")
    missing = [field for field in BINDING_FIELDS if not binding.get(field)]
    if missing:
        # 绑定不齐是“没有可登记的确认”，不是输入格式错：返回结构化拒绝，
        # 让调用方能读到缺哪几项，而不是整条链抛异常。
        return {
            "state": "NOT_REQUESTED",
            "recorded": False,
            "card_checked": False,
            "confirmation_entry": "record_confirmation",
            "card_check_note": PRIMITIVE_NOTE,
            "reason": "BINDING_FIELDS_MISSING",
            "missing_fields": missing,
            "binding": dict(binding),
            "user_event_ref": user_event_ref,
            "event": event,
            "identity_assurance": ASSURANCE_INSUFFICIENT,
            "assurance_note": ASSURANCE_NOTE,
            "canonical_binding_version": CANONICAL_BINDING_VERSION,
            "engineering_approval": False,
            "production_approved": False,
        }
    _check_binding_values(binding)

    base = {
        "card_checked": False,
        "confirmation_entry": "record_confirmation",
        "card_check_note": PRIMITIVE_NOTE,
        "identity_assurance": ASSURANCE_INSUFFICIENT,
        "assurance_note": ASSURANCE_NOTE,
        "canonical_binding_version": binding.get(
            "canonical_binding_version", CANONICAL_BINDING_VERSION),
        "engineering_approval": False,
        "production_approved": False,
    }
    event_run_id_check = "NOT_CHECKED"

    if event is None:
        return dict(base, state="NOT_REQUESTED", recorded=False,
                    reason="EVENT_MISSING_USER_EVENT_REF_ALONE_IS_NOT_CONFIRMATION")

    # 非对象事件先拦掉：classify_event 会返回 insufficient，
    # _check_event_matches_binding 需要 dict，不能让它抛 AttributeError。
    if not isinstance(event, dict):
        return dict(base, state="REJECTED", recorded=False,
                    reason="EVENT_NOT_OBJECT",
                    event_problems=[{"code": "EVENT_NOT_OBJECT",
                                     "detail": type(event).__name__}],
                    identity_assurance=ASSURANCE_INSUFFICIENT)

    # 缺 user_event_ref：只有事件对象不等于有可追溯的引用，不得 RECORDED。
    if not (isinstance(user_event_ref, str) and user_event_ref.strip()):
        return dict(base, state="NOT_REQUESTED", recorded=False,
                    reason="USER_EVENT_REF_MISSING")

    event_run_id_check = ("MATCHED" if "run_id" in event else "LEGACY_OMITTED")
    assurance, assurance_reasons = classify_event(event)
    problems = _check_event_matches_binding(event, binding)
    if problems:
        codes = [item["code"] for item in problems]
        state = "NOT_REQUESTED" if any(
            code.startswith("ACTION_NOT_A_CONFIRMATION") for code in codes) else "REJECTED"
        return dict(base, state=state, recorded=False,
                    reason="EVENT_INVALID:" + ",".join(codes),
                    event_problems=problems,
                    event_run_id_check=("MISMATCH" if "run_id" in event and any(
                        item["code"] == "EVENT_RUN_ID_MISMATCH" for item in problems)
                        else event_run_id_check),
                    identity_assurance=assurance)
    if assurance == ASSURANCE_INSUFFICIENT:
        return dict(base, state="NOT_REQUESTED", recorded=False,
                    reason="EVENT_ASSURANCE_INSUFFICIENT",
                    assurance_reasons=assurance_reasons)

    # 绑定若已声明 event_sha256，必须与本次事件摘要一致；否则是旧事件在冒充。
    declared_event_sha = binding.get("event_sha256")
    actual_event_sha = sha256_object(event)
    if declared_event_sha and declared_event_sha != actual_event_sha:
        return dict(base, state="REJECTED", recorded=False,
                    reason="EVENT_SHA256_MISMATCH",
                    event_problems=[{"code": "EVENT_SHA256_MISMATCH",
                                     "detail": {"binding": declared_event_sha,
                                                "event": actual_event_sha}}],
                    identity_assurance=assurance)

    stored = {field: binding[field] for field in BOUND_FIELDS if field in binding}
    stored["canonical_binding_version"] = binding.get(
        "canonical_binding_version", CANONICAL_BINDING_VERSION)
    stored["binding_sha256"] = compute_binding_sha256(stored)
    return dict(
        base,
        state="RECORDED",
        recorded=True,
        reason=None,
        user_event_ref=user_event_ref,
        event_ref_used=True,
        event=copy.deepcopy(event),
        binding=stored,
        binding_sha256=stored["binding_sha256"],
        identity_assurance=assurance,
        event_run_id_check=event_run_id_check,
        checked_objects=len(BINDING_FIELDS),
        optional_fields_checked=[field for field in DECLARED_OPTIONAL_FIELDS
                                 if field in stored],
    )


def invalidate(previous, current_binding):
    """返回新检查点。旧记录保留且原对象不被改写。

    逐字段 + 绑定总摘要都参与；只改 EXCLUDED_METADATA 中的时间戳不失效。
    """
    if not isinstance(previous, dict):
        raise TypeError("previous 必须是 dict")
    if not isinstance(current_binding, dict):
        raise InputError("BINDING_NOT_OBJECT", "current_binding 必须是对象")
    extra = unexpected_fields(current_binding)
    if extra:
        # 字段多余不静默：新增实质字段必须先进 canonical 绑定合同（§8.3）。
        raise InputError(
            "BINDING_FIELD_UNDECLARED",
            "current_binding 含未声明的键：%s；新增实质字段须先升绑定版本"
            % ",".join(extra))
    original = copy.deepcopy(previous)
    result = copy.deepcopy(previous)
    if not isinstance(previous.get("binding"), dict):
        # 从未登记成功的记录没有可冻结的绑定：如实说“无可失效”，
        # 不能当“全部变化”，也不能抛异常让调用方拿不到结论。
        return {
            "state": "NOT_RECORDED",
            "invalidated": False,
            "reason": "PREVIOUS_NOT_RECORDED_NOTHING_TO_INVALIDATE",
            "previous_state": previous.get("state"),
            "previous_reason": previous.get("reason"),
            "continues_cad": False,
            "re_review_required": True,
            "note": "旧记录没有绑定对象，说明当时未登记为 RECORDED；不需要失效，"
                    "但也不得据此继续 CAD",
        }
    stored = previous["binding"]
    diff = diff_bindings(stored, current_binding)
    changed = list(diff["changed_fields"])
    # 只有字段集完整时，才允许“逐字段看不出差异但总摘要变了”推出失效；
    # 部分字段调用方（如只给 10 个对象摘要）不得被当成清空其余字段。
    # 合同版本变化是实质变化，即使可选字段未比较也要失效（A3d-1）。
    if diff["binding_sha256_changed"] and not changed and (
            not diff["not_compared"] or diff["binding_version_changed"]):
        changed = ["binding_sha256"]
    if changed:
        result["state"] = "INVALIDATED"
        result["invalidated_by"] = {
            "changed_fields": changed,
            "not_compared": diff["not_compared"],
            "previous_binding_sha256": diff["previous_binding_sha256"],
            "current_binding_sha256": diff["current_binding_sha256"],
            "ignored_metadata_changes": diff["ignored_metadata_changes"],
            "previous_binding_version": diff["previous_binding_version"],
            "current_binding_version": diff["current_binding_version"],
            "binding_version_changed": diff["binding_version_changed"],
            "canonical_binding_version": diff["canonical_binding_version"],
        }
        result["previous_event_refs"] = [previous.get("user_event_ref")]
        result["continues_cad"] = False
        result["re_review_required"] = True
    else:
        result["state"] = previous.get("state", "UNCHANGED")
        result["unchanged_metadata_only"] = bool(diff["ignored_metadata_changes"])
        result["not_compared"] = diff["not_compared"]
        result["previous_binding_version"] = diff["previous_binding_version"]
        result["current_binding_version"] = diff["current_binding_version"]
        result["binding_version_changed"] = diff["binding_version_changed"]
        if diff["not_compared"]:
            result["partial_comparison_note"] = (
                "current_binding 未提供这些字段，本次未比较；"
                "不能据此认为它们未变")
    if previous != original:
        raise RuntimeError("旧确认记录被改写")
    return result


def selection_record(judge_ranking, user_selected):
    """用户改选不改写原评分，分别记录选择和分歧。"""
    return {
        "judge_ranking_kept": list(judge_ranking),
        "user_selected": user_selected,
        "agreement": bool(judge_ranking) and user_selected == judge_ranking[0],
        "scores_modified": False,
    }


def _parser():
    parser = argparse.ArgumentParser(
        prog="python -m cad_agent_showcase.governance.confirm",
        description="底层确认登记与失效原语（不含确认卡闸；正式确认用 pipeline confirm）")
    parser.add_argument("path", help="含 binding、user_event_ref、event 的 JSON")
    return parser


def confirm_spec(payload):
    """CLI 主体：登记确认；可再判失效。

    定位（第 3 轮 P2-06 明确）：本子命令是**底层登记原语**，只做事件与绑定
    的结构校验，**不包含确认卡闸**——卡闸在 `pipeline` 的 `confirm` 步
    （六项检查从上游产物实读 + 跨步回执链）。所以本命令的输出必须显式
    声明 `card_checked=false`，不能让人把它当成“确认卡已放行”。

    失效对照的两种给法（都要求给全，不猜）：
      * `previous` + `current_binding`：调用方已算好的两份绑定；
      * `previous` + `current_objects`：10 个当前真实对象，由
        `binding.rebind_from_objects` 现场复算摘要。
    两者同时给出 → InputError，不替调用方选。
    """
    if not isinstance(payload, dict):
        raise InputError("NOT_AN_OBJECT", "顶层必须是 JSON 对象")
    binding = payload.get("binding")
    if not isinstance(binding, dict):
        raise InputError("BINDING_MISSING", "缺少 binding 对象")
    event = payload.get("event")
    result = record_confirmation(binding, payload.get("user_event_ref"), event)
    result["card_checked"] = False
    result["card_check_note"] = (
        "本命令是底层登记原语，未执行确认卡六项检查；"
        "正式确认须走 pipeline 的 confirm 步")

    has_current = "current_binding" in payload or "current_objects" in payload
    if "previous" not in payload and not has_current:
        return result
    if "previous" not in payload:
        raise InputError("PREVIOUS_MISSING",
                         "给了 current_binding/current_objects 就必须给 previous")
    previous = payload.get("previous")
    if not isinstance(previous, dict):
        raise InputError("PREVIOUS_MISSING", "previous 必须是对象")
    if "current_binding" in payload and "current_objects" in payload:
        raise InputError("CURRENT_BINDING_AMBIGUOUS",
                         "current_binding 与 current_objects 只能给一个")
    if "current_objects" in payload:
        objects = payload["current_objects"]
        if not isinstance(objects, dict):
            raise InputError("CURRENT_OBJECTS_NOT_OBJECT",
                             "current_objects 必须是对象")
        # 定位字段不从对象猜：优先用调用方显式给的 identity，否则用旧记录
        # 里已经冻结的那 5 个（run_id/mode/endpoint/candidate_id/
        # candidate_version）。都不给才报错，不默认空、不读文档 schema 版本。
        identity = payload.get("identity")
        if not isinstance(identity, dict) and isinstance(previous.get("binding"), dict):
            identity = {field: previous["binding"].get(field)
                        for field in LOCALIZING_FIELDS}
        current = rebind_from_objects(objects, payload.get("object_locators"),
                                      identity)["binding"]
    elif "current_binding" in payload:
        current = payload["current_binding"]
        if not isinstance(current, dict):
            raise InputError("BINDING_NOT_OBJECT",
                             "current_binding 必须是对象")
    else:
        current = binding
    return {"recorded_result": result,
            "card_checked": False,
            "confirmation_entry": "confirm_spec",
            "card_check_note": PRIMITIVE_NOTE,
            "invalidation": invalidate(previous, current)}


def cli(argv=None):
    args = _parser().parse_args(argv)
    from .envelope import run_cli
    return run_cli("confirm", confirm_spec, args)


if __name__ == "__main__":
    import sys
    sys.exit(cli(sys.argv[1:]))
