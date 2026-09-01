# greenwash — Agentic Build Plan

**Status:** steps 1-14 code-complete, green on CI (branch `scaffold-v0.1`, not yet
merged). Outstanding: the two human measurements in §4 (§9 INCONCLUSIVE_COMPILE rate,
NFR-6 false-positive budget), which gate finalising step 14 and the v0.4 release claims.
**Purpose:** drive the v0.1 → v0.3 implementation with a coding agent, from
`REQUIREMENTS_1.md`, without the agent drifting off-spec or hacking its own tests.
**Last updated:** 2026-08-27

Read `REQUIREMENTS_1.md` first. This document is the *how to build it*; that one is
the *what*. FR / NFR / § references below point into it.

---

## 0. Guardrails (write these into `CLAUDE.md` before writing any code)

The agent will lose these mid-run. They must live in a file it reloads every session.

- **Python stdlib only** (NFR-3). No pip, no third-party imports, no venv requirement.
  Must run behind a corporate proxy with zero package access.
- **No LLM in `greenwash/` source** (NFR-1). The verification path is deterministic.
  An LLM may assist explanation later, never judgement.
- **No network calls, no telemetry, no API keys** (NFR-2).
- **Fail open** (NFR-4): a top-level `except` in the CLI exits `0` with a diagnostic
  on stderr. The tool must never be why a build breaks.
- **Non-destructive** (NFR-5): never mutate the user's working tree, index, or stash.
  All runs happen in isolated `git worktree` checkouts.
- **Fixtures are ground truth.** The agent may **never** edit a fixture's assertions,
  expected verdict, or planted diff to make a test pass. This is exactly the reward-hack
  greenwash exists to detect — doing it here invalidates the whole project.

### Open decision — config file format

`.greenwash.yml` (FR-30) implies YAML, but there is no YAML parser in the stdlib.
Options, pick one and record it in a decision note:

1. Use TOML, `.greenwash.toml`, parsed with `tomllib` (stdlib since Python 3.11).
   Cleanest. Costs a rename away from the spec's `.greenwash.yml`.
2. Hand-write a parser for a restricted YAML subset (scalars, one-level maps, lists).
   Keeps the spec name. More code to maintain and test.
3. Support both filenames, TOML semantics.

Recommendation: **option 1**, note it as a decision record amendment to §12.

---

## 1. Fixture corpus — build this BEFORE any verifier code

Spec: v0.1 is "validated against four planted scenarios" (§8). These fixtures *are*
the regression suite (§11) and the agent's ground truth. Each fixture is a minimal
self-contained Maven project plus a diff (two commits, or a base + a patch file).

### v0.1 fixtures

| Fixture | Planted diff | Expected headline verdict |
| --- | --- | --- |
| `honest-fix` | real bug fix in `src/main` + a matching test edit | `HONEST_FIX` |
| `fix-in-tests` | assertion flipped / expected value hardcoded, no real source fix | `FIX_IS_IN_THE_TESTS` |
| `tests-removed` | real source fix + a test method deleted or `@Disabled` | `TESTS_REMOVED_OR_SKIPPED` |
| `no-test-changes` | `src/main` only | `NO_TEST_CHANGES` |

### v0.2 fixtures (add when starting v0.2)

| Fixture | Planted diff | Expected |
| --- | --- | --- |
| `config-weakened` | JaCoCo `jacoco:check` threshold lowered so a failing gate now passes | `CONFIG_WEAKENED` |
| `lint-disabled` | Checkstyle/SpotBugs rule disabled in config | `CONFIG_WEAKENED` |
| `flaky-candidate` | a test whose A-pass / B-fail outcome is inconsistent across reruns | finding demoted; `INCONCLUSIVE_FLAKY` if it is the only candidate |
| `multi-module` | two modules, same-named test class in each, finding in one only | per-module finding, headline = highest precedence |

### v0.3 fixtures

| Fixture | Planted diff | Expected |
| --- | --- | --- |
| `compile-wall` | source signature change that breaks base tests when reverted | `INCONCLUSIVE_COMPILE` |
| `no-strictness-reduction` | test edit that only tightens / adds assertions | pre-filter skips the replay |

Each fixture ships an expected-output file (JSON, `schema_version` 1) checked byte-for-byte
minus timestamps.

---

## 2. Module layout

