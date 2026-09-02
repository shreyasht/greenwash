"""Claude Code `Stop` hook (REQUIREMENTS_1.md FR-36, §10 surface 3).

Runs astroturf on the working tree when the agent tries to end its turn. On a blocking
verdict it returns a `block` decision with the verdict text, so the agent is handed the
reason and retries with no human in the loop. Every other verdict, and any error, lets
the agent stop (NFR-4 fail open).

Wired via settings.json — see hooks/claude-stop-hook/README.md.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

BLOCK_GUIDANCE = {
    "FIX_IS_IN_THE_TESTS": (
        "The source change alone does not make these tests pass — the fix is in the test "
        "files. Move it into the source and run astroturf again."
    ),
    "CONFIG_WEAKENED": (
        "A gate that failed under the base config passes under your config change. "
        "Restore the gate, or take the change to a human reviewer."
    ),
}


def format_reason(report: dict) -> str:
    verdict = report.get("headline_verdict", "?")
    lines = [f"astroturf blocked completion: {verdict}."]
    for finding in report.get("findings", []):
        detail = finding.get("detail", {})
        subject = detail.get("goal") or ".".join(
            part for part in (detail.get("classname"), detail.get("name")) if part
        )
        lines.append(
            f"  - [{finding.get('verdict')}] {finding.get('module', '.')}: "
            f"{subject or '(see the JSON report)'}"
        )
    if verdict in BLOCK_GUIDANCE:
        lines.append(BLOCK_GUIDANCE[verdict])
    return "\n".join(lines)


def evaluate(report: dict | None, *, stop_hook_active: bool) -> dict | None:
    """The Claude Code Stop-hook decision, or None to allow the stop. `stop_hook_active`
    means this hook already fired once this turn — never block twice, or the agent is
    trapped."""
    if stop_hook_active or not report or not report.get("blocking"):
        return None
    return {"decision": "block", "reason": format_reason(report)}


def _run_astroturf(cwd: str, timeout: int) -> dict | None:
    try:
        proc = subprocess.run(
            ["astroturf", "--json"], cwd=cwd,
            capture_output=True, text=True, timeout=timeout,
        )
        return json.loads(proc.stdout)
    except Exception:
        return None


def main(stdin_text: str | None = None, *, runner=_run_astroturf) -> int:
    try:
        raw = stdin_text if stdin_text is not None else sys.stdin.read()
        payload = json.loads(raw)
    except Exception:
        payload = {}

    report = runner(
        payload.get("cwd") or os.getcwd(),
        int(os.environ.get("ASTROTURF_HOOK_TIMEOUT", "1800")),
    )
    decision = evaluate(report, stop_hook_active=bool(payload.get("stop_hook_active")))
    if decision is not None:
        print(json.dumps(decision))
    return 0  # blocking is signalled via the JSON decision, never the exit code (NFR-4)


def _console() -> None:
    sys.exit(main())
