"""Exact private evidence maps and byte-identical, controlled public copies."""

import copy
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

from .envelope import InputError
from .schema_runtime import decode_json, validate_projection, validate_schema

ANONYMOUS_IDS = tuple("K%02d" % index for index in range(1, 6))
NEW_SCHEMA = "wishcad.candidate.v1.1"
_TEXT_SUFFIXES = {".json", ".txt", ".md", ".csv"}
_MEDIA_SUFFIXES = {".pdf", ".dxf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
_MEDIA_KINDS = {"dxf_entity", "pdf_page", "image_region"}


def _reject(detail):
    raise InputError("NEUTRAL_EVIDENCE_INVALID", detail)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _same(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same(value, right[key]) for key, value in left.items())
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same(a, b) for a, b in zip(left, right))
    return left == right


def _path(root, relative):
    if not isinstance(relative, str) or not relative or re.search(
            r'[\\:#<>|"?*\x00-\x1f]', relative):
        _reject("Evidence path must be a controlled relative POSIX path")
    parts = relative.split("/")
    reserved = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)
    if any(part in ("", ".", "..") or part.rstrip(" .") != part
           or reserved.match(part) for part in parts):
        _reject("Evidence path contains a noncanonical component")
    base = Path(root).absolute()
    target = base.joinpath(*parts)
    for probe in (target, *target.parents):
        if probe.exists() or probe.is_symlink():
            attrs = getattr(probe.lstat(), "st_file_attributes", 0)
            if probe.is_symlink() or attrs & 0x400:
                _reject("Evidence paths cannot use symlinks or reparse points")
    if not target.resolve().is_relative_to(base.resolve()):
        _reject("Evidence path escapes its root")
    return target


def _read(root, ref):
    path = _path(root, ref["path"])
    if not path.is_file():
        _reject("Referenced evidence file is missing: " + ref["path"])
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != ref["sha256"]:
        _reject("Evidence digest does not bind current bytes: " + ref["path"])
    return path, data


def _records(node, keys, identity):
    if isinstance(node, dict):
        if any(node.get(key) == identity for key in keys):
            yield node
        for value in node.values():
            yield from _records(value, keys, identity)
    elif isinstance(node, list):
        for value in node:
            yield from _records(value, keys, identity)


def _is_media(path, data, kind):
    if kind in _MEDIA_KINDS or path.suffix.lower() not in _TEXT_SUFFIXES or b"%PDF-" in data:
        return True
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError:
        return True
    return any(ord(character) < 32 and character not in "\t\r\n" for character in text)


def _inspect_media(path, data, locator, media_inspector):
    if media_inspector is None:
        raise InputError("CORE_CAPABILITY_HIDDEN_IN_PUBLIC_REPO",
                         "Media evidence requires the public core inspection port")
    # A port exception is propagated so orchestration retains the refusal code.
    if media_inspector(path, data, copy.deepcopy(locator)) is not None:
        _reject("Media inspector must return None on acceptance")


def _locatable(path, data, locator, adapter=False, *, media_inspector=None):
    """Check actual source locations; adapters describe layout/view carrier leaves."""
    kind, token = locator["kind"], locator["token"]
    if kind not in ("image_region", "pdf_page") and locator["region"] is not None:
        _reject("This locator kind does not declare a source region")
    if kind == "dxf_entity" and re.fullmatch(r"handle:[0-9a-fA-F]+", token) is None:
        _reject("Malformed DXF locator")
    if kind == "pdf_page" and re.fullmatch(r"page:[1-9][0-9]*", token) is None:
        _reject("Malformed PDF page locator")
    if kind == "image_region" and (re.fullmatch(r"image:[A-Za-z0-9_-]+", token) is None
                                    or locator["region"] is None):
        _reject("Image locator requires image:<ID> and an actual region")
    if _is_media(path, data, kind):
        _inspect_media(path, data, locator, media_inspector)
        return
    try:
        document = decode_json(data) if path.suffix.lower() == ".json" else None
        if adapter:
            return
        if kind == "text_lines" or (kind == "user_event" and token.startswith("line:")):
            pattern = r"lines:([1-9][0-9]*)-([1-9][0-9]*)" if kind == "text_lines" else r"line:([1-9][0-9]*)"
            match = re.fullmatch(pattern, token)
            if match is None:
                _reject("Malformed source line locator")
            start = int(match[1])
            end = int(match[2]) if kind == "text_lines" else start
            if not 1 <= start <= end <= len(data.decode("utf-8-sig").splitlines()):
                _reject("Source line locator is not reachable")
        elif kind == "user_event":
            if not re.fullmatch(r"event:[A-Za-z0-9_-]+", token):
                _reject("Malformed saved-event locator")
            if document is None:
                document = decode_json(data)
            records = list(_records(document, ("event_id",), token[6:]))
            if len(records) != 1:
                _reject("Saved-event locator is not unique and reachable")
        elif kind == "derived_record":
            match = re.fullmatch(r"(record:|files/)([A-Za-z][A-Za-z0-9_-]*)", token)
            if match is None:
                _reject("Malformed derived-record locator")
            if document is None:
                document = decode_json(data)
            keys = ("source_id",) if match[1] == "files/" else ("record_id", "id", "decision_id")
            scope = document.get("files", []) if match[1] == "files/" and isinstance(document, dict) else document
            if len(list(_records(scope, keys, match[2]))) != 1:
                _reject("Derived record is not unique and reachable")
        else:
            _reject("Unsupported source locator")
    except InputError:
        raise
    except Exception as exc:
        _reject("Source locator cannot be verified: " + str(exc))


