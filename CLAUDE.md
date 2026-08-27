# greenwash — agent instructions

Deterministic verifier: *does the source change, on its own, still satisfy the checks?*
Full spec in `REQUIREMENTS_1.md`. Build approach in `BUILD_PLAN.md`. Follow both.

## Hard constraints — do not violate

- **Python stdlib only** (NFR-3). Target Python 3.11+ (`tomllib` is used). No pip, no
  third-party imports anywhere, including tests. Tests use `unittest`, not `pytest`.
- **No LLM / no network in `greenwash/` source** (NFR-1, NFR-2). The verification path is
  pure and deterministic: same inputs, same verdict. No telemetry, no API keys.
- **Fail open** (NFR-4). `cli.py` wraps everything in a top-level handler that exits `0`
  with a diagnostic on stderr. greenwash must never be why a build breaks.
- **Non-destructive** (NFR-5). Never touch the user's working tree, index, or stash.
  All build runs happen in `git worktree` checkouts under a temp dir. There is a property
  test enforcing this — keep it green.
- **Fixtures are ground truth.** Never edit a fixture's assertions, planted diff, or
  expected-output file to make a test pass. That is the exact reward-hack this tool
  detects. If a fixture seems wrong, stop and ask.

## Workflow

- One vertical slice at a time, in the order in `BUILD_PLAN.md` §3.
- Each slice: extend a fixture-driven test → implement → run the **full** `tests/` suite
  → commit only if green.
- Append one line to `BUILD_PLAN.md` §7 progress log per completed step.
- Record any deviation from `REQUIREMENTS_1.md` in `docs/decisions.md`.

## Interface contracts (§6.7) — never break silently

- Exit codes are permanently stable. Meanings never change.
- JSON output carries `schema_version` (int, starts at 1). Additive only within a version;
  any removal / rename / retype / meaning change bumps the version.
