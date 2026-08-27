# Fixtures — planted scenarios

Each fixture is a **minimal self-contained Maven project** plus a **planted diff**, and it
is the ground truth for one verdict (REQUIREMENTS_1.md §8, §11). `tests/test_fixtures.py`
runs greenwash against every fixture that has an `expected.json` and asserts the result.

## Layout per fixture

```
<fixture-name>/
  SPEC.md          # what is planted and why this verdict
  expected.json    # schema_version 1; headline_verdict + findings greenwash must produce
  repo/            # the Maven project at BASE (committed state before the change)
  change.patch     # the planted diff, applied on top of repo/ to form the HEAD state
```

The harness builds a throwaway git repo from `repo/`, commits it as base, applies
`change.patch`, commits that as head, then runs greenwash in commit-range mode.

## Do not

Never edit a fixture's assertions, `change.patch`, or `expected.json` to make a failing
run pass. The fixture is right; the code is wrong. If a fixture genuinely looks wrong,
stop and raise it — see `CLAUDE.md`.

## Status

| Fixture | Verdict | repo/ | change.patch | expected.json |
| --- | --- | --- | --- | --- |
| honest-fix | `HONEST_FIX` | todo | todo | stub |
| fix-in-tests | `FIX_IS_IN_THE_TESTS` | todo | todo | stub |
| tests-removed | `TESTS_REMOVED_OR_SKIPPED` | todo | todo | stub |
| no-test-changes | `NO_TEST_CHANGES` | todo | todo | stub |

v0.2 / v0.3 fixtures (`config-weakened`, `lint-disabled`, `flaky-candidate`,
`multi-module`, `compile-wall`, `no-strictness-reduction`) are added when their milestone
starts — see `BUILD_PLAN.md` §1.
