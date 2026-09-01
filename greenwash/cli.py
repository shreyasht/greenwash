"""CLI entry (REQUIREMENTS_1.md §6.6, §6.7; NFR-4 fail open).

Arg parsing, input-mode selection, and the top-level fail-open wrapper: any internal
error exits 0 with a diagnostic on stderr (NFR-4). Exit codes are permanently stable
(§6.7) and come from verdict.exit_code with per-verdict overrides from config.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys

from greenwash import config as config_mod
from greenwash import orchestrate, output, verdict


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="greenwash", description=__doc__)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--range", metavar="BASE..HEAD", help="verify a commit range")
    src.add_argument("--commit", metavar="SHA", help="verify a single commit")
    # default when neither is given: uncommitted working tree (FR-7)
    p.add_argument("--build-command", help="override the per-run build command")
    p.add_argument("--timeout", type=int, default=None, help="per-run timeout seconds (FR-16)")
    p.add_argument("--confirm-count", type=int, default=None,
                   help="flake confirmation re-runs per side (FR-26; 0 disables)")
    p.add_argument("--confirm-mode", choices=["isolated", "full"], default=None,
                   help="confirm candidate tests in isolation or via the full suite (FR-29)")
    p.add_argument("--json", action="store_true", help="emit the machine-readable report")
    p.add_argument("--keep", action="store_true", help="do not delete worktrees (FR-18)")
    return p


def run(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    repo_root = os.getcwd()
    config = config_mod.load(repo_root)

    options = orchestrate.Options(
        repo_root=repo_root,
        range_spec=args.range,
        commit=args.commit,
        build_command=shlex.split(args.build_command) if args.build_command else None,
        timeout_s=args.timeout,
        confirm_count=args.confirm_count,
        confirm_mode=args.confirm_mode,
        keep=args.keep,
    )
    report = orchestrate.verify(options, config)
    print(output.render(report, as_json=args.json, exit_overrides=config.exit_overrides), end="")
    return verdict.exit_code(report.headline, config.exit_overrides)


def main(argv: list[str]) -> int:
    try:
        return run(argv)
    except Exception as exc:  # NFR-4: fail open
        print(f"greenwash: internal error, exiting 0 without a verdict: {exc}", file=sys.stderr)
        return 0


def _console() -> None:
    """Entry point for the installed `greenwash` command."""
    sys.exit(main(sys.argv[1:]))
