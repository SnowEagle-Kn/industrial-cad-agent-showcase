# -*- coding: utf-8 -*-
"""Canonical 确认绑定适配器（F06 整改，新建）。

F06 缺陷：旧绑定字段表遗漏正式确认合同的 source_manifest_sha256、
candidate_sha256、cad_scope_sha256、event_sha256；这些摘要在
`record_confirmation` 的 stored 中被丢弃，`invalidate` 只比旧字段表，
所以候选几何、CAD 范围、用户事件变化都不失效。

本模块提供：
- `CANONICAL_BINDING_VERSION`：绑定合同版本，字段集变更必须升版本。
- `BINDING_FIELDS`：与正式合同 bound_objects 对齐的必需字段集。
- `DECLARED_OPTIONAL_FIELDS`：声明型可选字段（如确认图纸摘要）；出现即参与
  摘要与逐字段比较，未出现记 not_compared，不冒充“未变化”。
- `EXCLUDED_METADATA`：明确排除的时间元数据（只有这些改不改失效）。
- `compute_binding_sha256(binding)`：规范化后求总摘要，用于复算比对。
- `rebind_from_objects(objects)`：从当前真实对象**实际重算**每个摘要。
- `diff_bindings(previous, current)`：逐字段差异。

A3d-1（T14）：`design_drawing_sha256` 进入 v1.2 声明型合同；旧版 v1.1 记录
与新合同比较时按合同版本变化显式报告，不静默沿用。

A3d-1b（P3-2）：`design_drawing` 可选对象改为**内容摘要描述符**：
接受 `{path, sha256}` 或 64 位 SHA-256 字符串，直接采用其中的内容摘要；
禁止再对描述符 JSON 做 `sha256_object` 冒充图纸摘要。G2 记录的
`design_drawing_sha256`（文件/目录内容摘要）与 rebind 由此同源。

语义边界：本模块只做摘要与字段比对，不证明对象内容本身正确，
也不证明用户事件真实；后者见 `confirm.py` 的 identity_assurance。
"""

import hashlib
import json
import ntpath
import os

from .envelope import InputError

CANONICAL_BINDING_VERSION = "wishcad.binding.v1.2"

# 对齐确认合同的 bound_objects，并保留 run_id/endpoint 等
# 合同 §9 要求绑定但 bound_objects 未单列的定位字段。
BINDING_FIELDS = (
    "run_id",
    "mode",
    "endpoint",
    "candidate_id",
    "candidate_version",
    "brief_sha256",
    "source_manifest_sha256",
    "candidate_sha256",
    "parameters_sha256",
    "assumptions_sha256",
    "rubric_sha256",
    "judge_report_sha256",
    "cad_scope_sha256",
    "capability_snapshot_sha256",
    "event_sha256",
)

# A3d-1：声明型可选字段。不是每次确认都有图纸（选择确认发生在出图前），
# 但一旦出现，图纸摘要必须进入总摘要、逐字段比较和失效判定。
DECLARED_OPTIONAL_FIELDS = (
    "design_drawing_sha256",
)

# 参与绑定摘要与比较的完整字段集。
BOUND_FIELDS = BINDING_FIELDS + DECLARED_OPTIONAL_FIELDS

# 唯一允许变化而不失效的元数据。列表之外的时间戳也视为实质字段缺失。
EXCLUDED_METADATA = (
    "recorded_at",
    "confirmed_at",
    "invalidated_at",
    "shown_at",
    "checked_at",
)

# 对象名 → 绑定字段名。rebind_from_objects 用这张表重算摘要。
OBJECT_TO_FIELD = {
    "brief": "brief_sha256",
    "source_manifest": "source_manifest_sha256",
    "candidate": "candidate_sha256",
    "parameters": "parameters_sha256",
    "assumptions": "assumptions_sha256",
    "rubric": "rubric_sha256",
    "judge_report": "judge_report_sha256",
    "cad_scope": "cad_scope_sha256",
    "capability": "capability_snapshot_sha256",
    "event": "event_sha256",
}

# A3d-1：可选对象。提供则重算并进入绑定；未提供不是缺失，不伪造空摘要。
# A3d-1b/P3-2：design_drawing 的值是内容摘要描述符，不再按 JSON 对象求摘要。
OPTIONAL_OBJECT_TO_FIELD = {
    "design_drawing": "design_drawing_sha256",
}

# 不参与摘要的顶层键（版本标记与排除元数据）。
_NON_BOUND_KEYS = ("canonical_binding_version", "binding_sha256") + EXCLUDED_METADATA


