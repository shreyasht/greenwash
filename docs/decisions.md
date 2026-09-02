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

_Add new records below as DR-9, DR-10, …_
