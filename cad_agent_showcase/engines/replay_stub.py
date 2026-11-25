"""Serve declared replay results from pinned synthetic assets."""

import copy
import hashlib
import json
import math
import os
from pathlib import Path

from ..contracts import (CODE_ARTIFACT_HASH_MISMATCH, CODE_ARTIFACT_MISSING,
                         CODE_FIXTURE_INTEGRITY, CODE_FIXTURE_NOT_FOUND,
                         CODE_MISSING_PARAMETERS, CODE_PARAMETER_OUT_OF_RANGE,
                         CODE_UNSUPPORTED_FORMAT, CODE_UNSUPPORTED_REPLAY_INPUT,
                         EVIDENCE_REPLAY, WATERMARK, FixtureIntegrityError,
                         ReplayEngineFailure, ReplayRejection)
from ..ports.core_engine import CoreBoundaryError, CoreEnginePort
from ..util import canonical_sha256

CONCEPT_FIXTURE_DIR = "concept_to_manufacturing"
DRAWING_FIXTURE_DIR = "drawing_to_deliverable"
SUPPORTED_DRAWING_EXTENSIONS = (".dxf",)
_DRAWINGS = ("plate-demo.dxf", "plate-demo-mutated.dxf")
_REPO_ROOT = Path(__file__).absolute().parents[2]
_EVIDENCE_IMAGE = "examples/concept_to_manufacturing/concept-preview-3d.png"
_EVIDENCE_LOCATOR = {"kind": "image_region", "token": "region:full",
                     "view_id": None, "region": None}
_BOOKLET = "fixtures/delivery/booklet.pdf"

# Each key binds the package-relative identity to its exact bytes.
_FIXED_ASSETS = {
    "examples/concept_to_manufacturing/concept-preview-2d.svg": "0163e25ef404a59026641af3d8e0a1a8322c1d821e4259cf7f6bd3dff3f46154",
    "examples/concept_to_manufacturing/concept-preview-3d.png": "10710eb5e8bf00a438bd212883156dddf0e0326dfb53b99ad2079e1bba32c752",
    "examples/drawing_to_deliverable/deliverable-preview-2d.svg": "7d6a6607cacb35d6c77e3988f7ce6752a472b6c04672351d7fd391a2f1b8c3b4",
    "examples/drawing_to_deliverable/deliverable-preview-3d.png": "888319102b59bff10448d22b4b8836c851b793e659247899ea150d1226b5061c",
    "fixtures/concept_to_manufacturing/events-accept.json": "38f0c3de276292276f455456fca03c804a8d060125bf4e710180d314643894c9",
    "fixtures/concept_to_manufacturing/events-reject.json": "2308523e70adc99e645976b56c87c0e86b358db9b6af074f6fee859cbbdcff2c",
    "fixtures/concept_to_manufacturing/expected.json": "0a7a95e821b95b71848571d1fe248365b10c2d2595791f70966b86ef514c27b5",
    "fixtures/concept_to_manufacturing/input.json": "4aae016429e898308ebe18b759692dd814221fddfd58a4edad47f0b6faebf049",
    "fixtures/concept_to_manufacturing/parameters-continued.json": "aded1fea3d9f0b13bc2a18a10291f174194284823fc34498aa0515e98655233c",
    "fixtures/concept_to_manufacturing/parameters-missing.json": "f25b31ca449f3e16e9204955b80177e78c526450cf3e4f2ad689bcaaa5b4809a",
    "fixtures/concept_to_manufacturing/parameters-mutated.json": "52ee53edaa3568a8483ce4b3c86a6781977287d3ae32f37bceecb1afe9794a5b",
    "fixtures/concept_to_manufacturing/parameters-out-of-range.json": "18dbb8906d8f5e7106a504b93d381a3921bbefe64bf8882ef360ae1b64fb67e4",
    "fixtures/concept_to_manufacturing/parameters.json": "9119dbf83d0dbff6c2b96ca734fbbefe0fc1eecc6e09f9c0e00198dbc4cc6820",
    "fixtures/delivery/booklet.pdf": "980ba90452149499f8cc164f93cbae84ada0cea14ee848d10bd94fc5f35badd4",
    "fixtures/drawing_to_deliverable/expected.json": "db9043b7243f033a8a08220eacfdaa47750240e0379c79fadc2cced1bf717311",
    "fixtures/drawing_to_deliverable/object-summaries.json": "97f44ef72be071561615d380ba97a6befe8f40ea8ae5f8c4d715750081306f15",
    "fixtures/drawing_to_deliverable/parameters.json": "2b4dc35699a4ae8e4433f632bd79c55aa455da1760c55dbf10c94992e7b5868a",
    "fixtures/drawing_to_deliverable/plate-demo-mutated.dxf": "ca25d62cc7c1211c62ba656bcb8b2eee0670b30f65fc86b58d9e17a312f4c6e7",
    "fixtures/drawing_to_deliverable/plate-demo.dxf": "618f471a0c9db1400efc90547c51b7138b591623730be870fd0597c305195c32",
    "fixtures/evaluation/observation.json": "686c39ef612ea0bc56441c88cbbfaf3a6720aa41abdc27e9404904287db6163f",
    "fixtures/evaluation/session.json": "7600295297683d7a887b2654bb973cb1161d2876d23b74f1a0dc49441ff33875",
    "fixtures/gates/saved-events.json": "92c76b083259e913d5ae3ab41f3ae13f94c13e945cbeb0f790ce80f1f3f7b0c6",
    "fixtures/gates/scenarios.json": "fb6bf10e209ebf913e2fdfa940e5d92fc1f47e7dcfb15ad25d06b63bfae66e08",
}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _linked(path):
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & 0x400)  # Windows reparse point


