"""Flake confirmation (REQUIREMENTS_1.md §6.5, FR-26..FR-29, DR-2).

Before a per-test finding is reported, confirm it by re-running that test in both A and B
configurations K additional times (default K=2, configurable). The finding survives only
if the A-pass / B-fail outcome is consistent across all confirmations (FR-26).

Confirmation re-runs are scoped to the candidate test set, never the full suite — cost
scales with finding count, not suite size (FR-27, NFR-7). A failed confirmation demotes
that finding, not the run; the headline becomes INCONCLUSIVE_FLAKY only when every
candidate is demoted (FR-28). Default runs tests in isolation, which differs from
full-suite conditions; output must say so, and --confirm-mode=full re-runs the whole
suite at proportional cost (FR-29).
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from astroturf.reports import Outcome, TestKey
from astroturf.verdict import Finding

_FAILING = frozenset({Outcome.FAIL, Outcome.ERROR})

# A confirmation runner: given the test scope (None = whole suite, FR-29 full mode),
# run one side once and return its per-test outcomes.
Runner = Callable[[list[TestKey] | None], dict[TestKey, Outcome]]


class ConfirmMode(str, Enum):
    ISOLATED = "isolated"
    FULL = "full"


def _key_of(finding: Finding) -> TestKey:
    return TestKey(finding.module, finding.detail["classname"], finding.detail["name"])


def confirm(
    candidates: list[Finding],
    run_after: Runner,
    run_source_only: Runner,
    *,
    k: int = 2,
    mode: ConfirmMode = ConfirmMode.ISOLATED,
) -> tuple[list[Finding], list[Finding]]:
    """Re-run the candidate per-test findings K times per side. A finding survives only
    if `after == pass and source_only in {fail, error}` on every one of the K rounds
    (the original comparison already established it once). Returns (surviving, demoted);
    demotion is per-finding, never per-run (FR-28)."""
    if not candidates or k <= 0:
        return list(candidates), []

    by_key = {_key_of(f): f for f in candidates}
    scope = None if mode is ConfirmMode.FULL else list(by_key)
    alive = dict.fromkeys(by_key, True)

    for _ in range(k):
        after = run_after(scope)
        source_only = run_source_only(scope)
        for key in by_key:
            if not (after.get(key) is Outcome.PASS and source_only.get(key) in _FAILING):
                alive[key] = False
        if not any(alive.values()):
            break

    surviving = [f for key, f in by_key.items() if alive[key]]
    demoted = [f for key, f in by_key.items() if not alive[key]]
    return surviving, demoted
