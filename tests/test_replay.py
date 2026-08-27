"""Replay execution tests (FR-12..FR-18). Pure helpers + a real timeout; no Maven."""

import shutil
import tempfile
import unittest
from pathlib import Path

from greenwash.replay import (
    _is_maven,
    _maven_scope,
    _parse_failing_goals,
    discover_reports,
    run_build,
)


class MavenScopeTest(unittest.TestCase):
    def test_detects_maven(self):
        self.assertTrue(_is_maven(["mvn", "test"]))
        self.assertTrue(_is_maven(["./mvnw", "test"]))
        self.assertTrue(_is_maven(["/opt/bin/mvn", "test"]))
        self.assertFalse(_is_maven(["gradle", "test"]))

    def test_scopes_touched_modules(self):
        self.assertEqual(
            _maven_scope(["mvn", "-B", "test"], ["svc-b", "svc-a"]),
            ["mvn", "-B", "test", "-pl", "svc-a,svc-b", "-am"],
        )

    def test_root_module_is_not_scoped(self):
        self.assertEqual(_maven_scope(["mvn", "test"], ["."]), ["mvn", "test"])
        self.assertEqual(_maven_scope(["mvn", "test"], []), ["mvn", "test"])

    def test_non_maven_untouched(self):
        self.assertEqual(_maven_scope(["gradle", "test"], ["svc-a"]), ["gradle", "test"])


class FailingGoalsTest(unittest.TestCase):
    def test_parses_gav_goal(self):
        out = (
            "[INFO] BUILD FAILURE\n"
            "[ERROR] Failed to execute goal org.jacoco:jacoco-maven-plugin:0.8.11:check "
            "(jacoco-check) on project x: Coverage checks have not been met.\n"
            "[ERROR] Failed to execute goal "
            "org.apache.maven.plugins:maven-checkstyle-plugin:3.3.1:check (validate) on project x\n"
        )
        self.assertEqual(
            _parse_failing_goals(out),
            [
                "org.apache.maven.plugins:maven-checkstyle-plugin:3.3.1:check",
                "org.jacoco:jacoco-maven-plugin:0.8.11:check",
            ],
        )

    def test_empty_on_clean_output(self):
        self.assertEqual(_parse_failing_goals("[INFO] BUILD SUCCESS"), [])
        self.assertEqual(_parse_failing_goals(""), [])


class DiscoverReportsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="greenwash-replay-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_finds_surefile_failsafe_and_gradle(self):
        for rel in (
            "mod-a/target/surefire-reports/TEST-a.Foo.xml",
            "mod-a/target/failsafe-reports/TEST-a.FooIT.xml",
            "mod-b/build/test-results/test/TEST-b.Bar.xml",
        ):
            p = Path(self.tmp, rel)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("<testsuite/>")
        found = discover_reports(self.tmp)
        self.assertEqual(len(found), 3)


class TimeoutTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="greenwash-replay-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_timeout_degrades(self):
        r = run_build(self.tmp, ["sleep", "5"], timeout_s=1, name="A")
        self.assertTrue(r.timed_out)
        self.assertNotEqual(r.exit_code, 0)
        self.assertFalse(r.ran_tests)

    def test_missing_build_tool_raises(self):
        with self.assertRaises(RuntimeError):
            run_build(self.tmp, ["definitely-not-a-real-binary-xyz"], timeout_s=5, name="A")


if __name__ == "__main__":
    unittest.main()
