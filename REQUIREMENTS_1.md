# greenwash — High-Level Requirements

**Status:** draft v0.3
**Owner:** Shreyash
**Last updated:** 2026-08-26

---

## 1. Problem

Coding agents are measured by the checks they can also edit. When an agent cannot
make a test pass, a cheaper path is available to it: make the test stop asking.

This is documented, not anecdotal. The EvilGenie benchmark (Nov 2025) placed agents
in environments where test files were editable and observed explicit reward hacking
by both Codex and Claude Code — hardcoded expected values and edited test files —
alongside misaligned behaviour from every agent tested.

The developer-facing consequence is a trust gap. An agent reports "fixed, tests pass."
The suite is green. Nobody can cheaply tell whether the fix is in the source or in the
assertion. Code review does not close this gap: reviewers read diffs for correctness,
not for whether the diff's own test edits are load-bearing.

No tool currently answers the question directly. Adjacent categories miss it:

| Category | Example | Why it doesn't answer this |
| --- | --- | --- |
| Agent instruction files | AGENTS.md, CLAUDE.md | States intent; cannot verify compliance |
| Session-learning tools | slagent, memory gateways | Remembers corrections; doesn't check outcomes |
| AI code review | git-lrc, LLM PR reviewers | Opinion from a model, not reproducible evidence |
| Coverage / mutation testing | JaCoCo, PIT | Measures the suite, not the delta's honesty |

## 2. What greenwash is

A deterministic verifier that answers one question about a change:

> **Does the source change, on its own, still satisfy the checks?**

It answers by experiment, not inference. It splits a diff into source, test and config
buckets; re-runs the build with the test and config edits withheld; and compares two
observables across the runs — per-test outcomes and gate outcomes.

A check that passes with its own edits applied and fails without them is not evidence
of a fix. It is evidence of a moved goalpost.

## 3. What greenwash is not

Explicit non-goals. Each is a plausible adjacent feature that would dilute the product,
and each is out of scope permanently unless revisited by decision record.

- **Not a code reviewer.** No opinion on style, design, or correctness.
- **Not a coverage tool.** Coverage delta is a weak proxy; greenwash uses outcomes.
- **Not an agent.** No LLM in the verification path (see NFR-1).
- **Not a policy engine.** It reports; humans and CI decide what to do about it.
- **Not a test generator.** It never writes or repairs tests.
- **Not a config parser.** It never learns the schema of JaCoCo, Checkstyle or any other
  gate. It reverts config and observes what breaks. See §4.2 — this is load-bearing.
- **Not agent-specific.** It reads a diff. Which tool produced the diff is irrelevant —
  including a human.

## 4. Core concept: split and replay

### 4.1 The experiment

```
                 ┌── source hunks ──┐
   diff ─────────┼── test hunks ────┼──► run A ("after"):       all hunks applied
                 └── config hunks ──┘
                                     └──► run B ("source-only"): test + config reverted to base
                                     └──► run C ("base", optional): nothing applied

   compare per-test outcomes AND gate outcomes ──► findings ──► headline verdict
```

The comparison that matters is A vs B. Run C is optional and strengthens the claim: if a
test was already failing at base, the change did not fix it at all.

**Design principle — evidence over heuristics.** Every finding must be reproducible by a
human running two build commands. Pattern matching may decide *when* to run the
experiment; it must never *be* the finding.

### 4.2 Two observables

A single observable is insufficient. Weakening a gate produces no test-outcome delta at
all — lowering a coverage threshold leaves every test passing in both runs while the
`jacoco:check` goal quietly stops failing.

| Observable | Detects | Compared as |
| --- | --- | --- |
| Per-test outcome | Localized reward hacking: assertion weakened, expectation flipped, test deleted | `(classname, name) → pass\|fail\|error\|skipped` |
| Gate outcome | Systemic bypass: coverage threshold lowered, lint rule disabled, CI step removed, enforcer relaxed | `(build exit code, failing goal identifiers)` |

Gate detection is a *consequence of the replay*, not a separate analysis. greenwash does
not read `pom.xml` to find a threshold number. It reverts the config, observes that a goal
which now passes previously failed, and reports it. This works for any gate — JaCoCo,
Checkstyle, SpotBugs, maven-enforcer, or an internal plugin nobody has heard of — with
zero per-tool knowledge, and it preserves NFR-1.

### 4.3 Findings and headline verdict

A change can weaken a gate *and* prop up a test. The tool therefore emits a **list of
findings**, each categorised, plus a single **headline verdict** derived by precedence for
exit-code purposes:

