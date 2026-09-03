"""Replay execution tests (FR-12..FR-18). Pure helpers + a real timeout; no Maven."""

import shutil
import tempfile
import unittest
from pathlib import Path

from astroturf.replay import (
    MAVEN_DEFAULT_CMD,
    _is_gradle,
    _is_maven,
    _maven_scope,
    _parse_failing_goals,
    default_build_command,
    discover_reports,
    run_build,
    test_filter,
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


class TestFilterTest(unittest.TestCase):
    SPECS = [("com.x.CalcTest", "addsOne()"), ("com.x.CalcTest", "addsTwo")]

    def test_maven(self):
        out = test_filter(["mvn", "-B", "test"], self.SPECS)
        self.assertEqual(
            out,
            ["mvn", "-B", "test",
             "-Dtest=com.x.CalcTest#addsOne,com.x.CalcTest#addsTwo",
             "-DfailIfNoTests=false"],
        )

    def test_gradle(self):
        self.assertTrue(_is_gradle(["./gradlew", "test"]))
        out = test_filter(["./gradlew", "test"], self.SPECS[:1])
        self.assertEqual(out, ["./gradlew", "test", "--tests", "com.x.CalcTest.addsOne"])

    def test_none_or_empty_is_unchanged(self):
        self.assertEqual(test_filter(["mvn", "test"], None), ["mvn", "test"])
        self.assertEqual(test_filter(["mvn", "test"], []), ["mvn", "test"])

    def test_unknown_build_tool_unchanged(self):
        self.assertEqual(test_filter(["bazel", "test"], self.SPECS), ["bazel", "test"])


class DefaultBuildCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="astroturf-dbc-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _touch(self, name, mode=0o644):
        p = Path(self.tmp, name)
        p.write_text("")
        p.chmod(mode)

    def test_maven_when_no_gradle_marker(self):
        self._touch("pom.xml")
        self.assertEqual(default_build_command(self.tmp), list(MAVEN_DEFAULT_CMD))

    def test_no_markers_defaults_to_maven(self):
        self.assertEqual(default_build_command(self.tmp), list(MAVEN_DEFAULT_CMD))

    def test_gradle_wrapper(self):
        self._touch("build.gradle")
        self._touch("gradlew", mode=0o755)
        self.assertEqual(default_build_command(self.tmp)[0], "./gradlew")

    def test_gradle_without_wrapper_uses_bare_gradle(self):
        self._touch("build.gradle.kts")
        cmd = default_build_command(self.tmp)
        self.assertEqual(cmd[0], "gradle")
        self.assertIn("--continue", cmd)


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

    def test_parses_gradle_tasks(self):
        out = (
            "> Task :checkstyleMain FAILED\n"
            "Execution failed for task ':jacocoTestCoverageVerification'.\n"
            "> Task :test FAILED\n"           # test execution is not a gate
        )
        self.assertEqual(
            _parse_failing_goals(out),
            [":checkstyleMain", ":jacocoTestCoverageVerification"],
        )

    def test_maven_surefire_failure_is_not_a_gate(self):
        out = ("Failed to execute goal "
               "org.apache.maven.plugins:maven-surefire-plugin:3.2.5:test (default-test)\n")
        self.assertEqual(_parse_failing_goals(out), [])

    def test_compile_failure_is_not_a_gate(self):
        # a reverted test that won't compile against new source is the §9 compile wall
        # (INCONCLUSIVE_COMPILE), never CONFIG_WEAKENED — Maven and Gradle
        out = (
            "Failed to execute goal "
            "org.apache.maven.plugins:maven-compiler-plugin:3.11.0:testCompile (default-testCompile)\n"
            "> Task :compileTestJava FAILED\n"
        )
        self.assertEqual(_parse_failing_goals(out), [])


class DiscoverReportsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="astroturf-replay-")

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
        self.tmp = tempfile.mkdtemp(prefix="astroturf-replay-")

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