```
greenwash/
  __init__.py
  __main__.py        # python -m greenwash
  cli.py             # arg parsing, top-level fail-open wrapper, exit codes (§6.7)
  classify.py        # FR-1..6  : path -> source|test|config|neutral, attributed to module
  revisions.py       # FR-7..11 : input modes, git worktree setup/teardown, untracked warn
  replay.py          # FR-12..18: run A / run B / optional run C, per-run capture, timeout
  reports.py         # FR-19..25: JUnit XML discovery + parse, (module,classname,name) keys
  flake.py           # FR-26..29: K confirmation reruns per side, per-finding demotion
  verdict.py         # §4.3     : findings list -> headline verdict by precedence
  output.py          # FR-31..33: human stdout (names, not counts) + versioned JSON
  config.py          # FR-30    : load .greenwash.toml, apply overrides
fixtures/            # section 1
tests/               # stdlib unittest (NOT pytest — no third-party deps)
hooks/
  github-actions/    # FR-35
  pre-commit         # FR-35
  claude-stop-hook/  # FR-36 — the differentiating integration (§10 surface 3)
docs/
  decisions.md       # amendments to REQUIREMENTS_1.md §12
```

---

## 3. Implementation order (one vertical slice per step)

Each step: write / extend a fixture-driven test, implement, run the **full** `tests/`
suite, commit only if green.

1. **`revisions.py`** — worktree isolation. Ship the NFR-5 property test immediately:
   working tree, index, and `git stash list` are byte-identical before and after a run.
   Everything else depends on this being trustworthy.
2. **`classify.py`** — path buckets from Maven/Gradle convention (FR-2), config detection
   (FR-3), module attribution (FR-6), per-repo overrides (FR-4), reported in output (FR-5).
3. **`replay.py`** — run A (all hunks) and run B (test+config reverted to base). Arbitrary
   user build command with a Maven default that tolerates test failures (FR-12). Timeout
   to `INCONCLUSIVE_BUILD` (FR-16). Module-scoped builds `mvn -pl … -am` (FR-17).
4. **`reports.py`** — discover and parse Surefire/Failsafe/Gradle JUnit XML. Test identity
   `(module, classname, name)` (FR-20). Distinguish "tests never ran" from "ran and failed"
   (FR-25).
5. **`verdict.py`** — compare A vs B, emit findings, derive headline by the §4.3 precedence
   chain. Blocking only on `FIX_IS_IN_THE_TESTS` and `CONFIG_WEAKENED` (§5 blocking rule).
6. **`output.py`** — human stdout naming specific tests/goals grouped by module (FR-31);
   JSON with findings list and headline separate (FR-32), `schema_version: 1` (FR-33).
7. **`cli.py` + `config.py`** — wire input modes, exit codes (§6.7), fail-open wrapper.
   → **v0.1 done** when all four v0.1 fixtures produce their expected verdict.
8. **Gate observable** — extend `replay`/`reports`/`verdict` for `CONFIG_WEAKENED`:
   config-only revert (no test compilation needed), goal-identifier diffing (FR-22).
9. **`flake.py`** — K-rerun confirmation scoped to candidate tests (FR-26..28),
   `--confirm-mode=full` (FR-29).
10. **Multi-module** — per-module findings, headline = highest precedence across modules
    (DR-4), probable-rename / probable-move labelling (FR-23, open question 1).
11. **Config file, versioned JSON, Gradle paths, GH Actions workflow.**
    → **v0.2 done** when it runs unattended on one real repo for two weeks (§8).
12. **Claude Code Stop hook** (FR-36) — returns the verdict to the agent so it self-corrects
    before reporting success. See section 5.
13. **Static pre-filter** — skip the replay when the diff contains no strictness reduction
    (§8 v0.3). Pattern matching decides *when* to run, never *what the finding is* (§4.1).
14. **Compile-failure fallback** — design only after the measurement in section 4.
    → **v0.3 done.**

---

## 4. Human-only task — cannot be delegated to the agent

**§9 compile wall measurement.** Before the v0.3 fallback is designed:

- Run v0.1 against **≥100 real commits** that touch both `src/main` and `src/test`.
- Record the `INCONCLUSIVE_COMPILE` rate.
- If it fires on most commits, the per-test observable does not work on Java and the
  fallback (AST assertion-strictness diff, §9) becomes load-bearing rather than optional.

This is data collection against real repositories. Schedule it as its own work item;
the agent can build the measurement harness but a human picks the corpus and reads the result.

