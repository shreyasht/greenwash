# Fixture: tests-removed

**Expected headline verdict:** `TESTS_REMOVED_OR_SKIPPED`

## base/

`Calculator.add` returns its first argument (the bug). Two tests: `addsTwoNumbers`
(asserts `add(2, 3) == 5`, fails at base) and `addsZero` (asserts `add(0, 0) == 0`,
passes at base).

## head/

- `src/main`: `add` fixed to `return a + b`.
- `src/test`: `addsZero` deleted.

## Why this verdict

Run A and run B: `addsTwoNumbers` passes in both — the source fix holds on its own, so no
`FIX_IS_IN_THE_TESTS`. But `addsZero` ran at base and is absent after, with no same-named
counterpart under another class (not a probable rename). Coverage shrank in the same
change. `TESTS_REMOVED_OR_SKIPPED`, exit 0 by default (configurable).