def _adapter(path, sha256, name, view_id=None):
    # Layout/view carriers have no locator leaf; record locators identify them.
    return {"path": path, "sha256": sha256, "locator": {
        "kind": "derived_record", "token": "record:" + name,
        "view_id": view_id, "region": None}}


def reference_leaves(candidate):
    """Enumerate only declared source_ref, layout_ref and view path leaves."""
    found = []

    def source(ref, pointer):
        if isinstance(ref, dict):
            found.append((pointer + ("path",), copy.deepcopy(ref)))

    for index, parameter in enumerate(candidate.get("parameters") or []):
        source(parameter.get("source_ref"), ("parameters", index, "source_ref"))
    for index, record in enumerate(candidate["decision_records"]):
        prefix = ("decision_records", index)
        for number, ref in enumerate(record["source_refs"]):
            source(ref, prefix + ("source_refs", number))
        for number, cost in enumerate(record["costs"]):
            for offset, ref in enumerate(cost["source_refs"]):
                source(ref, prefix + ("costs", number, "source_refs", offset))
        for number, ref in enumerate(record["verification"]["source_refs"]):
            source(ref, prefix + ("verification", "source_refs", number))
    for index, unknown in enumerate(candidate["critical_unknowns"]):
        for number, ref in enumerate(unknown["source_refs"]):
            source(ref, ("critical_unknowns", index, "source_refs", number))
    evidence = candidate["evidence_refs"]
    for number, ref in enumerate(evidence["artifacts"]):
        source(ref, ("evidence_refs", "artifacts", number))
    layout = evidence["layout"]
    if layout is not None:
        prefix = ("evidence_refs", "layout")
        found.append((prefix + ("layout_ref",), _adapter(
            layout["layout_ref"], layout["sha256"], "layout")))
        for index, view in enumerate(layout["view_refs"]):
            found.append((prefix + ("view_refs", index, "path"), _adapter(
                view["path"], view["sha256"], "view-" + view["view_id"], view["view_id"])))
        for number, ref in enumerate(layout["source_refs"]):
            source(ref, prefix + ("source_refs", number))
    return found


def _set(node, pointer, value):
    for part in pointer[:-1]:
        node = node[part]
    node[pointer[-1]] = value


def _secrets(candidate):
    values = []
    keys = {"author_session", "session_id", "parent_session", "started_by",
            "startedBy", "author_name", "chat_ref", "source_executor_ref",
            "author_chat_ref", "designer_session", "design_session", "seat_id",
            "seat_label", "author_id", "author_ref", "author_chat", "window_id",
            "session_ref", "private_map_ref", "identity_map_ref"}

    def walk(node, path=()):
        if isinstance(node, dict):
            for key, value in node.items():
                identity = key in keys or (not path and key in ("author", "designer", "session"))
                identity = identity or (path[:1] == ("quality",) and key in ("author", "session"))
                if identity and isinstance(value, str) and value and not re.fullmatch(
                        r"D[0-4]|P|J0", value):
                    values.append(value)
                walk(value, path + (key,))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path + (index,))
    walk(candidate)
    return tuple(set(values))



