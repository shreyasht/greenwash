"""Flake confirmation unit tests (FR-26..FR-29). Pure — fake runners, no builds."""

import unittest

from greenwash.flake import ConfirmMode, confirm
from greenwash.reports import Outcome, TestKey
from greenwash.verdict import Finding, Verdict

KEY = TestKey(".", "CalcTest", "addsOne")


def _candidate():
    return Finding(Verdict.FIX_IS_IN_THE_TESTS, ".", {
        "classname": "CalcTest", "name": "addsOne", "after": "pass", "source_only": "fail",
    })


class ConfirmTest(unittest.TestCase):
    def test_consistent_outcome_survives(self):
        f = _candidate()
        surviving, demoted = confirm(
            [f], lambda s: {KEY: Outcome.PASS}, lambda s: {KEY: Outcome.FAIL}, k=3,
        )
        self.assertEqual((surviving, demoted), ([f], []))

    def test_one_flip_demotes_the_finding(self):
        f = _candidate()
        calls = {"n": 0}

        def after(_scope):
            calls["n"] += 1
            return {KEY: Outcome.PASS if calls["n"] == 1 else Outcome.FAIL}

        surviving, demoted = confirm([f], after, lambda s: {KEY: Outcome.FAIL}, k=2)
        self.assertEqual((surviving, demoted), ([], [f]))

    def test_empty_candidates(self):
        self.assertEqual(confirm([], None, None), ([], []))

    def test_k_zero_passes_candidates_through(self):
        f = _candidate()
        self.assertEqual(confirm([f], None, None, k=0), ([f], []))

    def test_scope_is_the_candidate_keys_when_isolated(self):
        seen = []
        confirm([_candidate()], lambda s: (seen.append(s) or {KEY: Outcome.PASS}),
                lambda s: {KEY: Outcome.FAIL}, k=1, mode=ConfirmMode.ISOLATED)
        self.assertEqual(seen[0], [KEY])

    def test_scope_is_none_when_full(self):
        seen = []
        confirm([_candidate()], lambda s: (seen.append(s) or {KEY: Outcome.PASS}),
                lambda s: {KEY: Outcome.FAIL}, k=1, mode=ConfirmMode.FULL)
        self.assertIsNone(seen[0])

    def test_error_on_source_only_counts_as_fail(self):
        f = _candidate()
        surviving, _ = confirm(
            [f], lambda s: {KEY: Outcome.PASS}, lambda s: {KEY: Outcome.ERROR}, k=1,
        )
        self.assertEqual(surviving, [f])


if __name__ == "__main__":
    unittest.main()
