# -*- coding: utf-8 -*-
import unittest

from cad_agent_showcase import workflow
from cad_agent_showcase.engines.replay_engine import ReplayEngine
from tests.support import FIXTURES, ROOT


class UnknownPreservationTests(unittest.TestCase):
    def setUp(self):
        self.engine = ReplayEngine(ROOT, FIXTURES)

    def test_concept_keeps_unknowns_before_parameters(self):
        state, expected = workflow.start_concept(self.engine)
        self.assertEqual(state["status"], "CONCEPT_DRAFT")
        self.assertEqual(len(state["unknowns"]), 6)
        self.assertIn("material", state["unknowns"])
        self.assertIn("plate_thickness_mm", state["unknowns"])
        self.assertEqual(state["brief"]["missing_required_parameters"], state["unknowns"])
        self.assertEqual(state["parameters"], None)

    def test_candidates_are_assumptions_not_parameters(self):
        state, expected = workflow.start_concept(self.engine)
        state = workflow.build_concept(state, self.engine, expected)
        self.assertEqual(state["status"], "NEED_PARAMETERS")
        self.assertEqual(len(state["candidates"]), 2)
        self.assertEqual(state["parameters"], None)
        assumptions = " ".join(state["candidates"][0]["assumptions"])
        self.assertIn("Assumes", assumptions)

    def test_drawing_unknown_entity_is_listed_not_interpreted(self):
        state, expected = workflow.start_drawing(self.engine)
        summary = state["object_summary"]
        self.assertEqual(summary["entities"]["CIRCLE"], 4)
        self.assertEqual(summary["entities"]["LINE"], 4)
        self.assertEqual([item["type"] for item in summary["unknown_entities"]],
                         ["SPLINE"])
        self.assertEqual(state["brief"]["unknown_objects"], ["SPLINE"])

    def test_parameter_provenance_is_explicit(self):
        state, expected = workflow.start_concept(self.engine)
        state = workflow.build_concept(state, self.engine, expected)
        workflow._apply_parameters(state, self.engine, expected, "parameters.json")
        self.assertEqual(state["status"], "PARAMETERS_READY")
        for item in state["parameters_summary"]:
            self.assertEqual(item["source"], "USER_INPUT")
            self.assertFalse(item["verified"])
        self.assertEqual(len(state["parameters_summary"]), 6)


if __name__ == "__main__":
    unittest.main()
