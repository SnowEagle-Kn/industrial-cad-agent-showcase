import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from cad_agent_showcase.governance.anonymize import RedactionError, anonymize
from cad_agent_showcase.governance.envelope import InputError
from cad_agent_showcase.governance.neutral_evidence import prepare_neutral_evidence


class AnonymizationTests(unittest.TestCase):
    def setUp(self):
        workspace = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.source = workspace / "source"
        self.source.mkdir()
        self.public = workspace / "public"

    def reference(self, name, data, *, kind="derived_record", token="record:SceneA", region=None):
        (self.source / name).write_bytes(data)
        return {
            "path": name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "locator": {"kind": kind, "token": token, "view_id": None, "region": region},
        }

    def candidate(self, *references):
        return {
            "schema": "wishcad.candidate.v1.1",
            "run_id": "SyntheticRun",
            "candidate_id": "DraftA",
            "author_session": "SyntheticAuthor",
            "role": "D1",
            "quality": [{"id": "Q1", "text": "Keep the D1 engineering label.", "window_id": "SyntheticWindow"}],
            "parameters": [{"parameter_id": "D1", "role": "interface", "value": 0, "source_ref": None}],
            "consumed_feature_ids": [],
            "decision_records": [],
            "critical_unknowns": [],
            "evidence_refs": {"layout": None, "artifacts": list(references)},
        }

    def prepare(self, candidate, **options):
        return prepare_neutral_evidence(candidate, self.source, self.public, "K01",
                                        candidate["run_id"], "r1", **options)

    def redact(self, candidate, prepared, **options):
        return anonymize(candidate, anonymous_id="K01", evidence_map=prepared["evidence_map"],
                         source_root=self.source, public_root=self.public, **options)

    def test_v10_preserves_engineering_roles_values_and_order(self):
        candidate = {
            "schema": "wishcad.candidate.v1.0",
            "author_session": "SyntheticLegacy",
            "role": "D1",
            "quality": [{"id": "Q1", "text": "D1 is evidence text."}, {"id": "Q2", "text": "Second."}],
            "parameters": [{"parameter_id": "D1", "value": 0, "unit": "mm", "role": "interface",
                            "designer_session": "SyntheticNested", "source_ref": "demo-note.txt"}],
            "mechanism_signature": {"basis": {"role": "engineering", "details": []}},
        }
        original = copy.deepcopy(candidate)
        result = anonymize(candidate, anonymous_id="K02")
        packet = result["packet"]
        self.assertEqual(candidate, original)
        self.assertEqual(result["schema_version"], "wishcad.anonymize.v1.1")
        self.assertEqual(packet["candidate_id"], "K02")
        self.assertEqual(packet["quality"], original["quality"])
        self.assertEqual(packet["mechanism_signature"], original["mechanism_signature"])
        self.assertEqual(packet["parameters"], [{k: v for k, v in original["parameters"][0].items()
                                                if k != "designer_session"}])
        self.assertIsNone(packet["author_session"])
        self.assertNotIn("role", packet)
        self.assertTrue(all(check["pass"] for check in result["evidence_integrity"]))
        with self.assertRaises(RedactionError):
            anonymize({**candidate, "parameters": [{}]})

    def test_v11_rewrites_only_declared_json_and_text_reference_leaves(self):
        json_bytes = b'{"records":[{"record_id":"SceneA","note":"synthetic"}]}\n'
        text_bytes = b"synthetic criterion\nsecond line\n"
        record = self.reference("draft.json", json_bytes)
        note = self.reference("note.txt", text_bytes, kind="text_lines", token="lines:1-2")
        candidate = self.candidate(record, note)
        candidate["parameters"][0]["source_ref"] = note
        candidate["decision_records"] = [{
            "decision_id": "DecisionA", "decision": "Review the example.",
            "requirement_ids": [], "feature_ids": [], "source_refs": [record], "costs": [],
            "mechanism": "Synthetic observation.", "failure_conditions": ["Example unavailable."],
            "verification": {"method": "Read back", "criterion": None, "source_refs": [note]},
        }]
        original = copy.deepcopy(candidate)
        prepared = self.prepare(candidate)
        result = self.redact(candidate, prepared)
        packet = result["packet"]
        self.assertEqual(candidate, original)
        self.assertEqual(result["schema_version"], "wishcad.anonymize.v1.2")
        self.assertEqual(packet["candidate_id"], "K01")
        self.assertIsNone(packet["author_session"])
        self.assertNotIn("role", packet)
        self.assertEqual(packet["quality"], [{"id": "Q1", "text": "Keep the D1 engineering label."}])
        self.assertEqual(packet["parameters"][0]["role"], "interface")
        self.assertEqual(packet["parameters"][0]["value"], 0)
        self.assertEqual(len(prepared["public_files"]), 2)
        public_record, public_note = packet["evidence_refs"]["artifacts"]
        self.assertEqual(packet["parameters"][0]["source_ref"], public_note)
        self.assertEqual(packet["decision_records"][0]["source_refs"], [public_record])
        self.assertEqual((self.public / public_record["path"]).read_bytes(), json_bytes)
        self.assertEqual((self.public / public_note["path"]).read_bytes(), text_bytes)
        self.assertTrue(all(check["pass"] for check in result["evidence_integrity"]))
        for secret in ("SyntheticAuthor", "SyntheticWindow", "private_source", "evidence_map", "draft.json"):
            self.assertNotIn(secret, json.dumps(result))

    def test_v11_requires_exact_map_and_current_distinct_copies(self):
        candidate = self.candidate(self.reference("draft.json", b'{"id":"SceneA"}'))
        with self.assertRaises(RedactionError):
            anonymize(candidate, anonymous_id="K01")
        prepared = self.prepare(candidate)
        missing = copy.deepcopy(prepared)
        missing["evidence_map"]["mappings"].clear()
        with self.assertRaisesRegex(InputError, "does not cover"):
            self.redact(candidate, missing)
        destination = self.public / prepared["public_files"][0]
        destination.write_bytes(b'{"id":"Other"}')
        with self.assertRaisesRegex(InputError, "digest"):
            self.redact(candidate, prepared)
        destination.unlink()
        os.link(self.source / "draft.json", destination)
        with self.assertRaisesRegex(InputError, "distinct byte-identical copy"):
            self.redact(candidate, prepared)

    def test_v11_rejects_noncanonical_paths_and_unreachable_locators(self):
        source = self.reference("draft.json", b'{"id":"SceneA"}')
        for path in ("../draft.json", "nested//draft.json", "nested/./draft.json", "NUL.json",
                     "draft.json ", "volume:/draft.json"):
            with self.subTest(path=path), self.assertRaises(InputError):
                self.prepare(self.candidate({**source, "path": path}))
        source["locator"]["token"] = "record:Missing"
        with self.assertRaisesRegex(InputError, "not unique and reachable"):
            self.prepare(self.candidate(source))

    def test_v11_rejects_escaped_identity_in_json(self):
        data = br'{"id":"SceneA","\u0053yntheticAuthor":"metadata"}'
        with self.assertRaisesRegex(InputError, "escaped author/session identity"):
            self.prepare(self.candidate(self.reference("draft.json", data)))
        self.assertFalse(self.public.exists())

    def test_v11_delegates_opaque_media_and_propagates_rejection(self):
        data = b"\x89PNG\r\n\x1a\nsynthetic port test bytes"
        ref = self.reference(
            "example.png", data, kind="image_region", token="image:ViewA",
            region={"x": 0, "y": 0, "width": 1, "height": 1, "unit": "normalized"},
        )
        candidate = self.candidate(ref)
        with self.assertRaises(InputError) as denied:
            self.prepare(candidate)
        self.assertEqual(denied.exception.code, "CORE_CAPABILITY_HIDDEN_IN_PUBLIC_REPO")
        self.assertFalse(self.public.exists())

        inspected = []

        def inspect(path, payload, locator):
            self.assertEqual(payload, data)
            self.assertEqual(locator, ref["locator"])
            inspected.append(path)

        prepared = self.prepare(candidate, media_inspector=inspect)
        inspected.clear()
        result = self.redact(candidate, prepared, media_inspector=inspect)
        self.assertEqual(result["status"], "REDACTED")
        self.assertEqual(inspected, [self.source / "example.png", self.public / prepared["public_files"][0]])

        class RefusedByPort(RuntimeError):
            pass

        def reject(path, payload, locator):
            raise RefusedByPort("fixture outside allowlist")

        with self.assertRaisesRegex(RefusedByPort, "outside allowlist"):
            self.redact(candidate, prepared, media_inspector=reject)


if __name__ == "__main__":
    unittest.main()
