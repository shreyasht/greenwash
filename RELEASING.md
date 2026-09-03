# Releasing astroturf

Distribution is dual-track from one source tree (see `docs/decisions.md` DR-7):

| Path | Install | For |
| --- | --- | --- |
| PyPI wheel | `pipx install astroturf` / `uv tool install astroturf` / `uvx astroturf` | most users |
| Offline zipapp | download `astroturf.pyz` from the GitHub Release, `python3 astroturf.pyz` | air-gapped / proxied networks with no package access (NFR-3) |

Distribution name, import package and both console scripts are all `astroturf`
(`astroturf-stop-hook` for the hook).

`release.yml` runs on any `vX.Y.Z` tag and routes by tag name:

- tag contains `rc` (e.g. `v0.3.0rc1`) → **TestPyPI**, GitHub Release marked pre-release
- otherwise (e.g. `v0.3.0`) → **PyPI**

Both use Trusted Publishing (OIDC) — no API token is stored anywhere, consistent with
NFR-2.

## One-time setup (Trusted Publishing, no tokens)

Do this once per index. For the first `rc` you only need the TestPyPI half.

### TestPyPI

1. Sign in at <https://test.pypi.org>.
2. **Account → Publishing → Add a new pending publisher**:
   - PyPI project name: `astroturf`
   - Owner: `shreyasht`
   - Repository name: `astroturf`
   - Workflow name: `release.yml`
   - Environment name: `testpypi`
3. In the GitHub repo: **Settings → Environments → New environment** named `testpypi`.
   No secrets.

### PyPI (before the first final tag)

Same as above at <https://pypi.org>, environment name `pypi`, and a GitHub `pypi`
environment.

## Cutting a release

1. Bump `__version__` in `astroturf/__init__.py` — the single source of truth; the wheel
   reads it via `[tool.setuptools.dynamic]`. `X.Y.ZrcN` for a pre-release.
2. Update `docs/decisions.md` / `BUILD_PLAN.md` §7 if anything shipped.
3. Commit, then tag and push (tag must match `__version__`, prefixed `v`):
   ```
   git tag v0.3.0rc1
   git push origin v0.3.0rc1
   ```
4. `release.yml` builds the wheel + sdist + `astroturf.pyz`, publishes to TestPyPI (rc)
   or PyPI (final), and attaches all three to a GitHub Release named for the tag.
5. Verify a pre-release from TestPyPI:
   ```
   pipx install --pip-args=--pre \
     --index-url https://test.pypi.org/simple/ \
     --pip-args=--extra-index-url=https://pypi.org/simple/ \
     astroturf
   astroturf --version
   ```
   or with uv:
   ```
   uv tool install --prerelease allow \
     --index https://test.pypi.org/simple/ astroturf
   ```

## Local dry run

```
python -m build            # wheel + sdist into dist/
sh tools/build-zipapp.sh    # dist/astroturf.pyz
python3 dist/astroturf.pyz --version
```