Also required: NFR-6 false-positive budget — `FIX_IS_IN_THE_TESTS` + `CONFIG_WEAKENED`
together ≤2% false positives on ≥200 human-authored commits.

**Status:** neither measurement has been run. Step 14's fallback ships as non-blocking
heuristic enrichment only; it stays that way until the INCONCLUSIVE_COMPILE rate is
known. All other steps (1-13) are code-complete and green on CI.

---

## 5. The Stop hook (FR-36 / §10 surface 3)

This is why greenwash is a product and not a lint rule. Build for it early even though
it serves the fewest users at first.

- Claude Code `Stop` hook fires when the agent tries to end its turn.
- Hook runs greenwash on the working-tree diff.
- On `FIX_IS_IN_THE_TESTS` or `CONFIG_WEAKENED`: hook blocks the stop and returns the
  verdict text to the agent (`"your fix is in the test file"`) so it retries with no
  human in the loop.
- On anything else: hook is silent, agent proceeds.
- Must respect NFR-4 fail-open: a broken hook never traps the agent.

---

## 6. Dogfooding

Once step 7 (v0.1) is green: run greenwash on greenwash's own commits. If it cannot
verify its own diffs, it is not done. Wire it as the pre-commit hook on this repo.

---

## 7. Progress log

_Append one line per completed step. Keep newest last._

- 2026-08-27 — plan written, no code yet.
- 2026-08-27 — scaffold: CLAUDE.md guardrails, DR-6 (config=TOML), `greenwash/` package
  with NotImplementedError stubs for all 11 modules, `tests/` (smoke green; fixture +
  NFR-5 tests skip-stubbed), v0.1 fixture dirs with SPEC.md + expected.json (repo/ and
  change.patch still todo), hooks/ stubs. `python -m unittest discover -s tests`: 8 tests,
  3 pass / 5 skip.
- 2026-08-27 — step 1 done: `revisions.py` — `resolve()` for all three input modes
  (FR-7), working-tree capture via `git stash create` (no stash-ref mutation),
  `--no-renames` file-level diff (FR-10), untracked warnings (FR-9), `read_blob()`, and
  the `worktree()` context manager with an overlay map for file-level revert (FR-8, FR-18).
  NFR-5 property test is live and green (4 cases: worktree run, staged+unstaged diff,
  untracked warn, commit mode). Suite: 11 tests, 7 pass / 4 skip.
- 2026-08-27 — step 2 done: `classify.py` — `classify()` returns ClassifiedPath
  (path, kind, module, reason) per FR-1/FR-5. Test detection by build-tool root first
  (`src/test/`, `src/integrationTest/`, `src/testFixtures/`, `src/it/`, …), filename
  fallback for non-standard layouts (FR-2). Config = build files, CI workflows, `.mvn/`,
  static-analysis configs (FR-3). Per-repo overrides via glob→kind, override wins (FR-4).
  Module attribution walks up to the nearest build file (`pom.xml` / `build.gradle*`),
  id = its repo-relative dir, `.` for root (FR-6). Suite: 24 tests, 20 pass / 4 skip.
- 2026-08-27 — step 3 done: `replay.py` — `run_build(workdir, command, *, timeout_s,
  modules, name, report_globs)` runs a build in a worktree and returns RunResult
  (exit_code, failing_goals, report_paths, timed_out) per FR-15. Maven default
  `mvn -B -Dmaven.test.failure.ignore=true test` keeps gates observable through test
  failures (FR-12). Timeout → `timed_out=True`, exit 124 (FR-16). `_maven_scope()` adds
  `-pl a,b -am` for touched non-root modules, no-ops for non-Maven / root-only (FR-17).
  `discover_reports()` globs surefire/failsafe/Gradle XML; `_parse_failing_goals()` pulls
  `GAV:goal` from "Failed to execute goal" lines. `RunResult.ran_tests` for the FR-25
  distinction. Missing build tool → RuntimeError (CLI fails open, NFR-4). Tests: pure
  helpers + real `sleep` timeout, no Maven needed. Suite: 33 tests, 29 pass / 4 skip.
