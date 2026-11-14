# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from tests.support import run_cli


class CliContractTests(unittest.TestCase):
    def _run(self, args):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return run_cli(args + ["--out", os.path.join(tmp.name, "out")])

    def test_three_public_commands_succeed(self):
        for command in ("concept", "drawing", "confirmation-mutation"):
            code, envelope, stdout, stderr = self._run(
                ["demo", command, "--replay"])
            self.assertEqual(code, 0, "%s failed: %s" % (command, stderr))
            self.assertEqual(envelope["status"], "OK")
            self.assertEqual(envelope["code"], "OK")
            self.assertEqual(envelope["schema_version"],
                             "cad_agent_showcase.envelope.v1")

    def test_missing_replay_flag_is_input_error_not_rejection(self):
        code, envelope, _, _ = self._run(["demo", "concept"])
        self.assertEqual(code, 2)
        self.assertEqual(envelope["status"], "INPUT_ERROR")
        self.assertEqual(envelope["code"], "LIVE_MODE_UNAVAILABLE")

    def test_rejection_cases_exit_one_with_distinct_codes(self):
        expected = {
            "missing-parameters": "MISSING_PARAMETERS",
            "out-of-range": "PARAMETER_OUT_OF_RANGE",
            "unknown-format": "UNSUPPORTED_FORMAT",
        }
        for case, expected_code in expected.items():
            code, envelope, stdout, stderr = self._run(
                ["demo", "reject", "--case", case, "--replay"])
            self.assertEqual(code, 1, "%s: %s" % (case, stderr))
            self.assertEqual(envelope["status"], "REJECTED")
            self.assertEqual(envelope["code"], expected_code)
            self.assertEqual(envelope["artifacts"], [])

    def test_engine_failure_exits_three_without_delivery(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = os.path.join(tmp.name, "out")
        code, envelope, stdout, stderr = run_cli(
            ["demo", "concept", "--replay", "--fail-engine", "--out", out])
        self.assertEqual(code, 3, stderr)
        self.assertEqual(envelope["status"], "ENGINE_FAILURE")
        self.assertEqual(envelope["code"], "ENGINE_FAILURE")
        self.assertEqual(envelope["artifacts"], [])
        self.assertFalse(os.path.exists(os.path.join(out, "manifest.json")))

    def test_unknown_reject_case_is_usage_error(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        code, envelope, stdout, stderr = run_cli(
            ["demo", "reject", "--case", "nope", "--replay", "--out",
             os.path.join(tmp.name, "out")])
        self.assertEqual(code, 2)
        self.assertIsNone(envelope)

    def test_mutation_scenarios(self):
        code, envelope, stdout, stderr = self._run(
            ["demo", "confirmation-mutation", "--replay"])
        self.assertEqual(code, 0, stderr)
        scenarios = {item["scenario"]: item for item in envelope["data"]["scenarios"]}
        self.assertEqual(scenarios["old_confirmation_invalidated"]["status"],
                         "CONFIRMATION_INVALIDATED")
        self.assertEqual(scenarios["deliver_with_old_confirmation"]["code"],
                         "CONFIRMATION_INVALIDATED")
        self.assertEqual(scenarios["old_confirmation_reuse"]["code"],
                         "CONFIRMATION_REUSED")
        self.assertEqual(scenarios["user_reject"]["status"], "CONCEPT_ONLY_CLOSED")
        self.assertEqual(scenarios["user_reject"]["code"], "USER_REJECTED")
        self.assertEqual(scenarios["new_revision_continuation"]["status"],
                         "REPLAY_DELIVERED")
        self.assertEqual(scenarios["duplicate_execution"]["code"],
                         "DUPLICATE_DELIVERY")
        self.assertEqual(envelope["data"]["mismatches"], [])


if __name__ == "__main__":
    unittest.main()
