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

_Add new records below as DR-8, DR-9, …_
