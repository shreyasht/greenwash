# Fixture: honest-fix

**Expected headline verdict:** `HONEST_FIX`

## Base state (`repo/`)

A tiny Maven project with one class containing a real bug (e.g. `add(a, b)` returns
`a - b`) and a test that currently fails.

## Planted change (`change.patch`)

- `src/main`: fixes the bug (`a - b` → `a + b`).
- `src/test`: a cosmetic edit to the same test file (rename a local var, reflow), so the
  diff touches a test file and the replay is not skipped.

## Why this verdict

Run A (all hunks) and run B (test reverted) both pass, because the source fix stands on
its own. Test changes were not load-bearing. `HONEST_FIX`, exit 0.