def canonical_bytes(value):
    """规范化序列化：键排序、UTF-8、紧凑分隔符、不转义非 ASCII。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def sha256_object(value):
    """对任意 JSON 对象求摘要，供 rebind_from_objects 使用。"""
    return sha256_bytes(canonical_bytes(value))


def _sha256_hex(value):
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value.lower())


def declared_content_sha256(value, field="design_drawing"):
    """读取调用方声明的**内容摘要**，不再对描述符 JSON 求摘要。

    A3d-1b/P3-2：G2 记录的是图纸文件/目录内容摘要；rebind 的
    `design_drawing` 必须用同一内容摘要，不能把 `{path, sha256}` 的
    JSON 规范化摘要当成图纸摘要（两者同名不同义）。
    """
    if _sha256_hex(value):
        return value.lower()
    if isinstance(value, dict):
        sha = value.get("sha256")
        if _sha256_hex(sha):
            return sha.lower()
    raise InputError(
        "DECLARED_SHA256_INVALID",
        "%s 必须是 {path, sha256} 描述符或 64 位 SHA-256 字符串；"
        "不得对 JSON 对象求摘要冒充内容摘要" % field)


def bound_subset(binding):
    """只保留绑定字段（含声明型可选字段）+ 版本，供摘要与比较使用。"""
    if not isinstance(binding, dict):
        raise InputError("BINDING_NOT_OBJECT", "绑定必须是对象")
    subset = {}
    for field in BOUND_FIELDS:
        if field in binding:
            subset[field] = binding[field]
    subset["canonical_binding_version"] = binding.get(
        "canonical_binding_version", CANONICAL_BINDING_VERSION)
    return subset


def compute_binding_sha256(binding):
    """绑定总摘要：对 `bound_subset` 的规范化序列化求 SHA-256。

    范围（`receipt_sha256_scope` 同款口径，独立审查第 2 轮 P2-E）：
    含 `BOUND_FIELDS` 中**出现**的字段 + `canonical_binding_version`；
    不含 `EXCLUDED_METADATA`（时间戳）、`binding_sha256` 自身、以及其他
    未声明键。复算方法见 `BINDING_SHA256_SCOPE`。
    """
    return sha256_bytes(canonical_bytes(bound_subset(binding)))


BINDING_SHA256_SCOPE = {
    "included": list(BOUND_FIELDS) + ["canonical_binding_version"],
    "excluded": list(EXCLUDED_METADATA) + ["binding_sha256"],
    "algorithm": "sha256(canonical_json: sort_keys, utf-8, separators=(',', ':'))",
    "note": "含 BOUND_FIELDS 中实际出现的字段；必需字段未出现的由 missing_fields "
            "拦截，声明型可选字段未出现的记 not_compared",
}


def missing_fields(binding):
    if not isinstance(binding, dict):
        raise InputError("BINDING_NOT_OBJECT", "绑定必须是对象")
    return [field for field in BINDING_FIELDS if not binding.get(field)]


def unexpected_fields(binding):
    """列出绑定里**未声明**的键（P2-03：字段多余也不能静默）。

    合同 §8.3：新增实质字段必须进入 canonical 绑定合同。未声明的键既不
    参与摘要、也不参与逐字段比较，如果不报出来，等于允许绑定悄悄漂移。
    """
    if not isinstance(binding, dict):
        return []
    allowed = set(BOUND_FIELDS) | {"canonical_binding_version",
                                   "binding_sha256"} | set(EXCLUDED_METADATA)
    return sorted(key for key in binding if key not in allowed)


def diff_bindings(previous, current):
    """返回 changed_fields（逐字段）与摘要是否变化。

    `current` 里**没有出现的键**不参与判定，记进 `not_compared`：
    只给了部分字段的调用方不该被当成“把这几个字段清空了”。
    只有显式给了键、且值为空（None/""），才算“由有变无”。

    `unexpected` 列出未声明键：字段多余同样不静默（P2-03）。
    """
    previous = previous if isinstance(previous, dict) else {}
    current = current if isinstance(current, dict) else {}
    changed = []
    not_compared = []
    for field in BOUND_FIELDS:
        if field not in current:
            not_compared.append(field)
            continue
        if previous.get(field) != current.get(field):
            changed.append(field)
    previous_sha = compute_binding_sha256(previous) if previous else None
    current_sha = compute_binding_sha256(current) if current else None
    ignored = sorted({key for key in set(list(previous) + list(current))
                      if key in EXCLUDED_METADATA
                      and previous.get(key) != current.get(key)})
    previous_version = previous.get("canonical_binding_version")
    current_version = current.get("canonical_binding_version",
                                  CANONICAL_BINDING_VERSION)
    return {
        "changed_fields": changed,
        "not_compared": not_compared,
        "unexpected_fields": unexpected_fields(current),
        "previous_binding_sha256": previous_sha,
        "current_binding_sha256": current_sha,
        "binding_sha256_changed": previous_sha != current_sha,
        "ignored_metadata_changes": ignored,
        "previous_binding_version": previous_version,
        "current_binding_version": current_version,
        "binding_version_changed": bool(
            previous_version and previous_version != current_version),
        "canonical_binding_version": CANONICAL_BINDING_VERSION,
    }


# 只在定位、不来自对象摘要的字段：必须由调用方提供（身份由流程给定，
# 不能从内容“算”出来）。rebind_from_objects 缺这些就报错，不默认空。
IDENTITY_FIELDS = ("run_id", "mode", "endpoint", "candidate_id",
                   "candidate_version")


def rebind_from_objects(objects, locators=None, identity=None):
    """从当前真实对象重新计算每个摘要。

    objects: {brief|source_manifest|candidate|parameters|assumptions|rubric|
              judge_report|cad_scope|capability|event: <已读入的 JSON 对象>}
              可选 design_drawing：提供则重算 design_drawing_sha256。
    identity: {run_id, mode, endpoint, candidate_id, candidate_version}
              这四个定位字段不能由内容摘要推出，必须显式给。
    缺任一必需对象或定位字段 → InputError，不允许用含义未定的字符串凑齐。
    locators: 可选，记录每个对象读自哪个文件（写进回执，便于复算）。
    """
    if not isinstance(objects, dict):
        raise InputError("OBJECTS_NOT_OBJECT", "objects 必须是对象")
    missing = [name for name in OBJECT_TO_FIELD if name not in objects]
    if missing:
        raise InputError(
            "BOUND_OBJECT_MISSING",
            "缺少待绑定对象：%s；不得用未定义字符串替代" % ",".join(sorted(missing)))
    for name, value in objects.items():
        if name not in OBJECT_TO_FIELD and name not in OPTIONAL_OBJECT_TO_FIELD:
            raise InputError("BOUND_OBJECT_UNKNOWN",
                             "未声明的绑定对象 %s；新增对象须升绑定版本" % name)
        if value is None:
            raise InputError("BOUND_OBJECT_NULL", "绑定对象 %s 为 null" % name)

    identity = dict(identity or {})
    # 对象里若已带定位字段（如 brief.run_id、candidate.candidate_id），
    # 允许自动取；显式 identity 优先。仍缺则报错。
    #
    # candidate_version 只认正式字段 `candidate_version`；文档 schema 的
    # `version`（如 "1.0"）是**另一个字段**，不得当候选版本用。
    # 只有当正式字段缺失、且调用方显式允许时，才回退读 `version`，
    # 并在结果里标 candidate_version_source，不静默替换。
    allow_legacy = bool((identity or {}).get("allow_legacy_version_fallback"))
    candidate_version = _first(identity.get("candidate_version"),
                               (objects.get("candidate") or {}).get("candidate_version"),
                               (objects.get("brief") or {}).get("candidate_version"))
    version_source = "candidate.candidate_version" if candidate_version else None
    if not candidate_version and allow_legacy:
        candidate_version = _first((objects.get("candidate") or {}).get("version"),
                                   (objects.get("brief") or {}).get("version"))
        version_source = "LEGACY_VERSION_FIELD" if candidate_version else None
    derived = {
        "run_id": _first(identity.get("run_id"),
                         (objects.get("brief") or {}).get("run_id"),
                         (objects.get("candidate") or {}).get("run_id")),
        "mode": _first(identity.get("mode"),
                       (objects.get("brief") or {}).get("mode"),
                       (objects.get("candidate") or {}).get("mode"),
                       (objects.get("cad_scope") or {}).get("mode")),
        "endpoint": _first(identity.get("endpoint"),
                           (objects.get("cad_scope") or {}).get("endpoint")),
        "candidate_id": _first(identity.get("candidate_id"),
                               (objects.get("candidate") or {}).get("candidate_id")),
        "candidate_version": candidate_version,
    }
    absent = [field for field, value in derived.items() if not value]
    if absent:
        raise InputError(
            "BINDING_IDENTITY_MISSING",
            "绑定定位字段缺 %s；这些字段不能由内容摘要推出，必须显式给 identity"
            % ",".join(sorted(absent)))

    binding = {"canonical_binding_version": CANONICAL_BINDING_VERSION}
    binding.update({field: derived[field] for field in IDENTITY_FIELDS})
    sources = {}
    for field in IDENTITY_FIELDS:
        sources[field] = {"object": None, "locator": None,
                          "method": "identity_supplied_not_hashed"}
    for name, field in OBJECT_TO_FIELD.items():
        binding[field] = sha256_object(objects[name])
        sources[field] = {
            "object": name,
            "locator": (locators or {}).get(name),
            "method": "sha256(canonical_json)",
        }
    for name, field in OPTIONAL_OBJECT_TO_FIELD.items():
        if name not in objects:
            continue
        if name == "design_drawing":
            # A3d-1b/P3-2：描述符或 64 位字符串，直接采用内容摘要。
            value = objects[name]
            binding[field] = declared_content_sha256(value, field)
            source = {
                "object": name,
                "locator": (locators or {}).get(name),
                "method": "declared_content_sha256",
                "optional": True,
            }
            if isinstance(value, dict) and value.get("path"):
                source["declared_path"] = value["path"]
                if not source["locator"]:
                    source["locator"] = value["path"]
            sources[field] = source
            continue
        binding[field] = sha256_object(objects[name])
        sources[field] = {
            "object": name,
            "locator": (locators or {}).get(name),
            "method": "sha256(canonical_json)",
            "optional": True,
        }
    binding["binding_sha256"] = compute_binding_sha256(binding)
    return {
        "binding": binding,
        "binding_sha256": binding["binding_sha256"],
        "field_sources": sources,
        "candidate_version_source": version_source,
        "canonical_binding_version": CANONICAL_BINDING_VERSION,
        "recomputed": True,
        "excluded_metadata": list(EXCLUDED_METADATA),
    }


def _first(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


# 回执路径定位不进入 BINDING_FIELDS，也不改变 canonical 绑定合同。
RUN_PATH_ROOT = "run_dir"


def receipt_path_fields(file_path, run_dir):
    """兼容保留 path，内部文件另记相对于运行根的定位；外部文件不搬迁。"""
    fields = {"path": file_path}
    if not isinstance(file_path, str) or not file_path:
        return fields
    root = os.path.realpath(os.path.abspath(run_dir))
    target = os.path.realpath(os.path.abspath(file_path))
    try:
        internal = os.path.commonpath([root, target]) == root
    except ValueError:  # 不同盘符
        internal = False
    if internal:
        fields.update(path_root=RUN_PATH_ROOT,
                      relative_path=os.path.relpath(target, root).replace("\\", "/"))
    return fields


def resolve_receipt_path(entry, run_dir):
    """锚点优先；兼容旧绝对路径与运行根相对路径，不按文件名猜迁移位置。

    path 保留给旧读者。存在 path_root 时 relative_path（或相对 path）才是
    权威定位；未知锚点、越根、盘符相对路径及链接逃逸均不能匹配。
    """
    if not isinstance(entry, dict):
        return None
    marker = entry.get("path_root")
    if "path_root" in entry and marker != RUN_PATH_ROOT:
        return None
    value = entry.get("relative_path", entry.get("path")) if marker else entry.get("path")
    if not isinstance(value, str) or not value or "\0" in value:
        return None
    root = os.path.realpath(os.path.abspath(run_dir))
    absolute = os.path.isabs(value) or ntpath.isabs(value)
    if marker and (absolute or ntpath.splitdrive(value)[0]):
        return None
    if absolute:
        return os.path.realpath(os.path.abspath(value))
    if ntpath.splitdrive(value)[0]:
        return None
    value = value.replace("\\", os.sep).replace("/", os.sep)
    target = os.path.realpath(os.path.join(root, value))
    try:
        if os.path.commonpath([root, target]) != root:
            return None
    except ValueError:
        return None
    return target


def receipt_path_matches(entry, expected_path, run_dir):
    actual = resolve_receipt_path(entry, run_dir)
    expected = os.path.realpath(os.path.abspath(expected_path))
    root = os.path.realpath(os.path.abspath(run_dir))
    try:
        if os.path.commonpath([root, expected]) != root:
            return False
    except ValueError:
        return False
    return actual is not None and os.path.normcase(actual) == os.path.normcase(expected)
