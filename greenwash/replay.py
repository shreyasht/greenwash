"""Replay execution (REQUIREMENTS_1.md §6.3, FR-12..FR-18).

Run A ("after"): all hunks applied.
Run B ("source-only"): test + config reverted to base.
Run C ("base", optional): nothing applied (FR-14) — strengthens the verdict.

Arbitrary user build command per run; ship a Maven default that tolerates test failures
without aborting the build (FR-12). Skip the replay when no test/config files changed
(FR-13). Per run capture: exit code, failing build-goal identifiers, all discoverable
test reports (FR-15). Configurable per-run timeout -> INCONCLUSIVE_BUILD (FR-16).
Optionally restrict the build to touched modules and dependents, e.g. `mvn -pl ... -am`
(FR-17) — the primary cost lever under NFR-7. Clean up worktrees on exit unless --keep
(FR-18).
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAVEN_DEFAULT_CMD = ["mvn", "-B", "-fae", "test"]  # -fae: fail at end, don't abort early


@dataclass
class RunResult:
    name: str  # "A" | "B" | "C"
    exit_code: int
    failing_goals: list[str] = field(default_factory=list)
    report_paths: list[str] = field(default_factory=list)
    timed_out: bool = False


def run_build(workdir: str, command: list[str], *, timeout_s: int, modules: list[str] | None = None) -> RunResult:
    raise NotImplementedError  # BUILD_PLAN.md §3 step 3
