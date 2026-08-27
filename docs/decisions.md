# Decision records — amendments to REQUIREMENTS_1.md §12

## DR-6 — Config file is TOML, not YAML

*Accepted 2026-08-27.*

§FR-30 names `.greenwash.yml`. The stdlib has no YAML parser and NFR-3 forbids adding one.
`tomllib` has been in the stdlib since Python 3.11.

Decision: config file is **`.greenwash.toml`**, parsed with `tomllib`. Same keys and
semantics as FR-30 describes (build command, report globs, classification overrides,
confirmation count, module scoping, per-verdict exit behaviour).

Consequence: minimum supported Python is **3.11**.

---

_Add new records below as DR-7, DR-8, …_
