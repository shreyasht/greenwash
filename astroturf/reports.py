"""Result comparison (REQUIREMENTS_1.md §6.4, FR-19..FR-25).

Parse JUnit XML from Surefire, Failsafe and Gradle report locations (FR-19). Identify
tests by (module, classname, name) — same-named classes in different modules are
distinct and must never be compared against one another (FR-20, DR-4); module is derived
from the report's location. Compare run A ("after", all hunks) against run B
("source-only", test + config reverted) and emit candidate findings:
  - tests that pass only with the test/config edits applied (FR-21)
  - build goals that fail under base config but pass under new config (FR-22)
  - tests newly skipped, and tests present at base but absent after, with probable-rename
    labelling (FR-23)
Every finding carries its module (FR-24). "Build never ran tests" is not a finding
(FR-25) — the caller guards on RunResult.ran_tests before comparing.

Candidates returned here still go through flake confirmation (flake.py) before they are
reported.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum

from astroturf.replay import RunResult
from astroturf.verdict import Finding, Verdict


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


_RANK = {Outcome.PASS: 0, Outcome.SKIPPED: 1, Outcome.FAIL: 2, Outcome.ERROR: 3}
_FAILING = frozenset({Outcome.FAIL, Outcome.ERROR})


def _worst(a: Outcome | None, b: Outcome) -> Outcome:
    if a is None:
        return b
    return a if _RANK[a] >= _RANK[b] else b


def _module_from_report(path: str, workdir: str) -> str:
    rel = os.path.relpath(path, workdir).replace(os.sep, "/")
    for marker in ("/target/", "/build/"):
        idx = rel.find(marker)
        if idx != -1:
            return rel[:idx] or "."
    return "."


def _outcome_of(testcase: ET.Element) -> Outcome:
    if testcase.find("error") is not None:
        return Outcome.ERROR
    if testcase.find("failure") is not None:
        return Outcome.FAIL
    if testcase.find("skipped") is not None:
        return Outcome.SKIPPED
    return Outcome.PASS


def _parse_file(path: str, module: str) -> dict[TestKey, Outcome]:
    out: dict[TestKey, Outcome] = {}
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return out
    for suite in root.iter("testsuite"):
        suite_name = suite.get("name", "")
        for tc in suite.findall("testcase"):
            name = tc.get("name") or ""
            if not name:
                continue
            key = TestKey(module, tc.get("classname") or suite_name, name)
            out[key] = _worst(out.get(key), _outcome_of(tc))
    return out


def parse_reports(report_paths: list[str], workdir: str) -> dict[TestKey, Outcome]:
    merged: dict[TestKey, Outcome] = {}
    for path in report_paths:
        module = _module_from_report(path, workdir)
        for key, outcome in _parse_file(path, module).items():
            merged[key] = _worst(merged.get(key), outcome)
    return merged


def compare(
    after: dict[TestKey, Outcome],
    source_only: dict[TestKey, Outcome],
    *,
    after_ran_tests: bool = True,
    source_only_ran_tests: bool = True,
) -> list[Finding]:
    """Candidate per-test findings from the A vs B delta (FR-21, FR-23)."""
    findings: list[Finding] = []

    for key, a in after.items():
        b = source_only.get(key)
        if a is Outcome.PASS and b in _FAILING:
            findings.append(Finding(Verdict.FIX_IS_IN_THE_TESTS, key.module, {
                "classname": key.classname,
                "name": key.name,
                "after": a.value,
                "source_only": b.value,
            }))
        elif a is Outcome.SKIPPED and b is not None and b is not Outcome.SKIPPED:
            findings.append(Finding(Verdict.TESTS_REMOVED_OR_SKIPPED, key.module, {
                "classname": key.classname,
                "name": key.name,
                "reason": "newly skipped",
                "source_only": b.value,
            }))

    if after_ran_tests and source_only_ran_tests:
        for key in source_only:
            if key in after:
                continue
            probable_rename = any(
                k.module == key.module and k.name == key.name and k.classname != key.classname
                for k in after
            )
            probable_move = any(
                k.classname == key.classname and k.name == key.name and k.module != key.module
                for k in after
            )
            if probable_rename:
                reason = "probable rename"
            elif probable_move:
                reason = "probable module move (open question 1)"
            else:
                reason = "present at base, absent after"
            findings.append(Finding(Verdict.TESTS_REMOVED_OR_SKIPPED, key.module, {
                "classname": key.classname,
                "name": key.name,
                "reason": reason,
                "probable_rename": probable_rename,
                "probable_move": probable_move,
            }))

    return findings


def split_by_base(
    fix_findings: list[Finding], base_outcomes: dict[TestKey, Outcome]
) -> tuple[list[Finding], list[Finding]]:
    """Partition FIX_IS_IN_THE_TESTS candidates by their outcome at base (run C, §4.3).

    A candidate that *passed at base* was a valid check for the old contract; the head
    source changed the behaviour it exercises and the assertions were updated to match.
    That is a legitimate co-change — reclassify to TESTS_UPDATED_FOR_BEHAVIOR_CHANGE
    (non-blocking). A candidate that was *already failing at base* (or cannot be run
    there) is the real thing: the source change did not make it pass, only the test edit
    did. It stays FIX_IS_IN_THE_TESTS.

    Returns (still_fix, behavior_change).
    """
    still_fix: list[Finding] = []
    behavior_change: list[Finding] = []
    for f in fix_findings:
        key = TestKey(f.module, f.detail["classname"], f.detail["name"])
        at_base = base_outcomes.get(key)
        if at_base is Outcome.PASS:
            behavior_change.append(Finding(
                Verdict.TESTS_UPDATED_FOR_BEHAVIOR_CHANGE, f.module, {
                    **f.detail,
                    "base": Outcome.PASS.value,
                    "reason": "passed at base; the head source changed the behaviour it checks",
                },
            ))
        else:
            f.detail["base"] = at_base.value if at_base is not None else "absent"
            still_fix.append(f)
    return still_fix, behavior_change


def _gate_module(goal: str) -> str:
    """Best-effort module for a failing goal. Gradle task path ':sub:task' -> 'sub';
    ':task' or a Maven GAV:goal -> '.'. Maven multi-module attribution needs pom
    parsing and is not done yet (FR-24)."""
    if goal.startswith(":"):
        parts = goal.strip(":").split(":")
        if len(parts) >= 2:
            return ":".join(parts[:-1])
    return "."


def compare_gates(after: RunResult, source_only: RunResult) -> list[Finding]:
    """Candidate gate findings (FR-22): a goal that failed under base config and no longer
    fails under the new config. Gate detection is a consequence of the replay, not a
    parse of pom.xml (§4.2)."""
    after_failing = set(after.failing_goals)
    weakened = sorted(g for g in source_only.failing_goals if g not in after_failing)
    return [
        Finding(Verdict.CONFIG_WEAKENED, _gate_module(goal), {
            "goal": goal,
            "failed_at_base": True,
            "passes_after": True,
        })
        for goal in weakened
    ]
