"""The split-and-replay experiment (REQUIREMENTS_1.md §4.1).

Ties the deterministic core together: resolve the diff, classify it, and — only when a
test or config file changed (FR-13) — replay the build twice in isolated worktrees:
  A ("after"): head as-is
  B ("source-only"): head with every test/config path reverted to base content
then compare per-test outcomes and gate outcomes and reduce to a headline verdict.

No LLM, no network (NFR-1, NFR-2). Flake confirmation (FR-26) is wired in step 9; until
then per-test candidates pass straight through.
"""

from __future__ import annotations

from dataclasses import dataclass

from greenwash import classify, replay, reports, revisions
from greenwash.classify import Kind
from greenwash.config import Config
from greenwash.output import Report
from greenwash.verdict import resolve


@dataclass
class Options:
    repo_root: str
    range_spec: str | None = None
    commit: str | None = None
    build_command: list[str] | None = None
    timeout_s: int | None = None
    keep: bool = False


def _run_side(
    repo_root: str,
    ref: str,
    command: list[str],
    *,
    overlay: dict[str, bytes | None] | None,
    timeout_s: int,
    modules: list[str] | None,
    name: str,
    report_globs: tuple[str, ...],
    keep: bool,
):
    with revisions.worktree(repo_root, ref, overlay=overlay, keep=keep) as wt:
        result = replay.run_build(
            wt, command, timeout_s=timeout_s, modules=modules,
            name=name, report_globs=report_globs,
        )
        outcomes = reports.parse_reports(result.report_paths, wt)
    return result, outcomes


def verify(options: Options, config: Config) -> Report:
    repo_root = options.repo_root
    spec = revisions.resolve(repo_root, range_spec=options.range_spec, commit=options.commit)
    classifications = classify.classify(
        spec.changed_paths, repo_root, config.classification_overrides,
    )

    warnings: list[str] = [
        f"untracked file not audited: {p}" for p in spec.untracked_warnings
    ]
    if spec.has_adds_or_deletes:
        warnings.append(
            "a rename is reported as a deletion plus an addition (FR-10/FR-11)"
        )

    testish = [c for c in classifications if c.kind in (Kind.TEST, Kind.CONFIG)]
    if not testish:
        findings, head = resolve(
            test_or_config_changed=False, per_test_findings=[], gate_findings=[],
        )
        return Report(head, findings, classifications, warnings)

    command = options.build_command or config.build_command or list(replay.MAVEN_DEFAULT_CMD)
    timeout_s = options.timeout_s or config.timeout_s
    report_globs = tuple(config.report_globs)

    modules = None
    if config.module_scope:
        scoped = sorted({c.module for c in classifications if c.module != "."})
        modules = scoped or None

    common = dict(timeout_s=timeout_s, modules=modules,
                  report_globs=report_globs, keep=options.keep)

    a_result, a_outcomes = _run_side(
        repo_root, spec.head_ref, command, overlay=None, name="A", **common,
    )
    b_overlay = {
        c.path: revisions.read_blob(repo_root, spec.base_ref, c.path) for c in testish
    }
    b_result, b_outcomes = _run_side(
        repo_root, spec.head_ref, command, overlay=b_overlay, name="B", **common,
    )

    per_test = reports.compare(
        a_outcomes, b_outcomes,
        after_ran_tests=a_result.ran_tests,
        source_only_ran_tests=b_result.ran_tests,
    )
    gates = reports.compare_gates(a_result, b_result)

    # flake confirmation (FR-26) is step 9; candidates pass straight through for now
    surviving, demoted = per_test, []

    findings, head = resolve(
        test_or_config_changed=True,
        per_test_findings=surviving,
        gate_findings=gates,
        demoted_findings=demoted,
        source_only_compiled=not b_result.compile_failed,
        source_only_ran_tests=b_result.ran_tests,
    )
    return Report(head, findings, classifications, warnings)
