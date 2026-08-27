"""Result comparison (REQUIREMENTS_1.md §6.4, FR-19..FR-25).

Parse JUnit XML from Surefire, Failsafe and Gradle report locations (FR-19). Identify
tests by (module, classname, name) — same-named classes in different modules are
distinct and must never be compared against one another (FR-20, DR-4). Report:
  - tests that pass only with test/config edits applied (FR-21)
  - build goals that fail under base config but pass under new config (FR-22)
  - tests newly skipped, and tests present at base but absent after; label a probable
    rename when a same-named counterpart appears under a different class (FR-23)
Attribute every finding to a module (FR-24). Distinguish "build never ran tests" from
"tests ran and failed" — the former is inconclusive, not a finding (FR-25).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Outcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class TestKey:
    module: str
    classname: str
    name: str


def parse_reports(report_paths: list[str]) -> dict[TestKey, Outcome]:
    raise NotImplementedError  # BUILD_PLAN.md §3 step 4


def compare(after: dict[TestKey, Outcome], source_only: dict[TestKey, Outcome]) -> list:
    """Return candidate findings from the A vs B per-test delta. Candidates go through
    flake confirmation (flake.py) before becoming reported findings."""
    raise NotImplementedError  # BUILD_PLAN.md §3 step 5
