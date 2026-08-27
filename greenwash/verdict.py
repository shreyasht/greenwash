"""Findings list -> headline verdict (REQUIREMENTS_1.md §4.3, §5).

A change can weaken a gate *and* prop up a test. greenwash emits a list of findings,
each categorised, plus a single headline verdict derived by precedence for exit-code
purposes. All findings appear in output regardless of the headline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    NO_TEST_CHANGES = "NO_TEST_CHANGES"
    HONEST_FIX = "HONEST_FIX"
    TESTS_REMOVED_OR_SKIPPED = "TESTS_REMOVED_OR_SKIPPED"
    CONFIG_WEAKENED = "CONFIG_WEAKENED"
    FIX_IS_IN_THE_TESTS = "FIX_IS_IN_THE_TESTS"
    INCONCLUSIVE_COMPILE = "INCONCLUSIVE_COMPILE"
    INCONCLUSIVE_FLAKY = "INCONCLUSIVE_FLAKY"
    INCONCLUSIVE_BUILD = "INCONCLUSIVE_BUILD"


# §5 verdict taxonomy. Blocking only where the finding is unambiguous and demonstrable
# (§5 blocking rule); everything else informs. Defaults; some are configurable via
# .greenwash.toml (DR-6 / FR-30).
EXIT_CODES: dict[Verdict, int] = {
    Verdict.NO_TEST_CHANGES: 0,
    Verdict.HONEST_FIX: 0,
    Verdict.TESTS_REMOVED_OR_SKIPPED: 0,
    Verdict.CONFIG_WEAKENED: 1,
    Verdict.FIX_IS_IN_THE_TESTS: 1,
    Verdict.INCONCLUSIVE_COMPILE: 0,
    Verdict.INCONCLUSIVE_FLAKY: 0,
    Verdict.INCONCLUSIVE_BUILD: 0,
}

# §4.3 precedence, highest first. The headline is the highest-precedence finding across
# all modules (DR-4) — one offending module fails the run.
PRECEDENCE: list[Verdict] = [
    Verdict.FIX_IS_IN_THE_TESTS,
    Verdict.CONFIG_WEAKENED,
    Verdict.TESTS_REMOVED_OR_SKIPPED,
    Verdict.INCONCLUSIVE_COMPILE,
    Verdict.INCONCLUSIVE_FLAKY,
    Verdict.INCONCLUSIVE_BUILD,
    Verdict.HONEST_FIX,
    Verdict.NO_TEST_CHANGES,
]


@dataclass
class Finding:
    verdict: Verdict
    module: str
    detail: dict = field(default_factory=dict)


def headline(findings: list[Finding]) -> Verdict:
    """Reduce findings to one headline verdict by §4.3 precedence."""
    raise NotImplementedError  # BUILD_PLAN.md §3 step 5
