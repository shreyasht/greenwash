"""Findings list -> headline verdict (REQUIREMENTS_1.md §4.3, §5).

A change can weaken a gate *and* prop up a test. astroturf emits a list of findings,
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
# .astroturf.toml (DR-6 / FR-30).
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
    """Reduce findings to one headline verdict by §4.3 precedence (highest wins across
    all modules, DR-4). An empty list means test/config changed but nothing was wrong."""
    present = {f.verdict for f in findings}
    for verdict in PRECEDENCE:
        if verdict in present:
            return verdict
    return Verdict.HONEST_FIX


def exit_code(verdict: Verdict, overrides: dict[str, int] | None = None) -> int:
    """§6.7: exit codes are permanently stable. Per-verdict overrides come from
    .astroturf.toml (FR-30); CONFIG_WEAKENED and TESTS_REMOVED_OR_SKIPPED are the
    configurable ones in practice."""
    if overrides and verdict.value in overrides:
        return overrides[verdict.value]
    return EXIT_CODES[verdict]


def is_blocking(verdict: Verdict, overrides: dict[str, int] | None = None) -> bool:
    return exit_code(verdict, overrides) != 0


def resolve(
    *,
    test_or_config_changed: bool,
    per_test_findings: list[Finding],
    gate_findings: list[Finding],
    demoted_findings: list[Finding] | None = None,
    source_only_compiled: bool = True,
    source_only_ran_tests: bool = True,
) -> tuple[list[Finding], Verdict]:
    """Assemble the full findings list (real + synthetic state findings) and the headline.

    `per_test_findings` are the survivors of flake confirmation; `demoted_findings` are
    the per-test candidates that failed it (FR-28). `gate_findings` never go through
    confirmation. The compile wall (§9) only blocks the per-test observable — a gate
    finding still outranks INCONCLUSIVE_COMPILE by precedence.
    """
    demoted_findings = demoted_findings or []
    findings: list[Finding] = [*per_test_findings, *gate_findings]

    if not test_or_config_changed:
        return findings, Verdict.NO_TEST_CHANGES

    if not source_only_compiled:
        findings.append(Finding(
            Verdict.INCONCLUSIVE_COMPILE, ".",
            {"reason": "base tests do not compile against the new source (§9)"},
        ))
    elif not source_only_ran_tests and not gate_findings:
        findings.append(Finding(
            Verdict.INCONCLUSIVE_BUILD, ".",
            {"reason": "the source-only run produced no test reports"},
        ))

    if demoted_findings and not per_test_findings and not gate_findings and source_only_compiled:
        findings.append(Finding(
            Verdict.INCONCLUSIVE_FLAKY, ".",
            {"reason": "every candidate finding failed flake confirmation (FR-28)",
             "demoted": len(demoted_findings)},
        ))

    return findings, headline(findings)