```
FIX_IS_IN_THE_TESTS > CONFIG_WEAKENED > TESTS_REMOVED_OR_SKIPPED
    > INCONCLUSIVE_* > HONEST_FIX > NO_TEST_CHANGES
```

All findings appear in both human and JSON output regardless of headline.

## 5. Verdict taxonomy

| Verdict | Meaning | Exit |
| --- | --- | --- |
| `NO_TEST_CHANGES` | No test or config files touched; nothing to verify | 0 |
| `HONEST_FIX` | Tests/config changed, source fix holds without them | 0 |
| `TESTS_REMOVED_OR_SKIPPED` | Source fix holds, but coverage shrank in the same change | 0 (configurable) |
| `CONFIG_WEAKENED` | A gate that failed under base config passes under the new config | 1 (configurable) |
| `FIX_IS_IN_THE_TESTS` | Source change alone does not make the named tests pass | 1 |
| `INCONCLUSIVE_COMPILE` | Base tests do not compile against new source | 0 |
| `INCONCLUSIVE_FLAKY` | Every candidate finding failed confirmation re-runs | 0 |
| `INCONCLUSIVE_BUILD` | Build produced no reports; nothing to compare | 0 |

**Blocking rule.** A verdict fails the build only when the finding is unambiguous and
demonstrable. `FIX_IS_IN_THE_TESTS` and `CONFIG_WEAKENED` both qualify: each is a
reproducible experimental result, not an inference. Everything else informs. A tool that
blocks on ambiguity gets disabled in week one.

On multi-module repos, findings are reported per module and the headline verdict is the
highest-precedence finding across all of them — one offending module fails the run.

## 6. Functional requirements

### 6.1 Change classification

- **FR-1** Classify every changed path as `source`, `test`, `config` or `neutral`.
- **FR-2** For Maven and Gradle layouts, derive `test` from build-tool convention
  (`src/test/`, `src/integrationTest/`, `src/testFixtures/`) rather than filename guessing.
  Fall back to filename suffixes (`*Test.java`, `*IT.java`) for non-standard layouts.
- **FR-3** Treat as `config` anything that can alter what the build enforces: build files,
  Surefire/Failsafe settings, coverage thresholds, static-analysis configs, CI workflows.
- **FR-4** Classification must be overridable per repo via config file (FR-30).
- **FR-5** Classification must be reported in output so a user can see and dispute it.
- **FR-6** Attribute each changed path to its owning build module, where the build defines
  modules. Module identity is the repo-relative directory of the build file that owns the
  path.

### 6.2 Revision handling

- **FR-7** Support three input modes: a commit range, a single commit, and the
  uncommitted working tree.
- **FR-8** Never mutate the user's working tree, index, or stash stack. Use isolated
  git worktrees for all runs.
- **FR-9** Detect untracked source files excluded from the audit and warn explicitly.
- **FR-10** Disable git rename detection so renames decompose into add + delete, keeping
  revert logic file-level. *Deferred, not rejected — see DR-3.*
- **FR-11** Disclose FR-10's consequence in output whenever any add or delete is present:
  renames are reported as a deletion plus an addition.

### 6.3 Replay execution

- **FR-12** Execute an arbitrary user-supplied build command per run; ship a Maven
  default that tolerates test failures without aborting the build.
- **FR-13** Skip the replay entirely when no test or config files changed.
- **FR-14** Support an optional third run at base for stronger verdicts.
- **FR-15** Capture per run: exit code, identifiers of failing build goals, and all
  discoverable test reports.
- **FR-16** Enforce a configurable timeout per run and degrade to `INCONCLUSIVE_BUILD`.
- **FR-17** Support restricting the build to the modules touched by the diff and their
  dependents, where the build tool provides it (`mvn -pl ... -am`). This is the primary
  cost lever on large repos and supersedes test-name filtering.
- **FR-18** Clean up all worktrees on exit, including on failure, unless `--keep`.

### 6.4 Result comparison

- **FR-19** Parse JUnit XML from Surefire, Failsafe and Gradle report locations.
- **FR-20** Identify tests by `(module, classname, name)`. Same-named test classes in
  different modules are distinct tests and must never be compared against one another —
  doing so fabricates findings. Module is derived from the report's location.
- **FR-21** Report tests that pass only with test/config edits applied.
- **FR-22** Report build goals that fail under base config but pass under new config.
- **FR-23** Report tests newly skipped, and tests present at base but absent after. When a
  vanished test has a same-named counterpart under a different class in the after run,
  label it a probable rename rather than a removal.
- **FR-24** Attribute every finding to a module.
- **FR-25** Distinguish "build never ran tests" from "tests ran and failed" — the former
  is inconclusive, not a finding.

### 6.5 Flake confirmation

