# -*- coding: utf-8 -*-
"""ReplayEngine: a fixed-fixture, standard-library-only demo engine.

The engine does not model CAD.  It validates declared fixture digests, parses
one simple self-made DXF dialect, and replays pre-generated DEMO media.  Any
input outside the declared fixture set is refused instead of silently
replaying an old result.
"""

import copy
import os
import shutil

from ..contracts import (CODE_ARTIFACT_HASH_MISMATCH, CODE_ARTIFACT_MISSING,
                         CODE_FIXTURE_INTEGRITY, CODE_FIXTURE_NOT_FOUND,
                         CODE_MISSING_PARAMETERS, CODE_PARAMETER_OUT_OF_RANGE,
                         CODE_UNSUPPORTED_FORMAT, CODE_UNSUPPORTED_REPLAY_INPUT,
                         EVIDENCE_REPLAY, WATERMARK, FixtureIntegrityError,
                         ReplayEngineFailure, ReplayRejection)
from ..util import canonical_sha256, file_sha256, read_json

CONCEPT_FIXTURE_DIR = "concept_to_manufacturing"
DRAWING_FIXTURE_DIR = "drawing_to_deliverable"
SUPPORTED_DRAWING_EXTENSIONS = (".dxf",)


def _extract_pairs(text):
    lines = text.splitlines()
    index = 0
    while index + 1 < len(lines):
        code_raw = lines[index].strip()
        if not code_raw:
            index += 1
            continue
        try:
            code = int(code_raw)
        except ValueError:
            raise FixtureIntegrityError(CODE_FIXTURE_INTEGRITY,
                                        "DXF group code is not an integer: %r" % code_raw)
        yield code, lines[index + 1].strip()
        index += 2


def parse_dxf_text(text):
    """Parse the small DXF subset used by the demo fixture.

    Recognised entities: LINE, CIRCLE, TEXT.  Anything else is reported as an
    unknown object and is *not* interpreted.
    """
    entities = []
    current = None
    in_entities = False
    section = None
    for code, value in _extract_pairs(text):
        if code == 0 and value == "SECTION":
            current = None
            section = None
            continue
        if code == 2 and section is None:
            section = value
            in_entities = value == "ENTITIES"
            continue
        if code == 0 and value == "ENDSEC":
            current = None
            in_entities = False
            section = None
            continue
        if not in_entities:
            continue
        if code == 0:
            current = {"type": value, "groups": []}
            entities.append(current)
            continue
        if current is not None:
            current["groups"].append((code, value))

    lines = []
    circles = []
    texts = []
    unknown = []
    for entity in entities:
        groups = {}
        for code, value in entity["groups"]:
            groups.setdefault(code, []).append(value)
        entity_type = entity["type"]
        if entity_type == "LINE":
            lines.append({
                "start": (float(groups[10][0]), float(groups[20][0])),
                "end": (float(groups[11][0]), float(groups[21][0])),
            })
        elif entity_type == "CIRCLE":
            circles.append({
                "center": (float(groups[10][0]), float(groups[20][0])),
                "radius": float(groups[40][0]),
            })
        elif entity_type == "TEXT":
            texts.append({
                "text": groups[1][0],
                "position": (float(groups[10][0]), float(groups[20][0])),
                "height": float(groups[40][0]) if 40 in groups else None,
            })
        else:
            unknown.append({
                "type": entity_type,
                "handle": groups.get(5, [None])[0],
            })
    xs = []
    ys = []
    for line in lines:
        xs.extend([line["start"][0], line["end"][0]])
        ys.extend([line["start"][1], line["end"][1]])
    for circle in circles:
        xs.extend([circle["center"][0] - circle["radius"],
                   circle["center"][0] + circle["radius"]])
        ys.extend([circle["center"][1] - circle["radius"],
                   circle["center"][1] + circle["radius"]])
    extents = None
    if xs and ys:
        extents = {"width": round(max(xs) - min(xs), 6),
                   "height": round(max(ys) - min(ys), 6)}
    return {
        "entities": {
            "LINE": len(lines),
            "CIRCLE": len(circles),
            "TEXT": len(texts),
        },
        "lines": lines,
        "circles": circles,
        "texts": texts,
        "unknown_entities": unknown,
        "extents_mm": extents,
    }


