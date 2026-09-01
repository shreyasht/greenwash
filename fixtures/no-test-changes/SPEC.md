# Fixture: no-test-changes

**Expected headline verdict:** `NO_TEST_CHANGES`

## base/

`Calculator.add` is correct; the suite is green.

## head/

- `src/main`: a `subtract` method added to `Calculator`. No `src/test` file and no
  build/config file touched.

## Why this verdict

Classification finds no `test` or `config` path in the diff. The replay is skipped
entirely (FR-13). Nothing to verify. `NO_TEST_CHANGES`, exit 0.
