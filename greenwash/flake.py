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

from enum import Enum


class ConfirmMode(str, Enum):
    ISOLATED = "isolated"
    FULL = "full"


def confirm(candidates: list, *, k: int = 2, mode: ConfirmMode = ConfirmMode.ISOLATED) -> tuple[list, list]:
    """Return (surviving_findings, demoted_findings)."""
    raise NotImplementedError  # BUILD_PLAN.md §3 step 9