def _private_path(text):
    value = text.replace("\\", "/").casefold()
    return bool(re.search(r"""(?:^|[/\s"'])(?:[-_.a-z]*私有|coordinator-private)(?:/|[\s"']|$)""", value))


def _safe_bytes(data, secrets):
    """Scan exact public bytes and decoded JSON leaves for known identity."""
    for secret in secrets:
        for encoding in ("utf-8", "utf-16-le", "utf-16-be"):
            if secret.encode(encoding) in data:
                _reject("Evidence contains known author/session identity")
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            text = data.decode(encoding)
        except UnicodeError:
            continue
        if any(secret in text for secret in secrets):
            _reject("Evidence contains encoded author/session identity")
        if _private_path(text):
            _reject("Private coordinator paths cannot be public evidence")
        try:
            document = decode_json(text.encode("utf-8"))
        except json.JSONDecodeError:
            continue
        except (ValueError, RecursionError) as exc:
            _reject("Invalid JSON evidence: " + str(exc))

        def inspect(node):
            if isinstance(node, dict):
                if node.get("schema") == "wishcad.neutral-evidence-map.v1":
                    _reject("Private evidence-map content cannot be public evidence")
                for key, value in node.items():
                    if key in ("author_session", "session_id", "author_chat_ref",
                               "designer_session", "design_session", "seat_id",
                               "seat_label", "window_id", "private_identity_map",
                               "identity_map", "identity_map_ref") and value not in (None, ""):
                        _reject("Evidence contains explicit private identity metadata")
                    inspect(key)
                    inspect(value)
            elif isinstance(node, list):
                for value in node:
                    inspect(value)
            elif isinstance(node, str):
                if any(secret in node for secret in secrets):
                    _reject("Evidence contains escaped author/session identity")
                if _private_path(node):
                    _reject("Private coordinator paths cannot be public evidence")
        inspect(document)
        break


def _public_path(anonymous_id, ref):
    evidence_id = "E" + hashlib.sha256(_canonical(ref).encode("utf-8")).hexdigest()
    extension = Path(ref["path"]).suffix.lower()
    if extension not in _TEXT_SUFFIXES | _MEDIA_SUFFIXES:
        extension = ".bin"
    return evidence_id, "evidence/" + anonymous_id + "/" + evidence_id + extension


def _unique_references(candidate):
    from .anonymize import _check_engineering_structure, _check_new_legacy_refs
    _check_engineering_structure(candidate)
    _check_new_legacy_refs(candidate)
    references = {}
    aliases = {}
    for pointer, ref in reference_leaves(candidate):
        key = _canonical(ref)
        alias = unicodedata.normalize("NFC", ref["path"]).casefold()
        if alias in aliases and aliases[alias] != ref["path"]:
            _reject("Evidence references contain path aliases")
        aliases[alias] = ref["path"]
        references.setdefault(key, (ref, []))[1].append(pointer)
    return references


def _is_adapter(pointers):
    return all(pointer[:2] == ("evidence_refs", "layout")
               and (pointer[-1] == "layout_ref" or "view_refs" in pointer)
               for pointer in pointers)


def apply_evidence_map(candidate, evidence_map, source_root, public_root,
                       anonymous_id=None, *, media_inspector=None):
    """Verify an exact private map against originals and reachable public bytes."""
    validate_projection("candidate", candidate)
    validate_schema("neutral-evidence-map", evidence_map)
    if source_root is None or public_root is None:
        _reject("Source and public roots are required for exact evidence verification")
    if "run_id" in candidate and candidate["run_id"] != evidence_map["run_id"]:
        _reject("Evidence map belongs to another run")
    references = _unique_references(candidate)
    mapped = copy.deepcopy(candidate)
    indexed = {}
    ids = set()
    public_paths = set()
    secrets = _secrets(candidate)
    for item in evidence_map["mappings"]:
        private = item["private_source"]
        public = item["public_evidence"]
        key = _canonical(private)
        if key in indexed or item["evidence_id"] in ids:
            _reject("Evidence IDs and private references must be unique")
        indexed[key] = item
        ids.add(item["evidence_id"])
        if key not in references:
            _reject("Evidence map contains an unreferenced private source")
        parts = public["path"].split("/")
        mapped_id = anonymous_id if anonymous_id is not None else (parts[1] if len(parts) == 3 else None)
        if mapped_id not in ANONYMOUS_IDS:
            _reject("Public evidence requires K01-K05")
        evidence_id, expected_path = _public_path(mapped_id, private)
        expected = copy.deepcopy(private)
        expected["path"] = expected_path
        if item["evidence_id"] != evidence_id or not _same(public, expected):
            _reject("Evidence mapping changes digest, locator, or controlled destination")
        if public["path"].casefold() in public_paths:
            _reject("Public evidence paths must be unique")
        public_paths.add(public["path"].casefold())
        original_path, original = _read(source_root, private)
        copy_path, actual = _read(public_root, public)
        if os.path.samefile(original_path, copy_path) or original != actual:
            _reject("Public evidence must be a distinct byte-identical copy")
        _safe_bytes(actual, secrets)
        adapter = _is_adapter(references[key][1])
        _locatable(original_path, original, private["locator"], adapter,
                   media_inspector=media_inspector)
        _locatable(copy_path, actual, public["locator"], adapter,
                   media_inspector=media_inspector)
        for pointer in references[key][1]:
            _set(mapped, pointer, public["path"])
    if set(indexed) != set(references):
        _reject("Evidence map does not cover the exact referenced source/locator set")
    return mapped


