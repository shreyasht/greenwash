# Fixture: no-test-changes

**Expected headline verdict:** `NO_TEST_CHANGES`

## Base state (`repo/`)

Tiny Maven project, suite green at base.

## Planted change (`change.patch`)

- `src/main` only: a small refactor or feature edit. No `src/test` file, no build/config
  file touched.

## Why this verdict

Classification finds no `test` or `config` paths in the diff. The replay is skipped
entirely (FR-13). Nothing to verify. `NO_TEST_CHANGES`, exit 0.
