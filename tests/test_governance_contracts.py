import copy
import json
import runpy
import unittest
from pathlib import Path

from cad_agent_showcase.governance import binding, confirm, schema_runtime, scoring, state_machine
from cad_agent_showcase.governance.envelope import InputError


DIGEST = "a" * 64
CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def contract_examples():
    run = {"run_id": "DemoRun", "revision": "r1"}
    locator = {"kind": "text_lines", "token": "lines:1-1", "view_id": None, "region": None}
    source = {"path": "note.txt", "sha256": DIGEST, "locator": locator}
    slot = {"statements": [], "unresolved_question_ids": []}
    binding_fields = {
        **run, "task_id": "DemoTask", "brief_sha256": DIGEST, "source_manifest_sha256": DIGEST,
        "requirements_revision": "r1", "rules_revision": "r1",
    }
    requirement_kinds = ("GOAL", "BOUNDARY", "PROCESS", "CONSTRAINTS", "DELIVERY")
    stage_fields = {"stage": "PRESELECTION", "candidate_id": "K01", "binding": binding_fields}
    contract_fields = {"contract_id": "DemoContract", "revision": "r1", "source_refs": []}
    file_ref = {"path": "note.txt", "sha256": DIGEST, "bytes": 8}
    semantic_files = (
        "candidate", "scene", "scene_binding", "brief", "facts", "generalization",
        "source_manifest", "render_manifest",
    )
    timestamp = "2020-01-02T03:04:05Z"
    return {
        "common": {},
        "entry": {
            **run, "schema": "wishcad.brief.v1.2",
            "entry_slots": {name: slot for name in ("goal", "object_context", "constraints")},
            "delivery_scope": "CONCEPT", "delivery_scope_source_refs": [source],
            "evidence_gaps": [{
                "question_id": "QuestionA", "slot": "goal", "question": "What is needed?",
                "dependency_ids": [], "status": "OPEN", "answer": None, "source_refs": [],
            }],
        },
        "facts": {
            **run, "schema": "wishcad.facts.v1.2", "source_manifest_ref": source,
            "reference_frames": [], "objects": [],
        },
        "source-manifest": {
            "schema": "wishcad.source-manifest.v1.2", "kind": "source_manifest",
            "recorded_at": timestamp, "file_count": 1, "content_sha256": DIGEST,
            "files": [{"source_id": "SourceA", "path": "note.txt", "sha256": DIGEST,
                       "bytes": 8, "locators": [locator], "usage_ids": []}],
        },
        "generalization": {
            **run, "schema": "wishcad.generalization.v1.1",
            "goal_requirement_ids": [], "success_observations": [], "causal_hypotheses": [],
            "change_scope": {"allowed_object_ids": [], "allowed_feature_ids": [],
                             "authority_refs": [], "unresolved": []},
        },
        "candidate-cognition": {
            "schema": "wishcad.candidate.v1.1", "consumed_feature_ids": [],
            "decision_records": [], "critical_unknowns": [],
            "evidence_refs": {"artifacts": [source], "layout": None},
        },
        "scene-cognition": {
            "run_id": "DemoRun", "candidate_id": "K01", "candidate_version": "r1",
            "candidate_sha256": DIGEST, "cognition_schema": "wishcad.scene-cognition.v1",
            "object_bindings": [],
        },
        "neutral-evidence-map": {
            **run, "schema": "wishcad.neutral-evidence-map.v1", "coordinator_only": True,
            "mappings": [{
                "evidence_id": "EvidenceA", "private_source": source,
                "public_evidence": {**source, "path": "evidence/neutral.txt"},
                "content_transform": "NONE", "purpose": "Example",
            }],
        },
        "semantic-check": {
            "schema": "wishcad.semantic-check.v1", "checked_at": timestamp,
            "feature_results": [], "overall_result": "INDETERMINATE", "critical_unresolved": [],
            "limited_conclusion": "Synthetic example.",
            "binding": {
                "schema": "wishcad.semantic-binding.v1", "task": {**run, "root": "demo"},
                "selected_candidate_id": "K01", "candidate_version": "r1",
                **{name: file_ref for name in semantic_files},
                "sources": [], "authorization_refs": [], "credential_sha256": DIGEST,
                "views": [{"view_id": "ViewA", "image": file_ref, "size": [4, 4], "view_type": "EXAMPLE",
                           "direction": [0, 0, 1], "viewpoint_sha256": DIGEST}],
                "feature_inventory": [], "expected_feature_ids": [], "critical_unknown_feature_ids": [],
                "rules": {"version": "r1", "implementation_sha256": DIGEST, "schema_sha256": DIGEST},
            },
            "evaluator": {"kind": "OTHER", "source": "synthetic", "model": None,
                          "session_ref": "DemoReview", "record_ref": file_ref,
                          "identity_authenticated": False, "limitations": "Example only."},
        },
        "content-export": {
            **stage_fields, "schema": "wishcad.content-export.v1", "candidate_sha256": DIGEST,
            "record_sha256": DIGEST, "anonymous_mapping_sha256": DIGEST,
        },
        "content-record": {
            **stage_fields, "schema": "wishcad.content-check.v1", "process_sha256": DIGEST,
            "delivery_sha256": DIGEST,
            "artifacts": {"layout_sha256": DIGEST, "scene_sha256": DIGEST,
                          "images": [{"view_id": "ViewA", "sha256": DIGEST}]},
            "reader": {"source_kind": "UNKNOWN", "executor": "Demo", "model_or_session": "DemoReview"},
            "items": [{"item_id": "ItemA", "applicable": True, "view_ids": [], "state_ids": [],
                       "feature_ids": [], "result": "INDETERMINATE", "reason": "Example only."}],
        },
        "requirements-content": {
            "schema": "wishcad.requirements-content.v1", "binding": binding_fields,
            "requirements_check": [
                {"kind": kind, "status": "UNKNOWN", "requirement_ids": [], "source_refs": [], "gap": None}
                for kind in requirement_kinds
            ],
            "actions": [{"action_id": "ActionA", "dependencies": [
                {"dependency_id": f"Dependency{index}", "check_kind": kind,
                 "requirement_ids": [], "required": True, "nonblocking_reason": ""}
                for index, kind in enumerate(requirement_kinds)
            ]}],
            "process_contract": {**contract_fields, "states": [], "transitions": []},
            "delivery_contract": {**contract_fields, "items": [
                {"item_id": "ItemA", "applicable": True, "applicability_reason": "",
                 "stages": ["PRESELECTION"], "view_ids": [], "state_ids": [], "feature_ids": []}
            ]},
        },
    }


