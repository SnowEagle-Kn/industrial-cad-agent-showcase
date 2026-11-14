# -*- coding: utf-8 -*-
import copy
import unittest

from cad_agent_showcase import workflow
from cad_agent_showcase.confirmation import (binding_from_state, invalidate,
                                             verify_for_delivery, verify_reuse)
from cad_agent_showcase.engines.replay_engine import ReplayEngine
from tests.support import FIXTURES, ROOT


class ConfirmationInvalidationTests(unittest.TestCase):
    def _confirmed_concept(self):
        engine = ReplayEngine(ROOT, FIXTURES)
        expected = engine.concept_expected()
        state, _ = workflow.start_concept(engine)
        state = workflow.build_concept(state, engine, expected)
        workflow._apply_parameters(state, engine, expected, "parameters.json")
        workflow.require_confirmation(state)
        workflow.confirm(state, "ACCEPT", "EVT-TEST-ACCEPT", "2026-01-01T00:00:03Z", "C1")
        return engine, expected, state

    def test_binding_is_recorded(self):
        _, _, state = self._confirmed_concept()
        self.assertEqual(state["status"], "CONFIRMED")
        record = state["confirmation"]
        self.assertEqual(record["state"], "RECORDED")
        self.assertTrue(record["recorded"])
        self.assertEqual(record["identity_assurance"], "replay_simulated")
        self.assertEqual(len(record["binding_sha256"]), 64)

    def test_unchanged_binding_stays_valid(self):
        _, _, state = self._confirmed_concept()
        result = invalidate(state["confirmation"], binding_from_state(state))
        self.assertEqual(result["state"], "VALID")
        self.assertFalse(result["invalidated"])

    def test_parameter_change_invalidates(self):
        engine, expected, state = self._confirmed_concept()
        new_state = workflow.next_parameter_revision(
            state, engine, expected, "parameters-mutated.json")
        result = invalidate(state["confirmation"], binding_from_state(new_state))
        self.assertEqual(result["state"], "CONFIRMATION_INVALIDATED")
        self.assertTrue(result["invalidated"])
        changed = result["invalidated_by"]["changed_fields"]
        self.assertIn("parameters_digest", changed)
        self.assertIn("revision", changed)
        self.assertFalse(result["continues_delivery"])

    def test_old_record_is_not_mutated(self):
        engine, expected, state = self._confirmed_concept()
        original = copy.deepcopy(state["confirmation"])
        new_state = workflow.next_parameter_revision(
            state, engine, expected, "parameters-mutated.json")
        invalidate(state["confirmation"], binding_from_state(new_state))
        self.assertEqual(state["confirmation"], original)

    def test_delivery_with_stale_confirmation_is_blocked(self):
        engine, expected, state = self._confirmed_concept()
        new_state = workflow.next_parameter_revision(
            state, engine, expected, "parameters-mutated.json")
        stale_state = dict(new_state, confirmation=state["confirmation"])
        verification = verify_for_delivery(stale_state)
        self.assertFalse(verification["allowed"])
        self.assertEqual(verification["code"], "CONFIRMATION_INVALIDATED")

    def test_reuse_is_detected(self):
        engine, expected, state = self._confirmed_concept()
        new_state = workflow.next_parameter_revision(
            state, engine, expected, "parameters-mutated.json")
        reuse = verify_reuse(state["confirmation"], binding_from_state(new_state))
        self.assertTrue(reuse["reused"])
        self.assertEqual(reuse["code"], "CONFIRMATION_REUSED")

    def test_reject_closes_without_delivery(self):
        engine, expected, state = self._confirmed_concept()
        state["confirmation"] = None
        workflow.confirm(state, "REJECT", "EVT-TEST-REJECT",
                         "2026-01-01T00:00:05Z")
        self.assertEqual(state["status"], "CONCEPT_ONLY_CLOSED")
        self.assertEqual(state["confirmation"]["recorded"], False)
        self.assertEqual(state["confirmation"]["reason"], "USER_REJECTED")
        self.assertFalse(state["confirmation"]["continues_delivery"])


if __name__ == "__main__":
    unittest.main()