- 2026-08-27 — step 4 done: `reports.py` — `parse_reports(paths, workdir)` parses
  Surefire/Failsafe/Gradle JUnit XML (handles `<testsuites>` wrapper, malformed files
  ignored) into `{TestKey(module, classname, name): Outcome}`; module derived from the
  `/target/` or `/build/` segment of the report path (FR-19, FR-20). `compare(after,
  source_only)` emits candidate findings: FIX_IS_IN_THE_TESTS (A pass / B fail, FR-21),
  TESTS_REMOVED_OR_SKIPPED for newly-skipped and vanished tests with probable-rename
  labelling (FR-23), suppressed when a side never ran tests (FR-25). `compare_gates(A, B)`
  emits CONFIG_WEAKENED for a goal failing at base but not after (FR-22) — full config-
  revert replay wiring is step 8. Candidates still pass through flake confirmation.
  Suite: 45 tests, 41 pass / 4 skip.
- 2026-08-27 — step 5 done: `verdict.py` — `headline()` picks the highest-precedence
  verdict across all modules (§4.3, DR-4), HONEST_FIX on an empty list. `exit_code()` /
  `is_blocking()` apply the §5 blocking rule with per-verdict `.greenwash.toml` overrides
  (§6.7). `resolve(...)` assembles the full findings list plus synthetic state findings:
  NO_TEST_CHANGES when nothing testable changed, INCONCLUSIVE_COMPILE when the base
  tests don't compile (gate findings still outrank it, §9), INCONCLUSIVE_BUILD on no
  reports, INCONCLUSIVE_FLAKY only when every per-test candidate was demoted and no gate
  finding survived (FR-28). Pure function, fully unit-tested. Suite: 60 tests, 56 pass /
  4 skip.
  (An `orchestrate.py` module was added beyond §2's list to hold the split-and-replay
  experiment; `cli.py` stays a thin arg-parse + fail-open shell.)
- 2026-08-27 — step 6 done: `output.py` — `Report(headline, findings, classifications,
  warnings, schema_version)`. `render_human()` names every test and goal (never counts),
  groups findings by module, prints the disposition line + per-verdict summary, the
  classification table with reasons (FR-5), and warnings (FR-31). `render_json()` emits
  `schema_version` first, `headline_verdict` separate from the `findings` list (FR-32,
  FR-33), plus additive `blocking` / `exit_code`; lists sorted for byte-determinism.
  `exit_overrides` from `.greenwash.toml` flow through both. Suite: 68 tests, 64 pass /
  4 skip.
- 2026-09-01 — step 7 done: **v0.1 converges.** `config.py` loads `.greenwash.toml`
  (`tomllib`, all keys optional, string-or-list build command). `replay.py` gains
  `RunResult.compile_failed` (§9). `orchestrate.py` runs the experiment: resolve →
  classify → skip if no test/config touched (FR-13) → run A (head) and run B (head with
  test/config paths overlaid to base content) in worktrees → `compare` + `compare_gates`
  → `verdict.resolve`. `cli.py` wired: `--range` / `--commit` / working-tree, `--json`,
  `--keep`, exit codes with config overrides, fail-open wrapper. Hermetic
  `tests/test_orchestrate.py` drives all four verdicts + non-destructive + CLI exit
  through a stdlib fake build (no JVM). v0.1 Maven `fixtures/` rebuilt as base/ + head/
  trees with `tests/test_fixtures.py` running greenwash for real (skipped locally without
  `mvn`, run in CI via `.github/workflows/ci.yml`). Suite: 74 tests, 70 pass / 4 skip
  locally; **all 74 green on CI** including the 4 real Maven builds (run 33525544046).
  Harness gotcha fixed: `shutil.copytree` default `copy2` preserved the shared checkout
  mtime, and a size-preserving one-char assertion edit tripped git's racy-clean skip so
  `git add -A` staged nothing for `fix-in-tests` — now copies without mtime and bumps
  every file's mtime forward.
  Branch `scaffold-v0.1` pushed; open the PR when ready. **v0.1 milestone: done.**
- 2026-09-01 — ran greenwash against a real external repo (`mentra-boot`, Gradle +
  Spring Boot) via a 5-line `.greenwash.toml`. Verdict on commit `c7d0afc` (a test-only
  `@SpringBootTest` exclusion): `FIX_IS_IN_THE_TESTS` — run A green, run B (test reverted)
  fails to load the Spring context. NFR-5 held (working tree / worktree list / stash
  untouched). Confirms classify + Gradle report parsing + worktree isolation work on a
  non-trivial third-party project.
