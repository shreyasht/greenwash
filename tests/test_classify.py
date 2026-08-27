"""Classification unit tests (FR-1..FR-6). Pure — no git, no Maven."""

import shutil
import tempfile
import unittest
from pathlib import Path

from greenwash.classify import Kind, classify


class ClassifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="greenwash-classify-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _c(self, path, **kw):
        return classify([path], repo_root=self.tmp, **kw)[0]

    def test_maven_main_is_source(self):
        self.assertIs(self._c("src/main/java/com/x/Calc.java").kind, Kind.SOURCE)

    def test_maven_test_root_is_test(self):
        self.assertIs(self._c("src/test/java/com/x/CalcTest.java").kind, Kind.TEST)

    def test_test_resource_yaml_is_test_not_config(self):
        self.assertIs(self._c("src/test/resources/application.yml").kind, Kind.TEST)

    def test_gradle_integration_test_root(self):
        self.assertIs(self._c("app/src/integrationTest/java/x/FooIT.java").kind, Kind.TEST)

    def test_pom_is_config(self):
        self.assertIs(self._c("pom.xml").kind, Kind.CONFIG)
        self.assertIs(self._c("service/pom.xml").kind, Kind.CONFIG)

    def test_ci_workflow_is_config(self):
        self.assertIs(self._c(".github/workflows/ci.yml").kind, Kind.CONFIG)

    def test_checkstyle_config_is_config(self):
        self.assertIs(self._c("config/checkstyle/checkstyle.xml").kind, Kind.CONFIG)
        self.assertIs(self._c("build-tools/spotbugs-exclude.xml").kind, Kind.CONFIG)

    def test_filename_fallback_for_non_standard_layout(self):
        self.assertIs(self._c("tests/CalculatorTest.java").kind, Kind.TEST)

    def test_docs_are_neutral(self):
        self.assertIs(self._c("README.md").kind, Kind.NEUTRAL)
        self.assertIs(self._c("docs/design.md").kind, Kind.NEUTRAL)

    def test_override_wins(self):
        c = self._c("src/main/java/Gen.java",
                    overrides={"src/main/java/Gen.java": "neutral"})
        self.assertIs(c.kind, Kind.NEUTRAL)
        self.assertIn("override", c.reason)

    def test_reason_is_always_populated(self):
        for p in ("pom.xml", "src/main/java/A.java", "src/test/java/ATest.java", "x.txt"):
            self.assertTrue(self._c(p).reason)

    def test_module_attribution(self):
        Path(self.tmp, "svc-a").mkdir()
        Path(self.tmp, "svc-a", "pom.xml").write_text("<project/>")
        Path(self.tmp, "pom.xml").write_text("<project/>")
        out = {c.path: c for c in classify(
            ["svc-a/src/main/java/A.java", "src/main/java/Root.java"], self.tmp)}
        self.assertEqual(out["svc-a/src/main/java/A.java"].module, "svc-a")
        self.assertEqual(out["src/main/java/Root.java"].module, ".")

    def test_no_build_files_means_root_module(self):
        self.assertEqual(self._c("src/main/java/A.java").module, ".")


if __name__ == "__main__":
    unittest.main()