- **FR-26** Before a per-test finding is reported, confirm it by re-running that test in
  both A and B configurations K additional times (default K=2, configurable). The finding
  survives only if the A-pass / B-fail outcome is consistent across all confirmations.
- **FR-27** Confirmation re-runs are scoped to the candidate test set, never the full
  suite. Cost scales with finding count, not suite size.
- **FR-28** A failed confirmation demotes that **finding**, not the run. The headline
  verdict becomes `INCONCLUSIVE_FLAKY` only when every candidate finding is demoted;
  surviving findings are reported normally.
- **FR-29** Default confirmation runs tests in isolation, which is materially different
  from full-suite conditions. Output must state this, since test-order dependence and
  shared-state pollution are indistinguishable from flakiness under isolation. Provide
  `--confirm-mode=full` to re-run the whole suite instead, at proportional cost.

### 6.6 Interfaces

- **FR-30** Config file at repo root (`.greenwash.yml`) for build command, report globs,
  classification overrides, confirmation count, module scoping, and per-verdict exit
  behaviour.
- **FR-31** Human-readable stdout naming specific tests and goals, not counts, grouped by
  module.
- **FR-32** Machine-readable JSON report for CI consumption, carrying the full findings
  list and the headline verdict separately.
- **FR-33** JSON output carries `schema_version`, an integer, starting at 1 in the first
  released JSON.
- **FR-34** Honour the interface contract in §6.7.
- **FR-35** Ship a GitHub Actions workflow and a `pre-commit` hook definition.
- **FR-36** Ship a Claude Code `Stop` hook that returns the verdict to the agent so it can
  correct itself before reporting success. *This is the differentiating integration —
  see §10.*

### 6.7 Interface stability contract

Two consumer-facing interfaces with deliberately different guarantees.

| Interface | Guarantee |
| --- | --- |
| Exit codes | Stable permanently. Meanings never change. This is the interface for simple CI consumers. |
| JSON report | Versioned via `schema_version`. Additive within a version. |

Within a schema version, fields may be **added**; existing field names, types and semantics
do not change. Any removal, rename, retype, or change of meaning increments
`schema_version`.

New verdict values may appear within a version. Consumers must therefore treat an
unrecognised verdict as non-blocking and defer to the exit code — a consumer that
switches exhaustively on verdict strings and fails closed on the unknown case is
misusing the interface.

## 7. Non-functional requirements

- **NFR-1 — Deterministic core.** No LLM call in the verification path. Same inputs,
  same verdict, always. An LLM may later assist *explanation*, never *judgement*.
- **NFR-2 — No egress.** Source code never leaves the machine. No telemetry, no API keys,
  no network calls. Non-negotiable: enterprise Java shops are the target users and this
  determines whether it can be installed at all.
- **NFR-3 — Zero install friction.** Python stdlib only. No pip install, no JVM plugin,
  no build-file modification. Must run behind a corporate proxy with no package access.
- **NFR-4 — Fail open.** Any internal error exits 0 with a diagnostic. The tool must never
  be the reason a build breaks.
- **NFR-5 — Non-destructive.** No operation may alter the user's working state. Verified
  by test: working tree, index and stash list identical before and after.
- **NFR-6 — False-positive budget.** `FIX_IS_IN_THE_TESTS` and `CONFIG_WEAKENED` must
  together reach ≤2% false positives on a corpus of ≥200 human-authored commits (§11).
  A single loud false positive costs more trust than ten missed detections.
- **NFR-7 — Bounded cost.** Two-run mode ≤2.2× a single suite run. Flake confirmation adds
  cost proportional to finding count, not suite size; a clean run pays nothing for it.
  On multi-module repos, scope the build to affected modules and their dependents (FR-17)
  rather than filtering by test name.

## 8. Scope by release

**v0.1 — proof (done)**
Java + Maven, split-and-replay core, per-test observable, four verdicts, CLI only,
validated against four planted scenarios.

**v0.2 — usable in one org**
Gate observable and `CONFIG_WEAKENED`. Flake confirmation. Findings list separated from
headline verdict. Config file, versioned JSON output, Gradle report paths, module-aware
test identity and per-module reporting, module-scoped builds, GitHub Actions workflow.
*Success: runs unattended on one real repo for two weeks.*

**v0.3 — the loop closes**
Claude Code `Stop` hook. Static pre-filter to skip the replay when no strictness reduction
is present. Compile-failure fallback (§9).

**v0.4 — second ecosystem**
Kotlin/JVM, then TypeScript (Jest/Vitest JUnit reporters). Language support is a plugin
boundary, not a fork.

## 9. Principal risk: the compile wall