class ReplayEngine:
    name = "ReplayEngine"
    mode = "replay"

    def __init__(self, repo_root, fixture_root=None, fail=False):
        self.repo_root = os.path.abspath(repo_root)
        self.fixture_root = os.path.abspath(
            fixture_root or os.path.join(self.repo_root, "fixtures"))
        self.fail = bool(fail)

    # -- fixture loading -------------------------------------------------
    def _group_dir(self, group):
        return os.path.join(self.fixture_root, group)

    def _read(self, group, name):
        path = os.path.join(self._group_dir(group), name)
        if not os.path.isfile(path):
            raise FixtureIntegrityError(CODE_FIXTURE_NOT_FOUND, path)
        return read_json(path)

    def concept_expected(self):
        return self._read(CONCEPT_FIXTURE_DIR, "expected.json")

    def drawing_expected(self):
        return self._read(DRAWING_FIXTURE_DIR, "expected.json")

    def load_concept_input(self):
        return self._read(CONCEPT_FIXTURE_DIR, "input.json")

    def load_parameters(self, group, name):
        return self._read(group, name)

    def load_event(self, group, name):
        return self._read(group, name)

    def concept_input_digest(self, payload):
        return canonical_sha256(payload)

    def parameter_digest(self, payload):
        return canonical_sha256(payload)

    # -- public EnginePort surface ---------------------------------------
    def inspect_input(self, record, name=None):
        """Dispatch the two declared input kinds (public port method)."""
        kind = record.get("kind") if isinstance(record, dict) else None
        if kind == "concept":
            return self.inspect_concept_input(record)
        if kind == "drawing":
            return self.inspect_drawing(
                name or record.get("file") or record.get("path") or "plate-demo.dxf")
        raise ReplayRejection(CODE_UNSUPPORTED_FORMAT,
                              "unsupported input record: %r" % (kind,))

    def readback(self, manifest, out_dir):
        """Verify delivered artifact and document bytes against the manifest."""
        verified = []
        for artifact in manifest.get("artifacts", []):
            path = os.path.join(out_dir, artifact["path"])
            if not os.path.isfile(path):
                raise FixtureIntegrityError(CODE_ARTIFACT_MISSING, path)
            if file_sha256(path) != artifact["sha256"]:
                raise FixtureIntegrityError(CODE_ARTIFACT_HASH_MISMATCH, path)
            verified.append(artifact["path"])
        documents = []
        for document in manifest.get("documents", []):
            path = os.path.join(out_dir, document["path"])
            if not os.path.isfile(path):
                raise FixtureIntegrityError(CODE_ARTIFACT_MISSING, path)
            if file_sha256(path) != document["sha256"]:
                raise FixtureIntegrityError(CODE_ARTIFACT_HASH_MISMATCH, path)
            documents.append(document["path"])
        return {
            "verified": True,
            "artifact_count": len(verified),
            "document_count": len(documents),
            "artifacts": verified,
            "documents": documents,
            "note": "Artifact bytes were re-hashed from the delivery directory.",
        }

    # -- concept ---------------------------------------------------------
    def inspect_concept_input(self, payload):
        expected = self.concept_expected()
        digest = self.concept_input_digest(payload)
        if digest not in expected.get("allowed_input_digests", []):
            raise ReplayRejection(
                CODE_UNSUPPORTED_REPLAY_INPUT,
                "concept input is outside the declared replay fixture set",
                {"input_digest": digest})
        return {"input_digest": digest, "expected": expected}

    def build_concept(self, expected):
        if not expected.get("candidates"):
            raise FixtureIntegrityError(CODE_FIXTURE_INTEGRITY,
                                        "concept fixture declares no candidates")
        return copy.deepcopy(expected["candidates"])

    def resolve_parameters(self, expected, payload):
        required = expected.get("required_parameters", [])
        supplied = {}
        for item in payload.get("parameters", []):
            if isinstance(item, dict) and item.get("parameter_id"):
                supplied[item["parameter_id"]] = item
        missing = [parameter_id for parameter_id in required
                   if parameter_id not in supplied
                   or supplied[parameter_id].get("value") in (None, "")]
        if missing:
            raise ReplayRejection(
                CODE_MISSING_PARAMETERS,
                "required demo parameters are missing: %s" % ",".join(missing),
                {"missing_parameters": missing})
        for parameter_id, bounds in expected.get("parameter_bounds", {}).items():
            if parameter_id not in supplied:
                continue
            value = supplied[parameter_id].get("value")
            low, high = bounds
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ReplayRejection(
                    CODE_PARAMETER_OUT_OF_RANGE,
                    "%s must be a number within [%s, %s]" % (parameter_id, low, high),
                    {"parameter_id": parameter_id, "value": value})
            if value < low or value > high:
                raise ReplayRejection(
                    CODE_PARAMETER_OUT_OF_RANGE,
                    "%s=%r is outside [%s, %s]" % (parameter_id, value, low, high),
                    {"parameter_id": parameter_id, "value": value,
                     "bounds": [low, high]})
        digest = self.parameter_digest(payload)
        if digest not in expected.get("allowed_parameter_digests", []):
            raise ReplayRejection(
                CODE_UNSUPPORTED_REPLAY_INPUT,
                "parameter set is outside the declared replay fixture set",
                {"parameters_digest": digest})
        return {"parameters_digest": digest}

    # -- drawing ---------------------------------------------------------
    def inspect_drawing(self, name):
        expected = self.drawing_expected()
        extension = os.path.splitext(name)[1].lower()
        if extension not in SUPPORTED_DRAWING_EXTENSIONS:
            raise ReplayRejection(
                CODE_UNSUPPORTED_FORMAT,
                "supported drawing extension: %s" % ",".join(
                    SUPPORTED_DRAWING_EXTENSIONS),
                {"file": name})
        path = os.path.join(self._group_dir(DRAWING_FIXTURE_DIR), name)
        if not os.path.isfile(path):
            raise FixtureIntegrityError(CODE_FIXTURE_NOT_FOUND, path)
        digest = file_sha256(path)
        variant = expected.get("variants", {}).get(name)
        if variant is None or digest not in expected.get("allowed_file_sha256", []):
            raise ReplayRejection(
                CODE_UNSUPPORTED_REPLAY_INPUT,
                "drawing file bytes are outside the declared replay fixture set",
                {"file": name, "file_sha256": digest})
        if digest != variant.get("file_sha256"):
            raise FixtureIntegrityError(
                CODE_FIXTURE_INTEGRITY,
                "declared variant hash does not match file bytes: %s" % name)
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8-sig")
        parsed = parse_dxf_text(text)
        declared_entities = variant.get("entities", {})
        if parsed["entities"] != declared_entities:
            raise FixtureIntegrityError(
                CODE_FIXTURE_INTEGRITY,
                "entity counts differ from the declared fixture: %r != %r"
                % (parsed["entities"], declared_entities))
        declared_extents = variant.get("extents_mm")
        if parsed["extents_mm"] != declared_extents:
            raise FixtureIntegrityError(
                CODE_FIXTURE_INTEGRITY,
                "extents differ from the declared fixture: %r != %r"
                % (parsed["extents_mm"], declared_extents))
        unknown_types = [item["type"] for item in parsed["unknown_entities"]]
        if unknown_types != variant.get("unknown_types", []):
            raise FixtureIntegrityError(
                CODE_FIXTURE_INTEGRITY,
                "unknown entity list differs from the declared fixture")
        return {
            "file": name,
            "file_sha256": digest,
            "format": "DXF",
            "object_summary": parsed,
            "expected": expected,
        }

    # -- deliverable -----------------------------------------------------
    def _fail_if_injected(self):
        if self.fail:
            raise ReplayEngineFailure(
                "ENGINE_FAILURE",
                "Injected ReplayEngine failure for the U06 fault-injection check.")

    def emit_deliverable(self, *, deliverable_spec):
        """Return a deliverable payload; evidence.py writes the bundle."""
        self._fail_if_injected()
        media = []
        for item in deliverable_spec.get("media", []):
            source = os.path.join(self.repo_root, item["source"])
            if not os.path.isfile(source):
                raise FixtureIntegrityError(
                    CODE_FIXTURE_INTEGRITY,
                    "pre-generated DEMO media missing: %s" % item["source"])
            media.append({
                "role": item["role"],
                "source": item["source"],
                "filename": os.path.basename(source),
                "source_path": source,
                "sha256": file_sha256(source),
                "bytes": os.path.getsize(source),
                "demo": True,
                "evidence_type": EVIDENCE_REPLAY,
            })
        return {
            "deliverable_id": deliverable_spec["deliverable_id"],
            "media": media,
            "readback_spec": copy.deepcopy(deliverable_spec.get("readback", {})),
            "watermark": WATERMARK,
            "evidence_type": EVIDENCE_REPLAY,
        }

    def copy_media(self, deliverable, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        copied = []
        for item in deliverable["media"]:
            target = os.path.join(out_dir, item["filename"])
            shutil.copyfile(item["source_path"], target)
            if file_sha256(target) != item["sha256"]:
                raise FixtureIntegrityError(
                    CODE_FIXTURE_INTEGRITY,
                    "copied DEMO media hash mismatch: %s" % item["filename"])
            copied.append({
                "role": item["role"],
                "path": item["filename"],
                "sha256": item["sha256"],
                "bytes": item["bytes"],
                "demo": True,
                "evidence_type": EVIDENCE_REPLAY,
            })
        return copied
