# Fixture: honest-fix

**Expected headline verdict:** `HONEST_FIX`

## base/

`Calculator.add` returns its first argument (the bug). `CalculatorTest.addsTwoNumbers`
asserts `add(2, 3) == 5` and fails.

## head/

- `src/main`: `add` fixed to `return a + b`.
- `src/test`: a comment added above the class — a real test-file hunk, but not
  load-bearing.

## Why this verdict

Run A (all hunks) and run B (test file reverted to base) both pass: the source fix
stands on its own. The test edit changed nothing. `HONEST_FIX`, exit 0.
