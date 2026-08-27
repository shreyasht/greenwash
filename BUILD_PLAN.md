# greenwash — Agentic Build Plan

**Status:** not started (repo has REQUIREMENTS_1.md, README.md, LICENSE only)
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
