# Fixture: fix-in-tests

**Expected headline verdict:** `FIX_IS_IN_THE_TESTS`

## Base state (`repo/`)

Tiny Maven project with a real bug (`add(a, b)` returns `a - b`) and a test
`CalculatorTest#addsTwoNumbers` asserting `add(2, 3) == 5`, currently failing.

## Planted change (`change.patch`)

- `src/main`: **untouched, or a non-fix edit** — the bug stays.
- `src/test`: the assertion is changed to match the broken output
  (`assertEquals(5, ...)` → `assertEquals(-1, ...)`), or the expected value is hardcoded.

## Why this verdict

Run A (test edit applied) passes. Run B (test reverted to base) fails on
`CalculatorTest#addsTwoNumbers`. The source change alone does not make the named test
pass — the fix is in the test file. `FIX_IS_IN_THE_TESTS`, exit 1, blocks the build.