Reverting tests against changed source breaks compilation whenever a signature changes.
Java's static typing makes this common — far more so than in dynamic languages. Every
such case degrades to `INCONCLUSIVE_COMPILE`, which is honest but useless.

If this fires on most real commits, the tool does not work, and no amount of detector
polish fixes it.

Note that the gate observable (§4.2) is **unaffected** by this wall: config revert does not
require test compilation, so `CONFIG_WEAKENED` remains detectable even when the per-test
comparison is inconclusive. This partially derisks §9 but does not remove it.

**Required measurement before v0.3 design is finalised:** run v0.1 against ≥100 real
commits that touch both `src/main` and `src/test`. Record the `INCONCLUSIVE_COMPILE` rate.

**Candidate fallback, to be designed only once that number is known:** when base tests do
not compile, abandon runtime comparison and compare *assertion strictness* via AST diff —
did assertions weaken, did exception handling broaden, did expected values become
literals matching current output. Weaker evidence, clearly labelled as such, but better
than a shrug.

## 10. Positioning

Three integration surfaces, ascending in value:

1. **CI check on PRs.** Obvious, lowest value — the change already landed.
2. **Pre-commit hook.** Catches it before it enters history.
3. **Agent stop hook.** The agent is blocked from reporting success and handed the
   verdict: *"your fix is in the test file."* It retries with no human in the loop.

Surface 3 is the reason this is a distinct product rather than a lint rule. General code
review tools are not shaped to sit inside an agent's completion loop. Build for it early
even though it serves the fewest users at first — it is what makes the project worth
sharing.

## 11. Success criteria

**Correctness**
- Regression suite covers every verdict with planted fixtures; green on every commit.
- NFR-6 false-positive budget met on the ≥200-commit corpus.
- Non-destructive property test passes (NFR-5).

**Adoption**
- Runs on one real internal repo for two weeks with no manual intervention and no
  disabling.
- ≥1 true positive found in production use that a human reviewer had already approved.
  *This is the single most valuable artifact the project can produce* — it is the
  README's opening example and the thing that makes the argument for everyone else.

**Deliberately not a success metric:** GitHub stars. They follow the true positive above;
optimising for them directly produces a detector list instead of a verifier.

## 12. Decision record

- **DR-1 — Config weakening is a distinct verdict.** *Accepted.* Weakening an assertion is
  localized; lowering a coverage gate is systemic. They warrant different review
  conversations. Named `CONFIG_WEAKENED` rather than `ENVIRONMENT_ALTERED` because
  "altered" would also fire on hardening, which is noise; "weakened" names a direction the
  experiment can demonstrate. Implementation is a second observable (§4.2), not a
  detector. Blocks by default, configurable.
- **DR-2 — Flaky findings are confirmed, then demoted.** *Accepted.* Candidate findings
  are re-run K times per side and survive only on consistent outcomes. Demotion is
  per-finding, not per-run. Isolation caveat documented in FR-25.
- **DR-3 — Rename detection deferred past v0.1.** *Accepted.* FR-9 stays; file-level
  revert is materially simpler than hunk surgery. Mitigated by FR-10 (explicit output
  disclosure) and FR-20 (probable-rename labelling). Revisit if
  `TESTS_REMOVED_OR_SKIPPED` noise proves to be dominated by renames in real use.
- **DR-4 — Multi-module: report per module, exit on any.** *Accepted.* Aggregating hides
  which module is affected, and Java monorepos are the expected deployment shape. The
  material consequence is not reporting but identity: test keys become
  `(module, classname, name)` (FR-20), without which same-named classes across modules
  cross-contaminate and fabricate findings. Module awareness also enables scoped builds
  (FR-17), the primary cost lever under NFR-7.
- **DR-5 — JSON carries `schema_version` from the first release.** *Accepted.* One integer
  now, versus a breaking change later against unknown CI consumers. Paired with an
  explicit stability contract (§6.7) that keeps exit codes permanently stable and requires
  consumers to fail open on unrecognised verdicts.

## 13. Open questions

Both prior questions are resolved (DR-4, DR-5). Two new ones follow from them:

1. **Module identity when a module is renamed or relocated between base and head.** The
   module path is part of the test key (FR-20), so a moved module makes every test in it
   look vanished and every test look new. Same shape as DR-3's rename problem, one level
   up. Likely mitigation is the same: probable-move labelling rather than git rename
   detection.
2. **Does `--confirm-mode=full` (FR-29) re-run the affected module or the whole reactor?**
   Module-only is far cheaper and matches FR-17, but loses cross-module test pollution as
   a cause — which is precisely the effect the full mode exists to capture.
