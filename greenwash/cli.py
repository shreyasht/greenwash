"""CLI entry (REQUIREMENTS_1.md §6.6, §6.7; NFR-4 fail open).

Arg parsing, input-mode selection, and the top-level fail-open wrapper: any internal
error exits 0 with a diagnostic on stderr (NFR-4). Exit codes are permanently stable
(§6.7) and come from verdict.EXIT_CODES with per-verdict overrides from config.
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="greenwash", description=__doc__)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--range", metavar="BASE..HEAD", help="verify a commit range")
    src.add_argument("--commit", metavar="SHA", help="verify a single commit")
    # default when neither is given: uncommitted working tree (FR-7)
    p.add_argument("--build-command", help="override the per-run build command")
    p.add_argument("--base-run", action="store_true", help="also run C at base (FR-14)")
    p.add_argument("--confirm-count", type=int, default=None, help="flake reruns per side (FR-26)")
    p.add_argument("--confirm-mode", choices=["isolated", "full"], default=None, help="FR-29")
    p.add_argument("--timeout", type=int, default=None, help="per-run timeout seconds (FR-16)")
    p.add_argument("--json", action="store_true", help="emit the machine-readable report")
    p.add_argument("--keep", action="store_true", help="do not delete worktrees (FR-18)")
    return p


def run(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)  # noqa: F841 — wired in BUILD_PLAN.md §3 step 7
    raise NotImplementedError


def main(argv: list[str]) -> int:
    try:
        return run(argv)
    except Exception as exc:  # NFR-4: fail open
        print(f"greenwash: internal error, exiting 0 without a verdict: {exc}", file=sys.stderr)
        return 0
