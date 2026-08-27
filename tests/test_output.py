"""Output rendering tests (FR-31..FR-33, §6.7). Pure."""

import json
import unittest

from greenwash.classify import ClassifiedPath, Kind
from greenwash.output import Report, render_human, render_json
from greenwash.verdict import Finding, Verdict


def _report(**kw):
    base = dict(
        headline=Verdict.FIX_IS_IN_THE_TESTS,
        findings=[
            Finding(Verdict.FIX_IS_IN_THE_TESTS, ".", {
                "classname": "CalculatorTest", "name": "addsTwoNumbers",
                "after": "pass", "source_only": "fail",
            }),
            Finding(Verdict.CONFIG_WEAKENED, "svc-b", {
                "goal": "org.jacoco:jacoco-maven-plugin:0.8.11:check",
                "failed_at_base": True, "passes_after": True,
            }),
        ],
        classifications=[
            ClassifiedPath("src/main/java/Calculator.java", Kind.SOURCE, ".", "under main source root 'src/main/'"),
            ClassifiedPath("src/test/java/CalculatorTest.java", Kind.TEST, ".", "under test source root 'src/test/'"),
        ],
        warnings=["untracked file not audited: scratch/notes.txt"],
    )
    base.update(kw)
    return Report(**base)


class JsonTest(unittest.TestCase):
    def test_schema_and_separation(self):
        payload = json.loads(render_json(_report()))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["headline_verdict"], "FIX_IS_IN_THE_TESTS")
        self.assertTrue(payload["blocking"])
        self.assertEqual(payload["exit_code"], 1)
        self.assertEqual(len(payload["findings"]), 2)
        self.assertEqual(payload["classifications"][0]["kind"], "source")

    def test_deterministic(self):
        self.assertEqual(render_json(_report()), render_json(_report()))

    def test_findings_sorted_by_precedence(self):
        payload = json.loads(render_json(_report()))
        self.assertEqual(payload["findings"][0]["verdict"], "FIX_IS_IN_THE_TESTS")
        self.assertEqual(payload["findings"][1]["verdict"], "CONFIG_WEAKENED")

    def test_exit_override_flows_through(self):
        r = _report(headline=Verdict.TESTS_REMOVED_OR_SKIPPED, findings=[])
        payload = json.loads(render_json(r, exit_overrides={"TESTS_REMOVED_OR_SKIPPED": 1}))
        self.assertTrue(payload["blocking"])
        self.assertEqual(payload["exit_code"], 1)


class HumanTest(unittest.TestCase):
    def test_names_specific_test_not_counts(self):
        out = render_human(_report())
        self.assertIn("CalculatorTest.addsTwoNumbers", out)
        self.assertIn("org.jacoco:jacoco-maven-plugin:0.8.11:check", out)
        self.assertNotIn("2 findings", out)

    def test_grouped_by_module(self):
        out = render_human(_report())
        self.assertIn("module .", out)
        self.assertIn("module svc-b", out)

    def test_shows_disposition_and_classification(self):
        out = render_human(_report())
        self.assertIn("build fails: exit 1", out)
        self.assertIn("dispute in .greenwash.toml", out)
        self.assertIn("under test source root", out)

    def test_honest_fix_wording(self):
        out = render_human(_report(headline=Verdict.HONEST_FIX, findings=[]))
        self.assertIn("build passes: exit 0", out)
        self.assertIn("satisfies the checks without the test or config edits", out)
        self.assertNotIn("Findings:", out)


if __name__ == "__main__":
    unittest.main()
