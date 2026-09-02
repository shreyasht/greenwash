# Releasing astroturf

Distribution is dual-track from one source tree (see `docs/decisions.md` DR-7):

| Path | Install | For |
| --- | --- | --- |
| PyPI wheel | `pipx install astroturf` / `uv tool install astroturf` / `uvx astroturf` | most users |
| Offline zipapp | download `astroturf.pyz` from the GitHub Release, `python3 astroturf.pyz` | air-gapped / proxied networks with no package access (NFR-3) |

Distribution name, import package and both console scripts are all `astroturf`
(`astroturf-stop-hook` for the hook).

## One-time PyPI setup (Trusted Publishing, no tokens)

1. Sign in at <https://pypi.org>.
2. Go to **Your projects → Publishing → Add a new pending publisher** and enter:
   - PyPI project name: `astroturf`
   - Owner: `shreyasht`
   - Repository name: `astroturf`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
3. In the GitHub repo, create an **Environment** named `pypi`
   (Settings → Environments → New environment). No secrets needed; optionally add a
   required reviewer so a release waits for a manual approve.

The pending publisher becomes a normal Trusted Publisher after the first successful
upload creates the project.

## Cutting a release

1. Bump `__version__` in `astroturf/__init__.py` (single source of truth; the wheel
   reads it via `[tool.setuptools.dynamic]`). Use `X.Y.ZrcN` for a pre-release.
2. Update `docs/decisions.md` / `BUILD_PLAN.md` §7 if anything shipped.
3. Commit, then tag and push:
   ```
   git tag v0.3.0
   git push origin v0.3.0
   ```
4. `release.yml` builds the wheel + sdist + `astroturf.pyz`, publishes the wheel and
   sdist to PyPI, and attaches all three to a GitHub Release named for the tag.
5. Verify:
   ```
   pipx install astroturf==0.3.0
   astroturf --version
   ```

## Local dry run

```
python -m build            # wheel + sdist into dist/
sh tools/build-zipapp.sh    # dist/astroturf.pyz
python3 dist/astroturf.pyz --version
```
