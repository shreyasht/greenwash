# astroturf

[![ci](https://github.com/shreyasht/astroturf/actions/workflows/ci.yml/badge.svg)](https://github.com/shreyasht/astroturf/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/shreyasht/astroturf/branch/main/graph/badge.svg)](https://codecov.io/gh/shreyasht/astroturf)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/astroturf.svg)](https://pypi.org/project/astroturf/)

**Did your coding agent fix the bug, or fix the test that caught it?**

astroturf re-runs your test suite with the agent's test edits withheld. If a test only
passes when its own edits are applied, the fix is in the assertion, not the code.

Java / Maven / Gradle. Python stdlib only, zero runtime dependencies, nothing leaves your
machine.

> **Status: 0.3, early.** The split-and-replay core, the gate observable
> (`CONFIG_WEAKENED`), flake confirmation, module-aware identity and run C
> (`TESTS_UPDATED_FOR_BEHAVIOR_CHANGE`) are all shipped and test-covered. The
> false-positive and compile-wall rates (`docs/`, NFR-6 / §9) are still being measured
> against real repositories. If you are evaluating this for a team, read
> [Known limitations](#known-limitations) first.

---

## The problem

Coding agents are graded by checks they are also allowed to edit. When the source fix is
hard, a cheaper path exists: change what the test asks for.

```diff
  public void testDivideByZeroGivesFriendlyError() {
      try {
          new Calc().divide(1, 0);
-         throw new AssertionError("expected IllegalArgumentException");
-     } catch (IllegalArgumentException expected) {
+         throw new AssertionError("expected ArithmeticException");
+     } catch (ArithmeticException expected) {
      }
  }
```

The suite goes green. The bug is untouched. The commit message says `fix: handle divide by
zero`, the diff touches `src/main` so it looks like real work, and a reviewer scanning for
correctness has no cheap way to notice that the test edit is the thing doing the work.

This is measured behaviour, not a hypothetical. The
[EvilGenie benchmark](https://arxiv.org/abs/2511.21654) (Nov 2025) put agents in
environments where test files were editable and recorded explicit reward hacking —
hardcoded expected values and edited test files — from both Codex and Claude Code.

## What it reports

```
$ astroturf --range main..agent-cheats

astroturf: FIX_IS_IN_THE_TESTS  (build fails: exit 1)

the source change alone does not make the named tests pass

Findings:

  module .
    FIX_IS_IN_THE_TESTS  CalcTest.testDivideByZeroGivesFriendlyError
        passes with the test/config edits applied, fails without them
        (source-only run); was already fail at base

Classification (dispute in .astroturf.toml):
  source  src/main/java/Calc.java      under main source root 'src/main/'
  test    src/test/java/CalcTest.java  under test source root 'src/test/' (FR-2)
```

Exit code 1. `was already fail at base` is the whole product: the test was failing before
this change, and the source edit did not fix it. Had it passed at base, the verdict would
be `TESTS_UPDATED_FOR_BEHAVIOR_CHANGE` instead — an honest co-change, exit 0.

## How it works

No model, no heuristics, no opinions. It runs an experiment.

```
                 ┌── source hunks ──┐
   diff ─────────┼── test hunks ────┼──► run A "after":       everything applied
                 └── config hunks ──┘
                                     └──► run B "source-only": test + config reverted to base

   compare per-test outcomes  ──►  candidate findings

   run C "base" (base commit, nothing applied), scoped to the candidate tests:
     candidate passed at base  ──►  honest co-change with a behaviour change
     candidate failed at base  ──►  the test edit is what turned it green
```

Java makes this unusually clean. Maven and Gradle already separate `src/main` from
`src/test` by convention, so bucketing a diff is decided by the build tool rather than
guessed from filenames — and reverting is a file-level `git checkout base -- src/test`
rather than hunk surgery.

Every run happens in an isolated `git worktree`. Your working tree, index and stash are
never touched.

**Every finding is reproducible by hand.** astroturf tells you which files it reverted and
which command it ran; you can rerun both yourself and get the same answer. If it ever
tells you something you can't verify in two commands, that's a bug.

## Install

Zero runtime dependencies — Python 3.11+, git, and whatever your project already builds
with. Nothing to add to your `pom.xml` or `build.gradle`.

```bash
pipx install astroturf        # or: uv tool install astroturf
```

`uvx astroturf --version` runs it without installing.

**Air-gapped / proxied network with no package index?** Grab the single-file archive from
the [latest release](https://github.com/shreyasht/astroturf/releases/latest) — it is the
whole tool, stdlib only:

```bash
curl -LO https://github.com/shreyasht/astroturf/releases/latest/download/astroturf.pyz
python3 astroturf.pyz --version
```

## Usage

```bash
# audit uncommitted work against HEAD  (pre-commit)
astroturf

# audit a single commit
astroturf --commit <sha>

# audit a branch against main
astroturf --range main..my-feature

# large repo: scope the build yourself
astroturf --commit <sha> \
  --build-command "mvn -B -pl billing-core -am -Dmaven.test.failure.ignore=true test"

# machine-readable report on stdout
astroturf --commit <sha> --json

# skip the replay when static analysis sees no strictness reduction
astroturf --commit <sha> --prefilter

# flake confirmation: re-runs per side, and how to scope them
astroturf --commit <sha> --confirm-count 3 --confirm-mode full
```

Run C is automatic. When the A-vs-B comparison produces `FIX_IS_IN_THE_TESTS`
candidates, astroturf re-runs those tests — and only those — at base to separate a
propped-up test from an honest behaviour co-change. There is no flag for it.

The default build command is `mvn -B -Dmaven.test.failure.ignore=true test`, or
`./gradlew test --continue --console=plain` when a Gradle wrapper is present. The
failure-ignore flag matters — without it the build halts at the first failing module and
produces nothing to compare. Override it with `--build-command` or a `.astroturf.toml`
(see [Verdicts](#verdicts) and `docs/`).

**Exit codes.** `0` for everything informational, `1` only for `FIX_IS_IN_THE_TESTS` and
`CONFIG_WEAKENED`. A tool that blocks builds on ambiguous findings gets disabled in a
week, so ambiguity never blocks.

### In CI

A reusable GitHub Actions workflow lives in [`hooks/github-actions/`](hooks/github-actions);
a `pre-commit` hook and a Claude Code `Stop` hook are in [`hooks/`](hooks). Minimal
manual wiring:

```yaml
- run: pipx install astroturf
- run: astroturf --range ${{ github.event.pull_request.base.sha }}..${{ github.sha }} --json
```

## Verdicts

| Verdict | Meaning | Exit | |
| --- | --- | --- | --- |
| `NO_TEST_CHANGES` | No test or config files touched | 0 | shipped |
| `HONEST_FIX` | Tests changed, source fix holds without them | 0 | shipped |
| `TESTS_UPDATED_FOR_BEHAVIOR_CHANGE` | Assertions changed with a real behaviour change — passed at base, fail when reverted against the new source | 0 | shipped |
| `TESTS_REMOVED_OR_SKIPPED` | Fix holds, but coverage shrank in the same change | 0 | shipped |
| `FIX_IS_IN_THE_TESTS` | Source change alone does not make the named tests pass, and they were already failing at base | 1 | shipped |
| `CONFIG_WEAKENED` | A gate that failed under base config passes now | 1 | shipped |
| `INCONCLUSIVE_COMPILE` | Base tests don't compile against the new source | 0 | shipped |
| `INCONCLUSIVE_BUILD` | Build produced no reports; nothing to compare | 0 | shipped |
| `INCONCLUSIVE_FLAKY` | Findings failed confirmation re-runs | 0 | shipped |

## What astroturf is not

- **Not a code reviewer.** No opinion on style, design or correctness.
- **Not a coverage tool.** Coverage delta is a proxy; astroturf compares outcomes.
- **Not an AI reviewer.** There is no model in the verification path, ever. Same inputs,
  same verdict, always.
- **Not a test generator.** It never writes or repairs tests.
- **Not agent-specific.** It reads a diff. Whether Claude Code, Codex, Cursor or a human
  wrote it is irrelevant — the experiment is the same.

## Known limitations

- **Two full suite runs.** Roughly 2.2× the cost of one, plus scoped re-runs for run C and
  flake confirmation. Narrow with `-pl` on large repos, or `--prefilter`.
- **The compile wall.** Reverting tests against changed source breaks compilation whenever
  a signature changes, which in a statically typed language is often. Those changes return
  `INCONCLUSIVE_COMPILE`. An AST-strictness fallback is drafted but gated on measuring how
  often this actually fires — see [Help wanted](#help-wanted). This remains the project's
  main open problem.
- **Flake confirmation runs candidates in isolation by default.** Test-order dependence and
  shared-state pollution are indistinguishable from flakiness under isolation, so the run
  warns when this applies. `--confirm-mode full` trades cost for a correct answer.
- **Untracked files are excluded.** Working-tree mode uses `git stash create`, which does
  not capture them; you get a warning naming what was skipped. Worktrees are also fresh
  checkouts, so untracked local config your suite depends on will not be present.
- **CI-workflow gate weakening is invisible to the replay.** astroturf runs the build
  command it is given; it does not read `.github/workflows` to check whether the job
  carrying a required check can be skipped (`if:`, path filters, `continue-on-error`,
  renamed checks). That is a static-audit problem — see
  [`greenwash`](https://pypi.org/project/greenwash/) — and DR-8 in `docs/decisions.md`.
- **Maven fixtures require Maven on PATH.** `tests/test_fixtures.py` skips without it;
  `tests/test_orchestrate.py` is the hermetic equivalent.

## Roadmap

Shipped in 0.3: split-and-replay core, gate observable (`CONFIG_WEAKENED`), run C and
`TESTS_UPDATED_FOR_BEHAVIOR_CHANGE`, flake confirmation, module-aware identity, static
prefilter, `.astroturf.toml`, versioned JSON, and pre-commit / GitHub Actions / Claude
Code `Stop` hooks in [`hooks/`](hooks).

**Next**

- Measured false-positive and compile-wall rates against real repositories (NFR-6, §9).
- An AST-strictness fallback for the compile wall, if the measured rate justifies it.
- Fixture coverage for the verdicts that currently have only hermetic tests —
  `TESTS_UPDATED_FOR_BEHAVIOR_CHANGE`, `INCONCLUSIVE_FLAKY`, `INCONCLUSIVE_COMPILE`.
- Kotlin, then TypeScript (Jest/Vitest JUnit reporters). Language support is a plugin
  boundary, not a fork.

Full requirements and decision record: [`REQUIREMENTS.md`](REQUIREMENTS.md) and
[`docs/decisions.md`](docs/decisions.md).

## Help wanted

The most useful contribution right now is not code. It's a number.

Run astroturf across ~100 real commits in your repo that touch both `src/main` and
`src/test`, and report **what fraction come back `INCONCLUSIVE_COMPILE`**. That rate decides whether
the runtime-comparison approach is viable in statically typed languages or whether it
needs an AST-based fallback. Nobody has measured it. Open an issue with the number, your
language, and your build tool.

Also welcome: build-tool adapters, report-format parsers, and false positives — a
reproducible false positive is worth more than a feature.

## License

MIT.
