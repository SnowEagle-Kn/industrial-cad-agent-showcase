# -*- coding: utf-8 -*-
"""Analysis-layer dependency scope for a changed source.

Only decision-critical objects are scanned: qualification, comparison,
selection and handoff. The formal version binding and invalidation chain are
not modified here; the report says so explicitly.
"""
import json
import re
from pathlib import Path, PureWindowsPath

from .envelope import InputError

SCHEMA = "wishcad.decision-dependencies.v1"
SCOPES = (
    ("review/qualification", "QUALIFICATION"),
    ("review/comparison", "COMPARISON"),
    ("selection", "SELECTION"),
    ("handoff", "HANDOFF"),
)
MAX_FILES = 4000
MAX_BYTES = 8 * 1024 * 1024


def _kind(relative):
    for prefix, kind in SCOPES:
        if relative.startswith(prefix + "/"):
            return kind
    return None


def _load(path):
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None


def _mentions(node, wanted):
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if current.get("path") == wanted:
                return True
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return False


def analyze(root, payload):
    root = Path(root).resolve()
    changed = payload.get("changed_source_refs")
    if not isinstance(changed, list) or not changed:
        raise InputError("ANALYSIS_SCOPE_INVALID", "须给出至少一个变更来源")
    paths = []
    for ref in changed:
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not ref["path"].strip():
            raise InputError("ANALYSIS_SCOPE_INVALID", "变更来源须含 run 相对路径")
        relative = ref["path"].replace("\\", "/")
        if (relative.startswith("/") or ":" in relative or PureWindowsPath(relative).drive
                or any(part in ("", ".", "..") for part in relative.split("/"))):
            raise InputError("ANALYSIS_SCOPE_INVALID", "变更来源路径须在 run 内")
        target = root / relative
        if not target.resolve().is_relative_to(root) or not target.is_file():
            raise InputError("ANALYSIS_SOURCE_UNKNOWN", "变更来源不在 run 内：" + relative)
        digest = ref.get("sha256")
        if not (isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise InputError("ANALYSIS_SCOPE_INVALID", "变更来源须给出当前 SHA-256")
        import hashlib
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise InputError("ANALYSIS_SOURCE_CHANGED", "变更来源当前摘要与声明不符")
        paths.append(relative)

    scanned = []
    for prefix, _ in SCOPES:
        base = root / prefix
        if not base.resolve().is_relative_to(root) or not base.is_dir():
            continue
        for path in sorted(base.rglob("*.json")):
            if len(scanned) >= MAX_FILES:
                break
            if path.resolve().is_relative_to(root):
                scanned.append(path)

    dependent = []
    gaps = []
    for relative in paths:
        hits = []
        for path in scanned:
            rel = path.relative_to(root).as_posix()
            kind = _kind(rel)
            if kind is None:
                continue
            value = _load(path)
            if value is None:
                continue
            if _mentions(value, relative):
                hits.append((kind, rel))
        if not hits:
            gaps.append(relative)
        for kind, rel in hits:
            if not any(row["kind"] == kind and row["path"] == rel for row in dependent):
                dependent.append({"kind": kind, "path": rel,
                                  "reasons": ["引用来源 " + relative],
                                  "binding": "FORMAL_BINDING_UNCHANGED"})
    # One-level co-source expansion: objects referenced by a dependent object join the scope.
    known = {row["path"] for row in dependent}
    for row in list(dependent):
        value = _load(root / row["path"])
        if value is None:
            continue
        for path in scanned:
            rel = path.relative_to(root).as_posix()
            if rel in known or _kind(rel) is None:
                continue
            if _mentions(value, rel):
                kind = _kind(rel)
                dependent.append({"kind": kind, "path": rel,
                                  "reasons": ["共源引用 " + row["path"]],
                                  "binding": "FORMAL_BINDING_UNCHANGED"})
                known.add(rel)
    dependent.sort(key=lambda row: (row["kind"], row["path"]))
    return {
        "schema": SCHEMA,
        "changed_sources": [{"path": relative, "sha256": next(
            (ref.get("sha256") for ref in changed if ref.get("path", "").replace("\\", "/") == relative), None)}
            for relative in paths],
        "dependent_objects": dependent,
        "review_scope": ["复查 " + row["kind"] + " " + row["path"] for row in dependent],
        "unmapped_gaps": gaps,
        "note": "分析层只圈复核范围；正式件版本绑定与失效链由既有绑定链独立判定，本报告不改 binding",
    }