def prepare_neutral_evidence(candidate, run_root, packet_root, anonymous_id,
                             run_id, revision, *, media_inspector=None):
    """Return mapped candidate, private map, and packet-relative public files.

    All originals and destinations are checked before the first copy is written.
    The caller persists the map only in its coordinator-private directory.
    """
    validate_projection("candidate", candidate)
    if anonymous_id not in ANONYMOUS_IDS:
        _reject("Anonymous evidence ID must be K01-K05")
    if not isinstance(run_id, str) or not run_id or not isinstance(revision, str) or not revision:
        _reject("Evidence map run_id and revision must be nonempty strings")
    if "run_id" in candidate and candidate["run_id"] != run_id:
        _reject("Candidate and evidence map run IDs differ")
    references = _unique_references(candidate)
    evidence_map = {"schema": "wishcad.neutral-evidence-map.v1",
                    "run_id": run_id, "revision": revision,
                    "coordinator_only": True, "mappings": []}
    plan = []
    source_paths = set()
    secrets = _secrets(candidate)
    for ref, pointers in references.values():
        original_path, data = _read(run_root, ref)
        _safe_bytes(data, secrets)
        _locatable(original_path, data, ref["locator"], _is_adapter(pointers),
                   media_inspector=media_inspector)
        source_paths.add(os.path.normcase(str(original_path.resolve())).casefold())
        evidence_id, destination = _public_path(anonymous_id, ref)
        public = copy.deepcopy(ref)
        public["path"] = destination
        item = {"evidence_id": evidence_id, "private_source": copy.deepcopy(ref),
                "public_evidence": public, "content_transform": "NONE",
                "purpose": "Exact candidate evidence reference"}
        evidence_map["mappings"].append(item)
        target = _path(packet_root, destination)
        if target.exists() and (not target.is_file() or target.read_bytes() != data):
            _reject("Existing neutral destination contains different bytes")
        plan.append((ref, target, data))
    validate_schema("neutral-evidence-map", evidence_map)
    for ref, target, data in plan:
        if os.path.normcase(str(target.resolve())).casefold() in source_paths:
            _reject("Neutral output would overwrite input evidence")
        if _read(run_root, ref)[1] != data:
            _reject("Source evidence changed during preparation")
        _path(packet_root, target.relative_to(Path(packet_root).absolute()).as_posix())
        for parent in target.parents:
            if parent.exists() and not parent.is_dir():
                _reject("Neutral destination parent is not a directory")
    for ref, target, data in plan:
        target.parent.mkdir(parents=True, exist_ok=True)
        _path(packet_root, target.relative_to(Path(packet_root).absolute()).as_posix())
        try:
            with target.open("xb") as output:
                output.write(data)
        except FileExistsError:
            if not target.is_file() or target.read_bytes() != data:
                _reject("Neutral destination changed before copying")
    mapped = apply_evidence_map(candidate, evidence_map, run_root, packet_root, anonymous_id,
                                media_inspector=media_inspector)
    return {"candidate": mapped, "evidence_map": evidence_map,
            "public_files": [item["public_evidence"]["path"]
                             for item in evidence_map["mappings"]]}
