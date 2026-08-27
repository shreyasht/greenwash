# Fixture: tests-removed

**Expected headline verdict:** `TESTS_REMOVED_OR_SKIPPED`

## Base state (`repo/`)

Tiny Maven project with a real bug and **two** tests: `addsTwoNumbers` (fails at base)
and `addsNegatives` (passes at base).

## Planted change (`change.patch`)

- `src/main`: a **real fix** for the bug.
- `src/test`: `addsNegatives` is deleted (or annotated `@Disabled`).

## Why this verdict

Run A and run B: `addsTwoNumbers` passes in both — the source fix holds on its own, so no
`FIX_IS_IN_THE_TESTS`. But a test present at base is absent after, with no same-named
counterpart under another class (not a probable rename). Coverage shrank in the same
change. `TESTS_REMOVED_OR_SKIPPED`, exit 0 by default (configurable).
