"""Headline derivation, precedence, blocking rule (§4.3, §5, §6.7). Pure."""

import unittest

from astroturf.verdict import (
    Finding,
    Verdict,
    exit_code,
    headline,
    is_blocking,
    resolve,
)


def F(verdict, module="."):
    return Finding(verdict, module, {})


class HeadlineTest(unittest.TestCase):
    def test_precedence_fix_in_tests_beats_removed(self):
        self.assertEqual(
            headline([F(Verdict.TESTS_REMOVED_OR_SKIPPED), F(Verdict.FIX_IS_IN_THE_TESTS)]),
            Verdict.FIX_IS_IN_THE_TESTS,
        )

    def test_config_weakened_beats_inconclusive_compile(self):
        self.assertEqual(
            headline([F(Verdict.INCONCLUSIVE_COMPILE), F(Verdict.CONFIG_WEAKENED)]),
            Verdict.CONFIG_WEAKENED,
        )

    def test_empty_is_honest_fix(self):
        self.assertEqual(headline([]), Verdict.HONEST_FIX)

    def test_highest_precedence_across_modules(self):
        self.assertEqual(
            headline([F(Verdict.TESTS_REMOVED_OR_SKIPPED, "mod-a"),
                      F(Verdict.FIX_IS_IN_THE_TESTS, "mod-b")]),
            Verdict.FIX_IS_IN_THE_TESTS,
        )


class ExitCodeTest(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(exit_code(Verdict.FIX_IS_IN_THE_TESTS), 1)
        self.assertEqual(exit_code(Verdict.CONFIG_WEAKENED), 1)
        self.assertEqual(exit_code(Verdict.HONEST_FIX), 0)
        self.assertEqual(exit_code(Verdict.TESTS_REMOVED_OR_SKIPPED), 0)

    def test_override(self):
        self.assertEqual(
            exit_code(Verdict.TESTS_REMOVED_OR_SKIPPED, {"TESTS_REMOVED_OR_SKIPPED": 1}), 1
        )

    def test_blocking_rule(self):
        self.assertTrue(is_blocking(Verdict.FIX_IS_IN_THE_TESTS))
        self.assertFalse(is_blocking(Verdict.INCONCLUSIVE_COMPILE))
        self.assertFalse(is_blocking(Verdict.NO_TEST_CHANGES))


class ResolveTest(unittest.TestCase):
    def test_no_test_changes(self):
        findings, head = resolve(
            test_or_config_changed=False, per_test_findings=[], gate_findings=[])
        self.assertEqual(head, Verdict.NO_TEST_CHANGES)
        self.assertEqual(findings, [])

    def test_clean_is_honest_fix(self):
        _, head = resolve(
            test_or_config_changed=True, per_test_findings=[], gate_findings=[])
        self.assertEqual(head, Verdict.HONEST_FIX)

    def test_surviving_per_test_finding(self):
        _, head = resolve(
            test_or_config_changed=True,
            per_test_findings=[F(Verdict.FIX_IS_IN_THE_TESTS)],
            gate_findings=[])
        self.assertEqual(head, Verdict.FIX_IS_IN_THE_TESTS)

    def test_compile_wall_without_gate(self):
        _, head = resolve(
            test_or_config_changed=True, per_test_findings=[], gate_findings=[],
            source_only_compiled=False)
        self.assertEqual(head, Verdict.INCONCLUSIVE_COMPILE)

    def test_gate_outranks_compile_wall(self):
        findings, head = resolve(
            test_or_config_changed=True, per_test_findings=[],
            gate_findings=[F(Verdict.CONFIG_WEAKENED)],
            source_only_compiled=False)
        self.assertEqual(head, Verdict.CONFIG_WEAKENED)
        self.assertIn(Verdict.INCONCLUSIVE_COMPILE, {f.verdict for f in findings})

    def test_all_candidates_demoted_is_flaky(self):
        _, head = resolve(
            test_or_config_changed=True, per_test_findings=[], gate_findings=[],
            demoted_findings=[F(Verdict.FIX_IS_IN_THE_TESTS)])
        self.assertEqual(head, Verdict.INCONCLUSIVE_FLAKY)

    def test_demoted_but_gate_survives_is_not_flaky(self):
        _, head = resolve(
            test_or_config_changed=True, per_test_findings=[],
            gate_findings=[F(Verdict.CONFIG_WEAKENED)],
            demoted_findings=[F(Verdict.FIX_IS_IN_THE_TESTS)])
        self.assertEqual(head, Verdict.CONFIG_WEAKENED)

    def test_no_reports_is_inconclusive_build(self):
        _, head = resolve(
            test_or_config_changed=True, per_test_findings=[], gate_findings=[],
            source_only_ran_tests=False)
        self.assertEqual(head, Verdict.INCONCLUSIVE_BUILD)


if __name__ == "__main__":
    unittest.main()
