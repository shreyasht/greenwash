# Fixture: fix-in-tests

**Expected headline verdict:** `FIX_IS_IN_THE_TESTS`

## base/

`Calculator.add` returns its first argument (the bug). `CalculatorTest.addsTwoNumbers`
asserts `add(2, 3) == 5` and fails.

## head/

- `src/main`: **unchanged** — the bug stays.
- `src/test`: the assertion is changed to `assertEquals(2, ...)` to match the broken
  output.

## Why this verdict

Run A (test edit applied) passes. Run B (test reverted to base) fails on
`calc.CalculatorTest.addsTwoNumbers`. The source change alone does not make the named
test pass — the fix is in the test file. `FIX_IS_IN_THE_TESTS`, exit 1, blocks the build.
