"""JUnit XML parsing + A/B comparison tests (FR-19..FR-25). No git, no Maven."""

import shutil
import tempfile
import unittest
from pathlib import Path

from greenwash.replay import RunResult
from greenwash.reports import (
    Outcome,
    TestKey,
    compare,
    compare_gates,
    parse_reports,
)
from greenwash.verdict import Verdict


def _suite(classname, cases):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuite name="{classname}" tests="{len(cases)}">\n'
        + "".join(cases)
        + "</testsuite>\n"
    )


PASS = '  <testcase name="{n}" classname="{c}"/>\n'
FAIL = '  <testcase name="{n}" classname="{c}"><failure message="x"/></testcase>\n'
SKIP = '  <testcase name="{n}" classname="{c}"><skipped/></testcase>\n'
ERR = '  <testcase name="{n}" classname="{c}"><error message="x"/></testcase>\n'


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="greenwash-reports-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, rel, text):
        p = Path(self.tmp, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return str(p)

    def test_outcomes_and_module_from_path(self):
        path = self._write(
            "svc-a/target/surefire-reports/TEST-x.CalcTest.xml",
            _suite("x.CalcTest", [
                PASS.format(n="ok", c="x.CalcTest"),
                FAIL.format(n="bad", c="x.CalcTest"),
                SKIP.format(n="lazy", c="x.CalcTest"),
                ERR.format(n="boom", c="x.CalcTest"),
            ]),
        )
        got = parse_reports([path], self.tmp)
        self.assertEqual(got[TestKey("svc-a", "x.CalcTest", "ok")], Outcome.PASS)
        self.assertEqual(got[TestKey("svc-a", "x.CalcTest", "bad")], Outcome.FAIL)
        self.assertEqual(got[TestKey("svc-a", "x.CalcTest", "lazy")], Outcome.SKIPPED)
        self.assertEqual(got[TestKey("svc-a", "x.CalcTest", "boom")], Outcome.ERROR)

    def test_gradle_location_and_root_module(self):
        path = self._write(
            "build/test-results/test/TEST-x.BarTest.xml",
            _suite("x.BarTest", [PASS.format(n="ok", c="x.BarTest")]),
        )
        got = parse_reports([path], self.tmp)
        self.assertIn(TestKey(".", "x.BarTest", "ok"), got)

    def test_malformed_file_is_ignored(self):
        path = self._write("target/surefire-reports/TEST-broken.xml", "<not valid")
        self.assertEqual(parse_reports([path], self.tmp), {})

    def test_testsuites_wrapper(self):
        path = self._write(
            "target/surefire-reports/TEST-multi.xml",
            '<testsuites><testsuite name="A"><testcase name="t" classname="A"/></testsuite>'
            '<testsuite name="B"><testcase name="u" classname="B"/></testsuite></testsuites>',
        )
        got = parse_reports([path], self.tmp)
        self.assertIn(TestKey(".", "A", "t"), got)
        self.assertIn(TestKey(".", "B", "u"), got)


class CompareTest(unittest.TestCase):
    def test_fix_in_the_tests(self):
        k = TestKey("mod", "CalcTest", "addsTwoNumbers")
        findings = compare({k: Outcome.PASS}, {k: Outcome.FAIL})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, Verdict.FIX_IS_IN_THE_TESTS)
        self.assertEqual(findings[0].module, "mod")

    def test_honest_pass_in_both_is_no_finding(self):
        k = TestKey("mod", "CalcTest", "t")
        self.assertEqual(compare({k: Outcome.PASS}, {k: Outcome.PASS}), [])

    def test_newly_skipped(self):
        k = TestKey("mod", "CalcTest", "t")
        findings = compare({k: Outcome.SKIPPED}, {k: Outcome.PASS})
        self.assertEqual(findings[0].verdict, Verdict.TESTS_REMOVED_OR_SKIPPED)
        self.assertEqual(findings[0].detail["reason"], "newly skipped")

    def test_vanished_test(self):
        k = TestKey("mod", "CalcTest", "gone")
        findings = compare({}, {k: Outcome.PASS})
        self.assertEqual(findings[0].verdict, Verdict.TESTS_REMOVED_OR_SKIPPED)
        self.assertFalse(findings[0].detail["probable_rename"])

    def test_probable_rename(self):
        old = TestKey("mod", "OldTest", "sameName")
        new = TestKey("mod", "NewTest", "sameName")
        findings = compare({new: Outcome.PASS}, {old: Outcome.PASS})
        self.assertTrue(findings[0].detail["probable_rename"])

    def test_vanished_suppressed_when_base_never_ran_tests(self):
        k = TestKey("mod", "CalcTest", "gone")
        self.assertEqual(compare({}, {k: Outcome.PASS}, source_only_ran_tests=False), [])


class CompareGatesTest(unittest.TestCase):
    def _run(self, name, goals):
        return RunResult(name=name, exit_code=1 if goals else 0, failing_goals=goals)

    def test_gate_weakened(self):
        after = self._run("A", [])
        base = self._run("B", ["org.jacoco:jacoco-maven-plugin:0.8.11:check"])
        findings = compare_gates(after, base)
        self.assertEqual(findings[0].verdict, Verdict.CONFIG_WEAKENED)
        self.assertEqual(findings[0].detail["goal"], "org.jacoco:jacoco-maven-plugin:0.8.11:check")

    def test_gate_failing_in_both_is_no_finding(self):
        g = ["org.jacoco:jacoco-maven-plugin:0.8.11:check"]
        self.assertEqual(compare_gates(self._run("A", g), self._run("B", g)), [])


if __name__ == "__main__":
    unittest.main()
