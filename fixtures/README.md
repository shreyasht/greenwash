# Fixtures — planted scenarios

Each fixture is a **minimal self-contained Maven project** in two states — `base/` and
`head/` — plus an `expected.json`. It is the ground truth for one verdict
(REQUIREMENTS_1.md §8, §11). `tests/test_fixtures.py` builds a throwaway git repo
(base commit, then head commit), runs greenwash in single-commit mode with the default
Maven command, and asserts the headline verdict and findings.

The hermetic, no-JVM equivalent of these scenarios is `tests/test_orchestrate.py`, which
runs everywhere; the Maven fixtures add the real integration and run in CI
(`.github/workflows/ci.yml`), skipped locally when `mvn` is absent.

## Layout per fixture

```
<fixture-name>/
  SPEC.md          # what is planted and why this verdict
  expected.json    # { "headline_verdict": ..., "findings": [{verdict, module, subject}] }
  base/            # project tree, committed first
  head/            # project tree, committed second (adds/mods/deletes vs base)
```

The domain is a one-method `calc.Calculator`. The bug is `add` returning its first
argument; the fix is `return a + b`.

## Do not

Never edit a fixture's assertions, its `head/` tree, or `expected.json` to make a
failing run pass. The fixture is right; the code is wrong. If a fixture genuinely looks
wrong, stop and raise it — see `CLAUDE.md`.

## Status

| Fixture | Verdict | Planted in head/ |
| --- | --- | --- |
| honest-fix | `HONEST_FIX` | real `add` fix + a comment-only test edit |
| fix-in-tests | `FIX_IS_IN_THE_TESTS` | assertion changed to match the broken output; no source fix |
| tests-removed | `TESTS_REMOVED_OR_SKIPPED` | real `add` fix + one test method deleted |
| no-test-changes | `NO_TEST_CHANGES` | source-only change (adds `subtract`) |
| config-weakened | `CONFIG_WEAKENED` | `pom.xml` lowers the JaCoCo coverage minimum 0.80 → 0.00 |

Remaining v0.2 / v0.3 fixtures (`flaky-candidate`, `multi-module`, `compile-wall`, …)
are added when their milestone starts — see `BUILD_PLAN.md` §1. A fixture may carry its
own `.greenwash.toml` (config-weakened needs `mvn verify` for the gate phase).
