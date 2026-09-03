"""Output rendering (REQUIREMENTS.md §6.6, FR-31..FR-33).

Human-readable stdout naming specific tests and goals, not counts, grouped by module
(FR-31). Machine-readable JSON for CI carrying the full findings list and the headline
verdict separately (FR-32), with `schema_version` (int, starts at 1) (FR-33, §6.7).
Both include the classification so a user can see and dispute it (FR-5).

Field additions within a schema version are allowed; renames, retypes and removals are
not (§6.7).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from astroturf import JSON_SCHEMA_VERSION
from astroturf.classify import ClassifiedPath
from astroturf.verdict import PRECEDENCE, Finding, Verdict, exit_code


@dataclass
class Report:
    headline: Verdict
    findings: list[Finding]
    classifications: list[ClassifiedPath] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    schema_version: int = JSON_SCHEMA_VERSION


_HEADLINE_SUMMARY: dict[Verdict, str] = {
    Verdict.NO_TEST_CHANGES: "no test or config files changed; nothing to verify",
    Verdict.HONEST_FIX: "the source change satisfies the checks without the test or config edits",
    Verdict.TESTS_UPDATED_FOR_BEHAVIOR_CHANGE: (
        "the assertions changed alongside a real behaviour change in the source — they "
        "passed at base; verify the behaviour change is intended"
    ),
    Verdict.TESTS_REMOVED_OR_SKIPPED: "the source fix holds, but test coverage shrank in the same change",
    Verdict.CONFIG_WEAKENED: "a gate that failed under the base config passes under the new config",
    Verdict.FIX_IS_IN_THE_TESTS: "the source change alone does not make the named tests pass",
    Verdict.INCONCLUSIVE_COMPILE: "base tests do not compile against the new source; per-test comparison skipped",
    Verdict.INCONCLUSIVE_FLAKY: "every candidate finding failed flake confirmation",
    Verdict.INCONCLUSIVE_BUILD: "the build produced no reports; nothing to compare",
}


def _finding_subject(f: Finding) -> str:
    d = f.detail
    if "goal" in d:
        return str(d["goal"])
    if "classname" in d and "name" in d:
        return f"{d['classname']}.{d['name']}"
    if "path" in d:
        return str(d["path"])
    return d.get("reason", f.verdict.value)


def _finding_explanation(f: Finding) -> str:
    d = f.detail
    if f.verdict is Verdict.FIX_IS_IN_THE_TESTS:
        base = d.get("base")
        tail = f"; was already {base} at base" if base in ("fail", "error") else ""
        return ("passes with the test/config edits applied, fails without them "
                f"(source-only run){tail}")
    if f.verdict is Verdict.TESTS_UPDATED_FOR_BEHAVIOR_CHANGE:
        return "passed at base; fails when the test edits are reverted against the new source"
    if f.verdict is Verdict.CONFIG_WEAKENED:
        return "fails under the base config, passes under the new config"
    if f.verdict is Verdict.TESTS_REMOVED_OR_SKIPPED:
        return str(d.get("reason", "coverage shrank"))
    if "suspected_weakening" in d:
        return "; ".join(d["suspected_weakening"]) + "  [" + str(d.get("evidence", "")) + "]"
    return str(d.get("reason", ""))


def _finding_sort_key(f: Finding):
    return (PRECEDENCE.index(f.verdict), f.module, _finding_subject(f))


def _sorted_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=_finding_sort_key)


def render_json(report: Report, *, exit_overrides: dict[str, int] | None = None) -> str:
    code = exit_code(report.headline, exit_overrides)
    payload = {
        "schema_version": report.schema_version,
        "headline_verdict": report.headline.value,
        "blocking": code != 0,
        "exit_code": code,
        "findings": [
            {"verdict": f.verdict.value, "module": f.module, "detail": f.detail}
            for f in _sorted_findings(report.findings)
        ],
        "classifications": [
            {"path": c.path, "kind": c.kind.value, "module": c.module, "reason": c.reason}
            for c in sorted(report.classifications, key=lambda c: c.path)
        ],
        "warnings": sorted(report.warnings),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_human(report: Report, *, exit_overrides: dict[str, int] | None = None) -> str:
    code = exit_code(report.headline, exit_overrides)
    disposition = f"build fails: exit {code}" if code != 0 else f"build passes: exit {code}"
    lines = [
        f"astroturf: {report.headline.value}  ({disposition})",
        "",
        _HEADLINE_SUMMARY.get(report.headline, ""),
    ]

    findings = _sorted_findings(report.findings)
    if findings:
        lines += ["", "Findings:"]
        current_module = None
        for f in findings:
            if f.module != current_module:
                current_module = f.module
                lines += ["", f"  module {f.module}"]
            lines.append(f"    {f.verdict.value}  {_finding_subject(f)}")
            explanation = _finding_explanation(f)
            if explanation:
                lines.append(f"        {explanation}")

    if report.classifications:
        lines += ["", "Classification (dispute in .astroturf.toml):"]
        width = max(len(c.kind.value) for c in report.classifications)
        for c in sorted(report.classifications, key=lambda c: (c.module, c.path)):
            lines.append(f"  {c.kind.value:<{width}}  {c.path}    {c.reason}")

    if report.warnings:
        lines += ["", "Warnings:"]
        lines += [f"  - {w}" for w in sorted(report.warnings)]

    return "\n".join(lines) + "\n"


def render(report: Report, *, as_json: bool = False, exit_overrides: dict[str, int] | None = None) -> str:
    fn = render_json if as_json else render_human
    return fn(report, exit_overrides=exit_overrides)
