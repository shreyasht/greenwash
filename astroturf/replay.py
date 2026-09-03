"""Replay execution (REQUIREMENTS.md §6.3, FR-12..FR-18).

Run A ("after"): all hunks applied.
Run B ("source-only"): test + config reverted to base.
Run C ("base", optional): nothing applied (FR-14) — strengthens the verdict.

Each run executes a build command in an isolated worktree (see revisions.worktree) and
captures exit code, failing build-goal identifiers, and every discoverable test report
(FR-15). The shipped Maven default tolerates test failures so later gates still run and
their outcomes stay visible (FR-12). A per-run timeout degrades the run to
INCONCLUSIVE_BUILD (FR-16). Where the build tool supports it, the build is scoped to the
touched modules and their dependents via `-pl … -am` (FR-17), the primary cost lever
under NFR-7. Worktree cleanup is the caller's responsibility (FR-18).
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# -Dmaven.test.failure.ignore=true: unit-test failures are recorded in the XML reports
# but do not abort the build, so gate goals (jacoco:check, checkstyle:check, enforce, …)
# still execute and their pass/fail stays observable. The per-test observable reads the
# XML, not the exit code. v0.2 gate work may move the phase to `verify`; users override
# the whole command via .astroturf.toml (FR-30).
MAVEN_DEFAULT_CMD = ["mvn", "-B", "-Dmaven.test.failure.ignore=true", "test"]

# --continue: keep running later tasks after one fails, so gate tasks
# (jacocoTestCoverageVerification, checkstyleMain, …) stay observable. Gradle always
# runs every test in the `test` task and writes the XML regardless of pass/fail.
GRADLE_DEFAULT_CMD = ["./gradlew", "test", "--continue", "--console=plain"]

_GRADLE_MARKERS = ("gradlew", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts")

REPORT_GLOBS = (
    "**/target/surefire-reports/*.xml",
    "**/target/failsafe-reports/*.xml",
    "**/build/test-results/**/*.xml",  # Gradle
)

TIMEOUT_EXIT = 124

_GOAL_RE = re.compile(r"Failed to execute goal ([\w.\-]+:[\w.\-]+:[\w.\-]+:[\w.\-]+)")
# Gradle: "Execution failed for task ':x'." and "> Task :x FAILED"
_GRADLE_TASK_RE = re.compile(r"Execution failed for task '(:[\w:.\-]+)'|> Task (:[\w:.\-]+) FAILED")
# Test-execution goals/tasks are the per-test observable's domain, and compile goals
# are the §9 compile wall's (a reverted test that won't compile against new source is
# INCONCLUSIVE_COMPILE, never CONFIG_WEAKENED). Excluding both keeps CONFIG_WEAKENED
# off the false-positive budget (NFR-6).
_NON_GATE_RE = re.compile(
    r"maven-(surefire|failsafe|compiler)-plugin|"
    r"(?:^|:)(test|integrationTest|intTest|functionalTest"
    r"|compile|testCompile|compileJava|compileTestJava)$|Test$"
)
_COMPILE_FAIL_RE = re.compile(
    r"COMPILATION ERROR|BUILD FAILED.*compileTest|compileTest\w*\s+FAILED|"
    r"cannot find symbol|error: .* is not abstract",
)


@dataclass
class RunResult:
    name: str  # "A" | "B" | "C"
    exit_code: int
    failing_goals: list[str] = field(default_factory=list)
    report_paths: list[str] = field(default_factory=list)
    timed_out: bool = False
    compile_failed: bool = False  # §9 compile wall — base tests won't compile vs new source

    @property
    def ran_tests(self) -> bool:
        """FR-25: distinguish 'build never ran tests' from 'tests ran and failed'."""
        return bool(self.report_paths)


def default_build_command(repo_root: str) -> list[str]:
    """Pick a default build command by build-tool markers at the repo root (FR-12).
    Gradle if a gradle marker is present, otherwise Maven. Uses `./gradlew` when the
    wrapper exists, else a bare `gradle`."""
    root = Path(repo_root)
    if any((root / marker).exists() for marker in _GRADLE_MARKERS):
        cmd = list(GRADLE_DEFAULT_CMD)
        if not (root / "gradlew").is_file():
            cmd[0] = "gradle"
        return cmd
    return list(MAVEN_DEFAULT_CMD)


def discover_reports(workdir: str, extra_globs: tuple[str, ...] = ()) -> list[str]:
    root = Path(workdir)
    found: set[str] = set()
    for glob in (*REPORT_GLOBS, *extra_globs):
        for p in root.glob(glob):
            if p.is_file():
                found.add(str(p))
    return sorted(found)


def _parse_failing_goals(output: str) -> list[str]:
    """Identifiers of build goals/tasks that failed (FR-15), Maven and Gradle, with
    test-execution goals filtered out (those are the per-test observable's job)."""
    text = output or ""
    goals = set(_GOAL_RE.findall(text))
    for a, b in _GRADLE_TASK_RE.findall(text):
        goals.add(a or b)
    return sorted(g for g in goals if not _NON_GATE_RE.search(g))


def _is_maven(command: list[str]) -> bool:
    return os.path.basename(command[0]).lower().startswith(("mvn", "mvnw"))


def _is_gradle(command: list[str]) -> bool:
    return "gradle" in os.path.basename(command[0]).lower()


def test_filter(command: list[str], specs: list[tuple[str, str]] | None) -> list[str]:
    """Restrict a build to specific (classname, method) tests for flake confirmation
    (FR-27). `specs` None/empty -> command unchanged (full suite). Maven:
    `-Dtest=Class#method`; Gradle: `--tests 'fqcn.method'`. Other build tools: unchanged.
    """
    if not specs:
        return list(command)
    methods = [(cls, name.rstrip("()")) for cls, name in specs]
    if _is_maven(command):
        joined = ",".join(f"{cls}#{name}" for cls, name in methods)
        return [*command, f"-Dtest={joined}", "-DfailIfNoTests=false"]
    if _is_gradle(command):
        out = list(command)
        for cls, name in methods:
            out += ["--tests", f"{cls}.{name}"]
        return out
    return list(command)


def _maven_scope(command: list[str], modules: list[str] | None) -> list[str]:
    """Append `-pl a,b -am` for Maven when specific (non-root) modules are touched (FR-17)."""
    if not modules or not _is_maven(command):
        return list(command)
    scoped = sorted(m for m in modules if m and m != ".")
    if not scoped:
        return list(command)
    return [*command, "-pl", ",".join(scoped), "-am"]


def run_build(
    workdir: str,
    command: list[str],
    *,
    timeout_s: int,
    modules: list[str] | None = None,
    name: str = "",
    report_globs: tuple[str, ...] = (),
) -> RunResult:
    argv = _maven_scope(command, modules)
    try:
        proc = subprocess.run(
            argv,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=os.environ.copy(),
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        reports = discover_reports(workdir, report_globs)
        return RunResult(
            name=name,
            exit_code=proc.returncode,
            failing_goals=_parse_failing_goals(output),
            report_paths=reports,
            timed_out=False,
            compile_failed=not reports and bool(_COMPILE_FAIL_RE.search(output)),
        )
    except subprocess.TimeoutExpired as exc:
        partial = ""
        for chunk in (exc.stdout, exc.stderr):
            if chunk:
                partial += chunk if isinstance(chunk, str) else chunk.decode("utf-8", "replace")
        return RunResult(
            name=name,
            exit_code=TIMEOUT_EXIT,
            failing_goals=_parse_failing_goals(partial),
            report_paths=discover_reports(workdir, report_globs),
            timed_out=True,
        )
    except FileNotFoundError as exc:
        # build tool not on PATH — fail open at the CLI layer (NFR-4)
        raise RuntimeError(f"build command not found: {argv[0]!r}") from exc
