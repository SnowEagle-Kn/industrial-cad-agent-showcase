# -*- coding: utf-8 -*-
import ast
import hashlib
import json
import os
import sys
import tempfile
import unittest

from tests.support import FIXTURES, ROOT, assert_no_forbidden, run_cli


def _read_json(path):
    with open(path, "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def _read_text(path):
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8")


class ReplayOutputTests(unittest.TestCase):
    def test_concept_delivery_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "concept")
            code, envelope, stdout, stderr = run_cli(
                ["demo", "concept", "--replay", "--out", out])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(envelope["status"], "OK")
            self.assertEqual(envelope["evidence_type"], "replay")
            self.assertEqual(envelope["engine"], "ReplayEngine")
            self.assertFalse(envelope["manufacturing_release"])
            self.assertFalse(envelope["engineering_approval"])
            self.assertFalse(envelope["production_approved"])
            self.assertFalse(envelope["verified_truth"])
            manifest_path = os.path.join(out, "manifest.json")
            self.assertTrue(os.path.isfile(manifest_path))
            manifest = _read_json(manifest_path)
            self.assertTrue(manifest["demo"])
            self.assertTrue(manifest["replay"])
            self.assertEqual(manifest["evidence_type"], "replay")
            self.assertIn("DEMO / REPLAY", manifest["watermark"])
            self.assertFalse(manifest["manufacturing_release"])
            self.assertFalse(manifest["engineering_approval"])
            self.assertEqual(manifest["revision"], 2)
            for artifact in manifest["artifacts"]:
                path = os.path.join(out, artifact["path"])
                self.assertTrue(os.path.isfile(path), artifact["path"])
                self.assertEqual(_sha256(path), artifact["sha256"])
                self.assertTrue(artifact["demo"])
            for document in manifest["documents"]:
                path = os.path.join(out, document["path"])
                self.assertTrue(os.path.isfile(path), document["path"])
                self.assertEqual(_sha256(path), document["sha256"])
            checklist = _read_text(os.path.join(out, "DELIVERY-CHECKLIST.md"))
            self.assertIn("DEMO / REPLAY", checklist)
            self.assertIn("NOT FOR MANUFACTURING", checklist)
            svg = _read_text(os.path.join(out, "concept-preview-2d.svg"))
            self.assertIn("DEMO / REPLAY", svg)
            with open(os.path.join(out, "concept-preview-3d.png"), "rb") as handle:
                self.assertIn(b"DEMO / REPLAY", handle.read())
            parameters = _read_json(os.path.join(out, "parameters-summary.json"))
            self.assertEqual(len(parameters["parameters"]), 6)
            for item in parameters["parameters"]:
                self.assertEqual(item["source"], "USER_INPUT")
                self.assertFalse(item["verified"])
            readback = _read_json(os.path.join(out, "readback.json"))["readback"]
            self.assertEqual(readback["counts"]["holes"], 2)
            self.assertIn("not_verified", readback)
            assert_no_forbidden(self, stdout)
            for name in os.listdir(out):
                if name.endswith((".json", ".md", ".svg")):
                    assert_no_forbidden(self, _read_text(os.path.join(out, name)))

    def test_drawing_delivery_and_mutation_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "drawing")
            code, envelope, stdout, stderr = run_cli(
                ["demo", "drawing", "--replay", "--out", out])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(envelope["entry"], "MANUFACTURING_CAD")
            data = envelope["data"]
            self.assertEqual(data["drawing"]["entities"]["CIRCLE"], 4)
            self.assertEqual(data["drawing"]["unknown_objects"], ["SPLINE"])
            self.assertEqual(data["drawing"]["extents_mm"]["width"], 120.0)
            mutation = data["mutation_check"]
            self.assertTrue(mutation["input_digest_changed"])
            self.assertEqual(mutation["invalidation"]["state"], "CONFIRMATION_INVALIDATED")
            self.assertIn("input_digest", mutation["invalidation"]["changed_fields"])
            self.assertFalse(mutation["old_confirmation_delivery"]["allowed"])
            manifest = _read_json(os.path.join(out, "manifest.json"))
            self.assertEqual(manifest["revision"], 2)
            self.assertEqual(manifest["readback"]["geometry"]["circles"], 4)
            assert_no_forbidden(self, stdout)

    def test_package_imports_are_standard_library_only(self):
        allowed = set(sys.stdlib_module_names) | {"cad_agent_showcase", "tests"}
        for directory, _, names in os.walk(ROOT):
            if "__pycache__" in directory:
                continue
            for name in names:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(directory, name)
                with open(path, encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=path)
                for node in ast.walk(tree):
                    modules = []
                    if isinstance(node, ast.Import):
                        modules = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                        modules = [node.module]
                    for module in modules:
                        top = module.split(".")[0]
                        self.assertIn(top, allowed,
                                      "%s imports non-stdlib module %s" % (path, module))


if __name__ == "__main__":
    unittest.main()
