"""JSON report stability contract (REQUIREMENTS_1.md §6.7, FR-33).

Pins the exact shape of schema_version 1. Fields may be ADDED within a version — update
the expected sets below and keep schema_version at 1. Any rename / retype / removal /
meaning change must bump schema_version.
"""

import json
import unittest

from astroturf.classify import ClassifiedPath, Kind
from astroturf.output import Report, render_json
from astroturf.verdict import Finding, Verdict

TOP_LEVEL_KEYS = {
    "schema_version", "headline_verdict", "blocking", "exit_code",
    "findings", "classifications", "warnings",
}
FINDING_KEYS = {"verdict", "module", "detail"}
CLASSIFICATION_KEYS = {"path", "kind", "module", "reason"}


class JsonContractTest(unittest.TestCase):
    def _payload(self):
        report = Report(
            headline=Verdict.FIX_IS_IN_THE_TESTS,
            findings=[Finding(Verdict.FIX_IS_IN_THE_TESTS, ".", {"classname": "T", "name": "t"})],
            classifications=[ClassifiedPath("a", Kind.TEST, ".", "why")],
            warnings=["w"],
        )
        return json.loads(render_json(report))

    def test_schema_version_is_1(self):
        self.assertEqual(self._payload()["schema_version"], 1)

    def test_top_level_keys(self):
        self.assertEqual(set(self._payload()), TOP_LEVEL_KEYS)

    def test_headline_separate_from_findings(self):
        p = self._payload()
        self.assertIsInstance(p["headline_verdict"], str)
        self.assertIsInstance(p["findings"], list)

    def test_finding_and_classification_shape(self):
        p = self._payload()
        self.assertEqual(set(p["findings"][0]), FINDING_KEYS)
        self.assertEqual(set(p["classifications"][0]), CLASSIFICATION_KEYS)

    def test_types(self):
        p = self._payload()
        self.assertIsInstance(p["blocking"], bool)
        self.assertIsInstance(p["exit_code"], int)
        self.assertIsInstance(p["warnings"], list)


if __name__ == "__main__":
    unittest.main()
