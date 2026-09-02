"""Claude Code Stop hook decision logic (FR-36). Pure — no real astroturf run."""

import contextlib
import io
import json
import unittest

from astroturf import stophook

BLOCKING = {
    "blocking": True,
    "headline_verdict": "FIX_IS_IN_THE_TESTS",
    "findings": [{
        "verdict": "FIX_IS_IN_THE_TESTS", "module": "svc-a",
        "detail": {"classname": "CalcTest", "name": "addsOne"},
    }],
}


class EvaluateTest(unittest.TestCase):
    def test_blocks_on_blocking_report(self):
        decision = stophook.evaluate(BLOCKING, stop_hook_active=False)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("svc-a: CalcTest.addsOne", decision["reason"])
        self.assertIn("fix is in the test files", decision["reason"])

    def test_allows_non_blocking(self):
        self.assertIsNone(stophook.evaluate(
            {"blocking": False, "headline_verdict": "HONEST_FIX"}, stop_hook_active=False))

    def test_never_blocks_twice_in_a_turn(self):
        self.assertIsNone(stophook.evaluate(BLOCKING, stop_hook_active=True))

    def test_missing_report_allows(self):
        self.assertIsNone(stophook.evaluate(None, stop_hook_active=False))

    def test_config_weakened_guidance(self):
        report = {"blocking": True, "headline_verdict": "CONFIG_WEAKENED",
                  "findings": [{"verdict": "CONFIG_WEAKENED", "module": ".",
                                "detail": {"goal": "org.jacoco:...:check"}}]}
        reason = stophook.evaluate(report, stop_hook_active=False)["reason"]
        self.assertIn("Restore the gate", reason)


class MainTest(unittest.TestCase):
    def test_fail_open_on_bad_stdin(self):
        self.assertEqual(stophook.main("not json", runner=lambda cwd, t: None), 0)

    def test_emits_block_decision(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = stophook.main('{"stop_hook_active": false, "cwd": "/x"}',
                                 runner=lambda cwd, t: BLOCKING)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buf.getvalue())["decision"], "block")

    def test_silent_when_allowed(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            stophook.main('{"stop_hook_active": true}', runner=lambda cwd, t: BLOCKING)
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
