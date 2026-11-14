# -*- coding: utf-8 -*-
import unittest

from cad_agent_showcase.contracts import (ENTRY_CONCEPT, ENTRY_DRAWING,
                                         STATE_CONCEPT_DRAFT, STATE_DRAWING_INSPECTED,
                                         STATE_STOPPED, ReplayRejection)
from cad_agent_showcase.engines.replay_engine import ReplayEngine
from cad_agent_showcase.routing import route_input
from tests.support import FIXTURES, ROOT


class RoutingTests(unittest.TestCase):
    def test_concept_routes_to_concept_entry(self):
        routed = route_input({"kind": "concept"})
        self.assertEqual(routed["entry"], ENTRY_CONCEPT)
        self.assertEqual(routed["status"], STATE_CONCEPT_DRAFT)
        self.assertEqual(routed["code"], "OK")

    def test_dxf_routes_to_drawing_entry(self):
        routed = route_input({"kind": "drawing", "path": "plate-demo.dxf"})
        self.assertEqual(routed["entry"], ENTRY_DRAWING)
        self.assertEqual(routed["status"], STATE_DRAWING_INSPECTED)

    def test_unknown_extension_is_refused(self):
        routed = route_input({"kind": "drawing", "path": "unsupported.xyz"})
        self.assertIsNone(routed["entry"])
        self.assertEqual(routed["status"], STATE_STOPPED)
        self.assertEqual(routed["code"], "UNSUPPORTED_FORMAT")

    def test_unknown_kind_is_refused(self):
        routed = route_input({"kind": "spreadsheet"})
        self.assertEqual(routed["status"], STATE_STOPPED)
        self.assertEqual(routed["code"], "UNSUPPORTED_FORMAT")

    def test_engine_refuses_unsupported_extension(self):
        engine = ReplayEngine(ROOT, FIXTURES)
        with self.assertRaises(ReplayRejection) as caught:
            engine.inspect_drawing("unsupported.xyz")
        self.assertEqual(caught.exception.code, "UNSUPPORTED_FORMAT")

    def test_engine_exposes_public_port_methods(self):
        engine = ReplayEngine(ROOT, FIXTURES)
        for name in ("inspect_input", "build_concept", "resolve_parameters",
                     "emit_deliverable", "readback"):
            self.assertTrue(callable(getattr(engine, name, None)), name)
        payload = engine.load_concept_input()
        info = engine.inspect_input(payload)
        self.assertEqual(info["input_digest"],
                         "cf45ee5129cf8300716788a4cc3bf312b234ac47f3e51d5cdbbab92364ee8e4e")


if __name__ == "__main__":
    unittest.main()
