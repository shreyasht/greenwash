# Decision records — amendments to REQUIREMENTS_1.md §12

## DR-6 — Config file is TOML, not YAML

*Accepted 2026-08-27.*

§FR-30 names `.astroturf.yml`. The stdlib has no YAML parser and NFR-3 forbids adding one.
`tomllib` has been in the stdlib since Python 3.11.

Decision: config file is **`.astroturf.toml`**, parsed with `tomllib`. Same keys and
semantics as FR-30 describes (build command, report globs, classification overrides,
confirmation count, module scoping, per-verdict exit behaviour).

Consequence: minimum supported Python is **3.11**.

---

## DR-7 — Dual-track distribution

*Accepted 2026-09-02.*

NFR-3 ("zero install friction… no pip install… must run behind a corporate proxy with
no package access") rules out *depending* on a package index, but not *offering* one.
astroturf has zero runtime dependencies, so a wheel is a convenience, not a dependency
chain.

Decision: ship the same source tree two ways.

1. **PyPI wheel** — `pipx install astroturf`, `uv tool install astroturf`,
   `uvx astroturf`. Distribution name, import package and console scripts are all
   `astroturf` (`astroturf-stop-hook` for the hook). The project was renamed from
   `greenwash` on 2026-09-02; `greenwash` on PyPI is an unrelated tool.
2. **Offline zipapp** — `astroturf.pyz`, a single stdlib-only archive attached to every
   GitHub Release. `curl` it and run `python3 astroturf.pyz`. This is the NFR-3 path:
   no pip, no index, nothing to resolve.

Publishing uses PyPI Trusted Publishing (OIDC) from `release.yml` on a `vX.Y.Z` tag — no
API token is stored anywhere, consistent with NFR-2. `__version__` in
`astroturf/__init__.py` is the single source of truth; `pyproject.toml` reads it
dynamically. Process in `RELEASING.md`.

---

## DR-8 — CI-workflow gate weakening is out of scope for the replay

*Accepted 2026-09-02.*

FR-3 classifies CI workflow files (`.github/workflows/*`) as `config`, and the
source-only run reverts them to base. But the replay observable is the outcome of the
*local build command* (`mvn test`, `./gradlew test`) — per-test results and build-local
gate goals (JaCoCo, Checkstyle, enforcer). An agent can neuter a required check without
touching any of that:

- adding `if:` to the job or step that runs the suite,
- a `paths:` / `paths-ignore:` filter that excludes the PR's files,
- `continue-on-error: true` on the test step,
- renaming a required check, or adding a second job with the same name that always
  passes.

None of these change `mvn test`, so the replay produces no observable and therefore no
verdict. §10 surface 1 (astroturf as a PR check) is itself exposed to this: if the job
carrying astroturf is skipped, its verdict never blocks.

Decision: this stays out of scope. Covering it means statically interpreting workflow
YAML against branch-protection rules — a different mechanism against a different
adversary (misconfiguration, usually accidental), and "not a config parser" (§3) is
load-bearing. The static pre-filter (§4.1) already flags an added `continue-on-error`
in a config diff as a suspected weakening, but that is a non-blocking heuristic, not a
replay result.

The adjacency is covered by [Avi Seth's `greenwash`](https://pypi.org/project/greenwash/),
a static audit of GitHub Actions YAML against branch protection that answers "can this
required check report green without ever running?". His tool audits whether the gate can
fire; astroturf audits whether the code passing through the gate earned it. Run both.

---

## DR-9 — Run C (base) disambiguates FIX_IS_IN_THE_TESTS; new non-blocking verdict

*Accepted 2026-09-03.*

The measurement harness on `stleary/JSON-java` returned a 20% blocking rate (5/25). Two
of those were a compiler goal mis-read as a gate (fixed separately). The other three were
all the same shape: a real behaviour change in `src/main` (e.g. `XML.toString` now throws
on illegal element names, CWE-91) with the assertions updated to match
(`assertEquals([1])` → `assertEquals([1,""])`). Reverting the tests makes them fail
against the new source, so `A-pass / B-fail` fires — mechanically correct, but a reviewer
calls every one an honest fix. On any repo where behaviour-changing commits routinely
touch assertions, this alone blows the NFR-6 2% budget.

The A/B experiment cannot tell "assertion updated for a real behaviour change" from
"assertion hacked to hide a non-fix". The distinguishing signal is the test's outcome
**at base**:

- **passed at base** → the check was valid for the old contract; the head source changed
  the behaviour it exercises. Legitimate co-change.
- **failing at base** → the test was already red; the source change did not fix it, only
  the test edit did. The real thing.

Decision: wire **run C** — re-run each `FIX_IS_IN_THE_TESTS` candidate at `base_ref` with
nothing applied, scoped to the candidate tests via the same `test_filter` path flake
confirmation uses (so a clean run pays nothing, NFR-7). Passed-at-base reclassifies to a
new verdict **`TESTS_UPDATED_FOR_BEHAVIOR_CHANGE`** (exit 0, non-blocking, precedence just
above `HONEST_FIX`); already-failing or un-runnable-at-base stays `FIX_IS_IN_THE_TESTS`,
now carrying `base: "fail" | "error" | "absent"` in its detail. Run C happens before
flake confirmation, so the expensive K-round confirmation only runs on genuine
candidates.

This makes the README's long-described `--with-base` / run C part of the default path
rather than an opt-in. Additive to JSON schema 1 (a new verdict string; consumers already
fail open on unrecognised verdicts, DR-5).

---

_Add new records below as DR-10, DR-11, …_
