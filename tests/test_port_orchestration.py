import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cad_agent_showcase import workflow
from cad_agent_showcase.contracts import (
    CODE_CORE_CAPABILITY_HIDDEN, ENGINEERING_FLAGS, FixtureIntegrityError)
from cad_agent_showcase.engines import ReplayEngine, ReplayStubEngine, parse_dxf_text
from cad_agent_showcase.orchestration.delivery_bundle import BUNDLE_FILES, verify_standard_bundle
from cad_agent_showcase.orchestration.gating import g2_binding, g2_gate
from cad_agent_showcase.orchestration.session_handoff import (
    acknowledge, prepare_judge_packet, prepare_outbox, record_send)
from cad_agent_showcase.ports import CoreBoundaryError, CoreEnginePort
from cad_agent_showcase.util import canonical_sha256
from tests.support import FIXTURES, ROOT, run_cli


class PublicBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.engine = ReplayStubEngine(ROOT, FIXTURES)
        self.workspace = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_fixed_drawing_requires_identity_and_digest(self):
        self.assertIs(ReplayEngine, ReplayStubEngine)
        self.assertEqual(len(CoreEnginePort.__abstractmethods__), 7)
        approved = Path(FIXTURES) / "drawing_to_deliverable" / "plate-demo.dxf"
        summary = self.engine.inspect_drawing_source(approved)["object_summary"]
        self.assertEqual(summary["entities"]["CIRCLE"], 4)
        self.assertEqual(parse_dxf_text(approved.read_text(encoding="utf-8")), summary)
        outside = self.workspace / approved.name
        outside.write_bytes(approved.read_bytes())
        with self.assertRaises(CoreBoundaryError):
            self.engine.construct_brep_and_measure(outside)
        with self.assertRaises(CoreBoundaryError):
            parse_dxf_text("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n")
        code, envelope, _, stderr = run_cli(
            ["demo", "drawing", "--replay", "--source", str(outside), "--out",
             str(self.workspace / "drawing-output")])
        self.assertEqual(code, 1, stderr)
        self.assertEqual(envelope["code"], CODE_CORE_CAPABILITY_HIDDEN)
        self.assertFalse((self.workspace / "drawing-output").exists())
        for flag in ENGINEERING_FLAGS:
            self.assertIs(envelope[flag], False)

    def test_external_binary_is_rejected_through_the_anonymous_packet(self):
        fixture = self.engine.load_event("evaluation", "session.json")
        reference_file = self.workspace / "outside.pdf"
        data = b"%PDF-1.7\nsynthetic unsupported media"
        reference_file.write_bytes(data)
        reference = {"path": reference_file.name, "sha256": hashlib.sha256(data).hexdigest(),
                     "locator": {"kind": "pdf_page", "token": "page:1", "view_id": None, "region": None}}
        candidates = {seat: {**fixture["candidate"], "candidate_id": seat,
                             "evidence_refs": {"layout": None, "artifacts": [reference]}}
                      for seat in fixture["designers"]}
        with self.assertRaises(CoreBoundaryError) as error:
            prepare_judge_packet(
                candidates, assignments=fixture["assignments"], run_id=fixture["run_id"],
                revision=fixture["revision"], source_root=self.workspace,
                public_root=self.workspace / "public", engine=self.engine)
        self.assertEqual(error.exception.code, CODE_CORE_CAPABILITY_HIDDEN)
        self.assertFalse((self.workspace / "public").exists())

    def test_media_callback_checks_the_declared_location(self):
        image = Path(ROOT) / "examples/concept_to_manufacturing/concept-preview-3d.png"
        data = image.read_bytes()
        locator = {"kind": "image_region", "token": "region:full", "view_id": None, "region": None}
        self.assertIsNone(self.engine.inspect_evidence_media(image, data, locator))
        outside = self.workspace / image.name
        outside.write_bytes(data)
        with self.assertRaises(CoreBoundaryError):
            self.engine.inspect_evidence_media(outside, data, locator)
        with self.assertRaises(CoreBoundaryError):
            self.engine.inspect_evidence_media(image, data, dict(locator, token="region:unlisted"))


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.engine = ReplayStubEngine(ROOT, FIXTURES)

    def run_replay(self, name):
        code, envelope, _, stderr = run_cli(
            ["demo", name, "--replay", "--out", str(self.workspace)])
        self.assertEqual(code, 0, stderr or envelope)
        for flag in ENGINEERING_FLAGS:
            self.assertIs(envelope[flag], False)
        return envelope["data"]

    def test_gate_replay_rejects_missing_input_and_forged_consent(self):
        result = self.run_replay("gates")
        cases = {item["scenario"]: item for item in result["scenarios"]}
        self.assertTrue(result["passed"])
        self.assertEqual(cases["g1_missing_outer_profile"]["blocking_missing"], ["outer_profile"])
        self.assertFalse(cases["g1_missing_outer_profile"]["allowed"])
        self.assertEqual(len(cases["g1_ready"]["items"]), 6)
        self.assertEqual(cases["g1_ready"]["not_specified"],
                         ["material_and_finish", "tolerance_accuracy"])
        self.assertEqual(cases["g2_forged_consent"]["code"], "G2_EVENT_MISSING")
        self.assertEqual(cases["g2_revision_changed"]["code"], "G2_CONSENT_INVALIDATED")
        self.assertEqual(cases["g2_saved_replay_consent"]["identity_assurance"], "replay_simulated")
        self.assertTrue(cases["g2_saved_replay_consent"]["allowed"])
        for scenario in cases.values():
            for flag in ENGINEERING_FLAGS:
                self.assertIs(scenario[flag], False)
        binding = g2_binding("REPLAY-ONLY", 2, "a" * 64, "b" * 64)
        result = g2_gate({"consent": True}, binding, prompt_binding=binding, engine=self.engine)
        self.assertEqual(result["code"], "G2_EVENT_MISSING")

    def test_five_seat_eval_publishes_only_readable_neutral_evidence(self):
        result = self.run_replay("eval")
        self.assertEqual(result["sensitivity"]["raw_combinations"], 128)
        anonymous_ids = ["K01", "K02", "K03", "K04", "K05"]
        self.assertEqual(result["anonymous_ids"], anonymous_ids)
        self.assertEqual(result["scoring"]["eligible_ids"], anonymous_ids)
        target = self.workspace / result["packet_path"]
        content = target.read_text(encoding="utf-8")
        packet = json.loads(content)
        for secret in ("SyntheticAuthor", "evidence_map", "private_source", "observation.json",
                       "REPLAY-JUDGE", "REPLAY-COORDINATOR"):
            self.assertNotIn(secret, content)
        self.assertEqual(sorted(packet["candidates"]), anonymous_ids)
        self.assertEqual(len(packet["public_evidence"]), 5)
        for anonymous_id, candidate in packet["candidates"].items():
            self.assertIsNone(candidate["author_session"])
            self.assertNotIn("role", candidate)
            self.assertEqual(candidate["candidate_id"], anonymous_id)
            self.assertIsNone(candidate["parameters"][0]["value"])
            reference = candidate["decision_records"][0]["source_refs"][0]
            self.assertTrue(reference["path"].startswith("evidence/" + anonymous_id + "/"))
            self.assertIn(reference, packet["public_evidence"])
            actual = (target.parent / reference["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(actual).hexdigest(), reference["sha256"])
        handoff = result["outbox_ack"]
        self.assertEqual(handoff["statuses"], [
            "OUTBOX_READY_NOT_SENT", "SEND_RECEIPT_RECORDED_ACK_PENDING",
            "P_ACK_CONCEPT_START_REQUESTED",
        ])
        self.assertFalse(handoff["delivery_authenticated"])

    def test_ack_rechecks_original_route_receipt_and_packet_revision(self):
        fixture = self.engine.load_event("evaluation", "session.json")
        packet = {"status": "JUDGE_PACKET_READY", "candidates": {"K02": {}}}
        route = {"run_id": fixture["run_id"], "revision": fixture["revision"],
                 "coordinator": fixture["coordinator"], "judge": fixture["judge"]}
        outbox = prepare_outbox(packet, fixture["selection"], **route)
        common = {"event_id": outbox["event_id"], "recipient_session_id": route["coordinator"]}
        request = {**common, "fixture": True, "event_sha256": canonical_sha256(outbox)}
        receipt = {**common, "success": True, "message_id": "replay-receipt-1"}
        raw = {**receipt, "fixture": True}
        with self.assertRaises(FixtureIntegrityError):
            record_send(outbox, request, receipt, dict(raw, recipient_session_id="wrong"))
        sent = record_send(outbox, request, receipt, raw)
        with self.assertRaises(FixtureIntegrityError):
            acknowledge(outbox, request, receipt, raw, sent, consumer=route["coordinator"],
                        packet=dict(packet, status="different"), revision=route["revision"])
        ack = acknowledge(outbox, request, receipt, raw, sent, consumer=route["coordinator"],
                          packet=packet, revision=route["revision"])
        self.assertFalse(ack["backend_called"])

    def test_six_piece_bundle_readback_detects_a_changed_member(self):
        data = self.run_replay("concept")
        readback = data["artifact_verification"]["standard_bundle"]
        directory = self.workspace / readback["path"]
        legacy = json.loads((self.workspace / "manifest.json").read_bytes())
        self.assertEqual(set(readback["files"]), set(BUNDLE_FILES))
        self.assertEqual(len(readback["archive_members"]), 5)
        self.assertEqual(readback["binding"]["confirmation_binding_sha256"],
                         legacy["confirmation_binding_sha256"])
        for flag in ENGINEERING_FLAGS:
            self.assertIs(legacy[flag], False)
            self.assertIs(json.loads((directory / "manifest.json").read_bytes())[flag], False)
        (directory / "notes.md").write_text("changed", encoding="utf-8")
        with self.assertRaises(FixtureIntegrityError):
            verify_standard_bundle(directory, binding=readback["binding"])

    def test_revision_invalidates_attached_confirmation(self):
        state, expected = workflow.start_concept(self.engine)
        workflow.build_concept(state, self.engine, expected)
        workflow._apply_parameters(state, self.engine, expected, "parameters.json")
        workflow.require_confirmation(state)
        workflow.confirm(state)
        revised = workflow.next_parameter_revision(state, self.engine, expected,
                                                    "parameters-mutated.json")
        self.assertEqual(state["confirmation"]["state"], "RECORDED")
        self.assertEqual(revised["confirmation"]["state"], "CONFIRMATION_INVALIDATED")
        self.assertEqual(revised["revision"], state["revision"] + 1)
