"""The split-and-replay experiment (REQUIREMENTS.md §4.1).

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

from astroturf import classify, flake, replay, reports, revisions, strictness
from astroturf.classify import Kind
from astroturf.config import Config
from astroturf.output import Report
from astroturf.verdict import Finding, Verdict, resolve


@dataclass
class Options:
    repo_root: str
    range_spec: str | None = None
    commit: str | None = None
    build_command: list[str] | None = None
    timeout_s: int | None = None
    confirm_count: int | None = None
    confirm_mode: str | None = None
    prefilter: bool | None = None
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

    diffs = revisions.unified_diff(
        repo_root, spec.base_ref, spec.head_ref, [c.path for c in testish]
    )

    prefilter = options.prefilter if options.prefilter is not None else config.prefilter
    if prefilter:
        analysis = strictness.analyse(
            [(c.path, c.kind.value, diffs.get(c.path, "")) for c in testish]
        )
        if not analysis["weakened_paths"] and not analysis["unrecognised"]:
            warnings.append(
                "replay skipped: the test/config changes show no strictness reduction "
                "under static analysis (--no-prefilter forces the replay)"
            )
            findings, head = resolve(
                test_or_config_changed=True, per_test_findings=[], gate_findings=[],
            )
            return Report(head, findings, classifications, warnings)

    command = (
        options.build_command
        or config.build_command
        or replay.default_build_command(repo_root)
    )
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

    # Gate observable (FR-22, §4.2): a goal that failed under base config but passes under
    # the new config. CONFIG_WEAKENED requires an actual config change — with none, there
    # is no "base config vs new config" to compare, so the observable is skipped entirely.
    # When there is a candidate (or run B never reached its gates), confirm it against a
    # config-only revert: head source + head tests + base config. A goal failing there
    # fails because of the config, not because reverting the test files tripped a
    # formatting / style gate (spotless, ktlint) on their base content.
    config_paths = [c for c in classifications if c.kind is Kind.CONFIG]
    gates: list[Finding] = []
    if config_paths:
        candidate_gates = reports.compare_gates(a_result, b_result)
        if candidate_gates or b_result.compile_failed or not b_result.ran_tests:
            cfg_overlay = {
                c.path: revisions.read_blob(repo_root, spec.base_ref, c.path)
                for c in config_paths
            }
            b_cfg, _ = _run_side(
                repo_root, spec.head_ref, command, overlay=cfg_overlay, name="B_cfg", **common,
            )
            gates = reports.compare_gates(a_result, b_cfg)
        else:
            gates = candidate_gates

    mode = flake.ConfirmMode(options.confirm_mode or config.confirm_mode)
    k = options.confirm_count if options.confirm_count is not None else config.confirm_count

    # Only the A-pass / B-fail finding goes through flake confirmation (FR-26). A vanished
    # or newly-skipped test is a structural fact, not a flaky outcome — it reports directly.
    fix_candidates = [f for f in per_test if f.verdict is Verdict.FIX_IS_IN_THE_TESTS]
    structural = [f for f in per_test if f.verdict is not Verdict.FIX_IS_IN_THE_TESTS]

    # Run C (§4.3): re-run each FIX_IS_IN_THE_TESTS candidate at base with nothing applied.
    # A candidate that passed at base was valid for the old contract — the head source
    # changed the behaviour it checks and the assertions were updated to match; that is a
    # legitimate co-change (TESTS_UPDATED_FOR_BEHAVIOR_CHANGE), not a propped-up test.
    # One already failing at base is the real FIX_IS_IN_THE_TESTS. Scoped to the candidate
    # tests, so a clean run pays nothing (NFR-7).
    behavior_change: list[Finding] = []
    if fix_candidates:
        base_specs = [(f.detail["classname"], f.detail["name"]) for f in fix_candidates]
        _, c_outcomes = _run_side(
            repo_root, spec.base_ref, replay.test_filter(command, base_specs),
            overlay=None, name="C", **common,
        )
        fix_candidates, behavior_change = reports.split_by_base(fix_candidates, c_outcomes)

    if fix_candidates and k > 0:
        def _confirm_runner(overlay):
            def run(scope):
                specs = None if scope is None else [(key.classname, key.name) for key in scope]
                with revisions.worktree(
                    repo_root, spec.head_ref, overlay=overlay, keep=options.keep
                ) as wt:
                    res = replay.run_build(
                        wt, replay.test_filter(command, specs), timeout_s=timeout_s,
                        modules=modules, name="confirm", report_globs=report_globs,
                    )
                    return reports.parse_reports(res.report_paths, wt)
            return run

        surviving, demoted = flake.confirm(
            fix_candidates, _confirm_runner(None), _confirm_runner(b_overlay),
            k=k, mode=mode,
        )
    else:
        surviving, demoted = fix_candidates, []

    confirmed_a_fix = bool(surviving)
    surviving = surviving + structural + behavior_change

    if confirmed_a_fix and mode is flake.ConfirmMode.ISOLATED:
        warnings.append(
            "per-test findings were confirmed with tests run in isolation, not under "
            "full-suite conditions; test-order and shared-state effects are "
            "indistinguishable from flakiness here (FR-29)"
        )

    findings, head = resolve(
        test_or_config_changed=True,
        per_test_findings=surviving,
        gate_findings=gates,
        demoted_findings=demoted,
        source_only_compiled=not b_result.compile_failed,
        source_only_ran_tests=b_result.ran_tests,
    )

    # Compile-wall fallback (§9, step 14 — candidate, pending the INCONCLUSIVE_COMPILE-rate
    # measurement): when the per-test comparison is impossible, attach the *suspected*
    # weakenings from static analysis. Informational only — not reproducible by two build
    # commands, so it never blocks (§5 blocking rule).
    if head is Verdict.INCONCLUSIVE_COMPILE:
        analysis = strictness.analyse([
            (c.path, c.kind.value, diffs.get(c.path, "")) for c in testish if c.kind is Kind.TEST
        ])
        module_of = {c.path: c.module for c in testish}
        for path, reasons in analysis["signals"].items():
            findings.append(Finding(Verdict.INCONCLUSIVE_COMPILE, module_of.get(path, "."), {
                "path": path,
                "suspected_weakening": reasons,
                "evidence": "static heuristic on the diff, not verified by replay (§9)",
            }))
        if analysis["signals"]:
            warnings.append(
                "base tests do not compile against the new source; the findings above are "
                "static heuristics, not experimental results (§9 fallback)"
            )

    return Report(head, findings, classifications, warnings)