class ContractTests(unittest.TestCase):
    def test_all_twelve_named_contracts_validate_instances(self):
        examples = contract_examples()
        self.assertEqual(set(examples), set(schema_runtime.SCHEMAS))
        for name, data in examples.items():
            with self.subTest(schema=name):
                self.assertTrue(schema_runtime.validate_schema(name, data)["schema_valid"])
                # The common document provides definitions used by other schemas.
                if name != "common":
                    with self.assertRaises(InputError) as refused:
                        schema_runtime.validate_schema(name, {**data, "undeclared": True})
                    self.assertEqual(refused.exception.code, "COGNITION_SCHEMA_INVALID")

    def test_nested_refs_conditionals_and_policy_reject_invalid_evidence(self):
        examples = contract_examples()
        candidate = copy.deepcopy(examples["candidate-cognition"])
        candidate["evidence_refs"]["artifacts"][0]["locator"]["kind"] = "unknown"
        with self.assertRaises(InputError):
            schema_runtime.validate_schema("candidate-cognition", candidate)
        brief = examples["entry"]
        brief["evidence_gaps"][0]["status"] = "ANSWERED"
        with self.assertRaises(InputError):
            schema_runtime.validate_projection("brief", brief)
        brief["evidence_gaps"][0]["answer"] = "A supported answer."
        brief["evidence_gaps"][0]["source_refs"] = brief["delivery_scope_source_refs"]
        carrier = {**brief, "mode": "NO_DRAWING_CONCEPT"}
        self.assertEqual(schema_runtime.validate_projection("brief", carrier), brief)
        with self.assertRaises(InputError) as refused:
            schema_runtime.validate_projection("brief", {**carrier, "unexpected_field": "value"})
        self.assertEqual(refused.exception.code, "COGNITION_UNKNOWN_KEY")

    def test_semantic_datetime_and_local_references_are_validated(self):
        value = contract_examples()["semantic-check"]
        value["checked_at"] = "2020-02-31T03:04:05Z"
        with self.assertRaises(InputError):
            schema_runtime.validate_schema("semantic-check", value)
        value["checked_at"] = "2020-02-29T03:04:05Z"
        value["binding"]["views"][0]["size"] = [1, 2, 3]
        with self.assertRaises(InputError):
            schema_runtime.validate_schema("semantic-check", value)
        value["binding"]["views"][0]["size"] = [True, 2]
        with self.assertRaises(InputError):
            schema_runtime.validate_schema("semantic-check", value)

    def test_checklist_is_structural_and_refuses_changed_acceptance_status(self):
        verifier = runpy.run_path(str(CONTRACTS / "verify_checklist.py"))
        contract = json.loads((CONTRACTS / "acceptance-checklist-72.json").read_bytes())
        coverage = json.loads((CONTRACTS / "requirements-coverage.json").read_bytes())
        self.assertEqual(verifier["verify"](contract, coverage), [])
        self.assertEqual(len(contract["items"]), 72)
        self.assertEqual({item["status"] for item in contract["items"]}, {"NOT_RUN"})
        contract["items"][0]["status"] = "PASS"
        self.assertTrue(verifier["verify"](contract, coverage))
        contract["items"][0]["status"] = "NOT_RUN"
        contract["items"][1]["id"] = contract["items"][0]["id"]
        self.assertTrue(any("Duplicate IDs" in problem for problem in verifier["verify"](contract, coverage)))

    def test_state_machine_keeps_25_states_and_refuses_terminal_advances(self):
        self.assertEqual(len(set(state_machine.CHAIN_STATES)), 25)
        self.assertEqual(set(state_machine.TRANSITIONS), set(state_machine.CHAIN_STATES))
        for previous, next_states in state_machine.TRANSITIONS.items():
            for action in next_states:
                with self.subTest(previous=previous, action=action):
                    result, code = state_machine.evaluate({"previous_state": previous, "action_status": action})
                    self.assertEqual(code, 0)
                    self.assertTrue(result["transition"]["allowed"])
        result, code = state_machine.evaluate({
            "previous_state": "DESIGN_ONLY_CLOSED", "action_status": "DEVELOPMENT_OUTPUT_DELIVERED"
        })
        self.assertNotEqual(code, 0)
        self.assertEqual(result["code"], "STATE_TERMINAL_NO_TRANSITION")

    def test_128_scoring_vertices_and_inverted_interval_refusal(self):
        points = {criterion: 3 for criterion in scoring.CRITERIA}
        report = scoring.perturb({"K01": {**points, "C1": 4, "C2": 2}, "K02": points})
        self.assertEqual(report["raw_combinations"], 128)
        self.assertEqual(report["unique_normalized_weight_sets"], 127)
        self.assertEqual(report["base_leader"], "K02")
        self.assertGreater(report["leader_runner_flipped_combinations"], 0)
        self.assertFalse(report["probability_claim"])
        passed = dict.fromkeys(scoring.GATES, "PASS_CONCEPT")
        with self.assertRaises(InputError) as refused:
            scoring.score_candidate(passed, {"C1": {"interval": [4, 2]}})
        self.assertEqual(refused.exception.code, "INTERVAL_INVERTED")

    def test_upstream_revision_invalidates_bound_confirmation(self):
        event = {
            "action": "ACCEPT", "selected_candidate_id": "K01", "candidate_version": "r1",
            "mode": "NO_DRAWING_CONCEPT", "run_id": "DemoRun", "locally_recorded": True,
            "capture_sha256": DIGEST, "captured_by": "SyntheticRecorder",
        }
        before = {field: binding.sha256_object({"example": field}) for field in binding.BINDING_FIELDS
                  if field.endswith("_sha256")}
        before.update({
            "mode": event["mode"], "run_id": event["run_id"], "endpoint": "CONCEPT_CAD",
            "candidate_id": "K01", "candidate_version": "r1", "event_sha256": binding.sha256_object(event),
        })
        record = confirm.record_confirmation(before, "events/synthetic", event)
        self.assertEqual(record["state"], "RECORDED")
        original = copy.deepcopy(record)
        after = {**before, "candidate_sha256": DIGEST, "candidate_version": "r2"}
        invalidated = confirm.invalidate(record, after)
        self.assertEqual(invalidated["state"], "INVALIDATED")
        self.assertEqual(set(invalidated["invalidated_by"]["changed_fields"]),
                         {"candidate_version", "candidate_sha256"})
        self.assertFalse(invalidated["continues_cad"])
        self.assertTrue(invalidated["re_review_required"])
        self.assertEqual(record, original)


if __name__ == "__main__":
    unittest.main()