def _leaf_name(value):
    return (isinstance(value, str) and value not in ("", ".", "..")
            and not any(character in value for character in "/\\:\0"))


def _canonical_matches(left, right):
    try:
        return canonical_sha256(left) == canonical_sha256(right)
    except (TypeError, ValueError):
        return False


class ReplayStubEngine(CoreEnginePort):
    # Preserve the v1 envelope and manifest engine string.
    name = "ReplayEngine"
    mode = "replay"

    def __init__(self, repo_root=None, fixture_root=None, fail=False):
        self.repo_root = _REPO_ROOT
        self.fixture_root = self.repo_root / "fixtures"
        if (repo_root is not None and Path(repo_root).absolute() != self.repo_root
                or fixture_root is not None and Path(fixture_root).absolute() != self.fixture_root):
            raise CoreBoundaryError("Use the fixture directory of this repository checkout.")
        self.fail = bool(fail)

    def _fixed_bytes(self, path):
        path = Path(path).absolute()
        if not path.is_relative_to(self.repo_root):
            raise CoreBoundaryError()
        relative = path.relative_to(self.repo_root).as_posix()
        expected = _FIXED_ASSETS.get(relative)
        if expected is None:
            raise CoreBoundaryError("This file identity is outside the fixed replay set.")
        try:
            for component in (path, *path.parents):
                if _linked(component):
                    raise CoreBoundaryError("Replay assets may not use symlinks or junctions.")
                if component == self.repo_root:
                    break
            if not path.is_file():
                raise FixtureIntegrityError(CODE_FIXTURE_NOT_FOUND, relative)
            data = path.read_bytes()
        except FileNotFoundError as exc:
            raise FixtureIntegrityError(CODE_FIXTURE_NOT_FOUND, relative) from exc
        except OSError as exc:
            raise FixtureIntegrityError(CODE_FIXTURE_INTEGRITY, relative) from exc
        if _sha(data) != expected:
            raise FixtureIntegrityError(CODE_FIXTURE_INTEGRITY, relative)
        return data

    def read_fixture_bytes(self, group, name):
        if not _leaf_name(group) or not _leaf_name(name):
            raise CoreBoundaryError("A replay fixture requires its declared group and basename.")
        return self._fixed_bytes(self.fixture_root / group / name)

    def _read(self, group, name):
        return json.loads(self.read_fixture_bytes(group, name))

    def verify_fixed_assets(self):
        for relative in _FIXED_ASSETS:
            self._fixed_bytes(self.repo_root / relative)
        return len(_FIXED_ASSETS)

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

    def inspect_input(self, record, name=None):
        """Dispatch declared inputs through the same fixed fixture boundary."""
        kind = record.get("kind") if isinstance(record, dict) else None
        if kind == "concept":
            return self.inspect_concept_input(record)
        if kind == "drawing":
            return self.inspect_drawing(
                name or record.get("file") or record.get("path") or "plate-demo.dxf")
        raise ReplayRejection(CODE_UNSUPPORTED_FORMAT,
                              "Unsupported input record: %r" % (kind,))

    def inspect_concept_input(self, payload):
        expected = self.concept_expected()
        if not _canonical_matches(payload, self.load_concept_input()):
            raise CoreBoundaryError("Concept input is outside the fixed replay set.",
                                    code=CODE_UNSUPPORTED_REPLAY_INPUT)
        return {"input_digest": self.concept_input_digest(payload), "expected": expected}

    def run_cognition_gate(self, expected):
        fixed = self.concept_expected()
        if not _canonical_matches(expected, fixed):
            raise CoreBoundaryError("Cognition requires the fixed concept replay contract.")
        return copy.deepcopy(fixed["candidates"])

    def build_concept(self, expected):
        return self.run_cognition_gate(expected)

    def solve_parameter_bridge(self, expected, parameters):
        fixed = next((contract for contract in (self.concept_expected(), self.drawing_expected())
                      if _canonical_matches(expected, contract)), None)
        if fixed is None or not isinstance(parameters, dict):
            raise CoreBoundaryError("Parameter resolution requires a fixed replay contract.")
        rows = parameters.get("parameters", [])
        if not isinstance(rows, list):
            raise CoreBoundaryError("Parameter rows must belong to a fixed replay fixture.")
        supplied = {item["parameter_id"]: item for item in rows
                    if isinstance(item, dict) and isinstance(item.get("parameter_id"), str)}
        missing = [name for name in fixed["required_parameters"]
                   if name not in supplied or supplied[name].get("value") in (None, "")]
        if missing:
            raise ReplayRejection(CODE_MISSING_PARAMETERS,
                                  "Required demo parameters are missing.",
                                  {"missing_parameters": missing})
        for name, (low, high) in fixed.get("parameter_bounds", {}).items():
            value = supplied.get(name, {}).get("value")
            if name in supplied and (type(value) not in (int, float) or not low <= value <= high):
                raise ReplayRejection(CODE_PARAMETER_OUT_OF_RANGE,
                                      "Demo parameter falls outside the fixture range.",
                                      {"parameter_id": name, "bounds": [low, high],
                                       "value": value if type(value) is not float or math.isfinite(value) else None})
        try:
            digest = self.parameter_digest(parameters)
        except (ValueError, TypeError) as exc:
            raise CoreBoundaryError("Parameter set is outside the fixed replay set.") from exc
        if digest not in fixed["allowed_parameter_digests"]:
            raise CoreBoundaryError("Parameter set is outside the fixed replay set.",
                                    code=CODE_UNSUPPORTED_REPLAY_INPUT,
                                    data={"parameters_digest": digest})
        return {"parameters_digest": digest}

    def resolve_parameters(self, expected, payload):
        return self.solve_parameter_bridge(expected, payload)

    def inspect_drawing_source(self, path):
        source = Path(path).absolute()
        if source.parent != self.fixture_root / DRAWING_FIXTURE_DIR or source.name not in _DRAWINGS:
            raise CoreBoundaryError("Drawing sources must use a fixed synthetic fixture path.")
        digest = _sha(self._fixed_bytes(source))
        expected = self.drawing_expected()
        variant = expected["variants"][source.name]
        if digest != variant["file_sha256"] or digest not in expected["allowed_file_sha256"]:
            raise FixtureIntegrityError(CODE_FIXTURE_INTEGRITY, "Replay drawing digest mismatch.")
        summary = self._drawing_summary(source.name)
        if (summary["entities"] != variant["entities"]
                or summary["extents_mm"] != variant["extents_mm"]
                or [row["type"] for row in summary["unknown_entities"]] != variant["unknown_types"]):
            raise FixtureIntegrityError(CODE_FIXTURE_INTEGRITY, "Replay drawing summary mismatch.")
        return {"file": source.name, "file_sha256": digest, "format": "DXF",
                "object_summary": summary, "expected": expected}

    def _drawing_summary(self, name):
        summary = self._read(DRAWING_FIXTURE_DIR, "object-summaries.json")[name]
        # Keep the original Python summary types for legacy callers.
        for row in summary["lines"]:
            row["start"], row["end"] = tuple(row["start"]), tuple(row["end"])
        for row in summary["circles"]:
            row["center"] = tuple(row["center"])
        for row in summary["texts"]:
            row["position"] = tuple(row["position"])
        return summary

    def inspect_drawing(self, name):
        """Resolve the two historical logical fixture names."""
        name = os.fspath(name)
        if name == "unsupported.xyz":
            raise ReplayRejection(CODE_UNSUPPORTED_FORMAT, "Supported drawing extension: .dxf",
                                  {"file": name})
        if name in _DRAWINGS:
            return self.inspect_drawing_source(self.fixture_root / DRAWING_FIXTURE_DIR / name)
        return self.inspect_drawing_source(name)

    def construct_brep_and_measure(self, path):
        return self.inspect_drawing_source(path)["object_summary"]

    def _delivery_spec(self, proposed):
        for expected in (self.concept_expected(), self.drawing_expected()):
            if _canonical_matches(proposed, expected["deliverable"]):
                return expected["deliverable"]
        raise CoreBoundaryError("Delivery requires a fixed replay specification.")

    def render_concept_views(self, deliverable_spec):
        plan = self._delivery_spec(deliverable_spec)
        media = []
        for item in plan["media"]:
            source = self.repo_root / item["source"]
            data = self._fixed_bytes(source)
            media.append({"role": item["role"], "source": item["source"],
                          "filename": source.name, "source_path": str(source),
                          "sha256": _sha(data), "bytes": len(data),
                          "demo": True, "evidence_type": EVIDENCE_REPLAY})
        return media

    def emit_and_verify_sheets(self, deliverable_spec):
        if self.fail:
            raise ReplayEngineFailure("ENGINE_FAILURE", "Injected ReplayEngine failure.")
        spec = self._delivery_spec(deliverable_spec)
        return {"deliverable_id": spec["deliverable_id"],
                "media": self.render_concept_views(spec),
                "readback_spec": copy.deepcopy(spec["readback"]),
                "watermark": WATERMARK, "evidence_type": EVIDENCE_REPLAY}

    def emit_deliverable(self, *, deliverable_spec):
        return self.emit_and_verify_sheets(deliverable_spec)

    def copy_media(self, deliverable, out_dir):
        target_dir = Path(out_dir)
        artifacts = []
        for item in deliverable.get("media", []):
            if not isinstance(item, dict) or not isinstance(item.get("source"), str):
                raise CoreBoundaryError("Delivery media must reference a fixed synthetic asset.")
            source = self.repo_root / item["source"]
            if source.suffix not in (".svg", ".png") or not source.is_relative_to(
                    self.repo_root / "examples"):
                raise CoreBoundaryError("Delivery media must reference a fixed synthetic image.")
            data = self._fixed_bytes(source)
            if item.get("sha256") != _sha(data) or item.get("filename") != source.name:
                raise FixtureIntegrityError(CODE_ARTIFACT_HASH_MISMATCH, source.name)
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / source.name
            if (target.exists() or target.is_symlink()) and _linked(target):
                raise FixtureIntegrityError(CODE_FIXTURE_INTEGRITY, source.name)
            target.write_bytes(data)
            artifacts.append({"role": item["role"], "path": source.name,
                              "sha256": _sha(data), "bytes": len(data), "demo": True,
                              "evidence_type": EVIDENCE_REPLAY})
        return artifacts

    def readback(self, manifest, out_dir):
        """Verify artifact and document bytes through their delivery manifest."""
        verified = {}
        for section in ("artifacts", "documents"):
            names = []
            for item in manifest.get(section, []):
                name = item["path"]
                if not _leaf_name(name):
                    raise FixtureIntegrityError(CODE_FIXTURE_INTEGRITY, "Invalid delivery name.")
                path = Path(out_dir) / name
                if not path.is_file() or _linked(path):
                    raise FixtureIntegrityError(CODE_ARTIFACT_MISSING, name)
                if _sha(path.read_bytes()) != item["sha256"]:
                    raise FixtureIntegrityError(CODE_ARTIFACT_HASH_MISMATCH, name)
                names.append(name)
            verified[section] = names
        return {"verified": True, "artifact_count": len(verified["artifacts"]),
                "document_count": len(verified["documents"]), **verified,
                "note": "Artifact bytes were re-hashed from the delivery directory."}

    def replay_booklet(self):
        return self._fixed_bytes(self.repo_root / _BOOKLET)

    def inspect_evidence_media(self, path, data, locator):
        source = Path(path).absolute()
        if (source != self.repo_root / _EVIDENCE_IMAGE or locator != _EVIDENCE_LOCATOR
                or type(data) is not bytes):
            raise CoreBoundaryError("Media location is outside the fixed replay set.")
        try:
            approved = self._fixed_bytes(source)
        except FixtureIntegrityError as exc:
            raise CoreBoundaryError("The fixed media location could not be verified.") from exc
        if data != approved:
            raise CoreBoundaryError("Media location does not bind the fixed replay bytes.")


def parse_dxf_text(text):
    """Resolve the exact historical fixture contents to their recorded summary."""
    if not isinstance(text, str):
        raise CoreBoundaryError("The legacy replay lookup requires text.")
    engine = ReplayStubEngine()
    for name in _DRAWINGS:
        source = engine.fixture_root / DRAWING_FIXTURE_DIR / name
        if engine._fixed_bytes(source).decode("utf-8-sig") == text:
            return engine._drawing_summary(name)
    raise CoreBoundaryError("The legacy replay lookup only accepts the two exact fixture texts.")