- 2026-09-01 — step 9 done: `flake.py` — `confirm(candidates, run_after, run_source_only,
  *, k, mode)` re-runs each FIX_IS_IN_THE_TESTS candidate K times per side; survives only
  on a consistent A-pass / B-fail across all rounds, early-exits once all demoted (FR-26,
  FR-27). `replay.test_filter()` scopes a build to `(class, method)` tests —
  `-Dtest=Class#m` (Maven) / `--tests fqcn.m` (Gradle) — so isolated mode costs ∝ finding
  count not suite size. `orchestrate` wires confirmation runners (fresh worktree per
  round), keeps vanished/skipped findings out of confirmation (structural, not flaky),
  adds the FR-29 isolation caveat to warnings, threads `--confirm-count` / `--confirm-mode`.
  Every-candidate-demoted → INCONCLUSIVE_FLAKY (via verdict.resolve, FR-28). Hermetic
  tests: flaky-case demotion + a surviving fix through 2 confirmation rounds. Suite:
  87 tests, 83 pass / 4 skip.
- 2026-09-01 — build-tool auto-detect: `replay.default_build_command(repo_root)` returns
  the Gradle command (`./gradlew test --continue --console=plain`, or bare `gradle` with
  no wrapper) when a gradle marker is at the root, else the Maven default. `orchestrate`
  uses it when neither CLI nor config supplies a build command — so a plain Gradle repo
  needs no `.greenwash.toml` at all. Suite: 91 tests, 87 pass / 4 skip.
- 2026-09-01 — step 8 done: **gate observable / CONFIG_WEAKENED.** `_parse_failing_goals`
  now reads Gradle failing tasks (`Execution failed for task ':x'`, `> Task :x FAILED`)
  alongside Maven `Failed to execute goal GAV:goal`, and filters out test-execution
  goals/tasks (`:test`, surefire/failsafe) so they don't feed the false-positive budget
  (NFR-6). `compare_gates` was already there; `orchestrate` now reads gates from run B,
  and when config changed AND run B hit the compile wall / never ran, does a dedicated
  config-only revert run (`B_cfg`) — no test compilation needed, so CONFIG_WEAKENED stays
  detectable (§9). Hermetic test: a `gate.json` pass-ratio threshold lowered head-side →
  `CONFIG_WEAKENED`. Maven fixture `config-weakened` (JaCoCo `check` 0.80→0.00, carries
  its own `.greenwash.toml` for `mvn verify`); `test_fixtures.py` now loads each
  fixture's config. Gate-finding module attribution is still `.` — multi-module mapping
  is step 10. Suite: 95 tests, 90 pass / 5 skip (Maven fixtures).
- 2026-09-01 — steps 10-14:
  - **10 multi-module:** probable-move labelling (open Q1) distinct from probable-rename;
    `_gate_module` derives a module from a Gradle task path. Maven reactor fixture
    `multi-module` (finding attributed to `svc-a`, `svc-b`'s same-named class never
    cross-compared). Maven gate→module still `.` (needs pom parsing).
  - **11 packaging/interfaces:** `pyproject.toml` (pip-installable, stdlib only, console
    scripts `greenwash` + `greenwash-stop-hook`). Real `hooks/github-actions/greenwash.yml`
    and `hooks/pre-commit`. `test_config.py` round-trip, `test_json_contract.py` pins the
    schema-1 shape. setup-java@v5.
  - **12 Stop hook (FR-36):** `greenwash/stophook.py` — `evaluate(report, stop_hook_active)`
    returns the Claude Code `block` decision on a blocking verdict (never twice a turn),
    else None; `main()` fail-open. `test_stop_hook.py`.
  - **13 static pre-filter (§4.1):** `greenwash/strictness.py` — `analyse()` reports
    weakening signals (disabled test, assertion removed/changed, threshold decreased,
    rule block removed, continue-on-error) and separately the files it cannot read.
    `orchestrate` skips the replay only when opted in (`--prefilter` / `prefilter=true`)
    AND every changed file is analysable AND none weakened → HONEST_FIX + a loud warning.
    Opt-in, not default: a skipped replay is a false-negative risk and fixtures must keep
    exercising the real replay.
  - **14 compile-wall fallback (§9) — CANDIDATE, not final:** on INCONCLUSIVE_COMPILE,
    orchestrate attaches the suspected weakenings from `strictness` as informational
    findings tagged "static heuristic, not verified by replay". Non-blocking (§5). The
    full design (promote to a real verdict? AST vs diff?) is still gated on the §9
    INCONCLUSIVE_COMPILE-rate measurement below.
  Suite: 129 tests, 123 pass / 6 skip (Maven fixtures).
