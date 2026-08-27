"""Output rendering (REQUIREMENTS_1.md §6.6, FR-31..FR-33).

Human-readable stdout naming specific tests and goals, not counts, grouped by module
(FR-31). Machine-readable JSON for CI carrying the full findings list and the headline
verdict separately (FR-32), with `schema_version` (int, starts at 1) (FR-33, §6.7).
"""

from __future__ import annotations

import json

from greenwash import JSON_SCHEMA_VERSION
from greenwash.verdict import Finding, Verdict


def render_human(findings: list[Finding], head: Verdict) -> str:
    raise NotImplementedError  # BUILD_PLAN.md §3 step 6


def render_json(findings: list[Finding], head: Verdict) -> str:
    payload = {
        "schema_version": JSON_SCHEMA_VERSION,
        "headline_verdict": head.value,
        "findings": [],  # BUILD_PLAN.md §3 step 6
    }
    return json.dumps(payload, indent=2, sort_keys=True)
