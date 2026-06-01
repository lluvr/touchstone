# Releasing

How to cut a `touchstone-mcp` release. This document is for the project maintainers.

## The package

This repository builds one PyPI distribution, `touchstone-mcp`, from the repository root. It bundles two components:

| Component | Source | Role |
|---|---|---|
| `clarethium_touchstone` (reference library) | `src/clarethium_touchstone/` | the eleven measurement layers + the calibrated Verifier |
| `touchstone_mcp` (MCP server) | `src/touchstone_mcp.py` | wraps the library as MCP tools |

`fastmcp >= 3.3.1` is the only runtime dependency. `from clarethium_touchstone import ...` works for anyone who installs the package; the library is not published separately.

### Version strings

Three version strings, two of which must match:

- **`pyproject.toml` `version`** and **`src/touchstone_mcp.py::__version__`** are the published package version. They MUST be equal; the MCP server reports `__version__` as `serverInfo.version` to host UIs, so a mismatch shows the wrong version.
- **`src/clarethium_touchstone/_version.py::__version__`** is the library/measurement version. It moves independently and only changes when the measurement implementation changes. It is reported as `touchstone_library` in the `list_modes` versions block.

## Cadence

Package releases follow semantic versioning:

- **Patch (0.1.x → 0.1.y):** bug fixes, documentation, internal cleanup. No API changes.
- **Minor (0.x → 0.y):** additive API changes, new layers/tools exposed, new optional parameters. No breaking changes.
- **Major (0.x → 1.0, 1.x → 2.x):** breaking API or measurement-output changes. Coordinates with a Standard version bump.

Pre-1.0 (0.x): intentional breaking changes may occur between minor versions; CHANGELOG entries flag them.

## Pre-release checklist

Run every step. Each is a gate; a failure blocks the release.

1. **Working tree is clean.**
   ```bash
   git status                # nothing uncommitted
   git diff main..HEAD       # only the changes you intend to release
   ```

2. **Package version bumped, and the two package-version strings match.**
   ```bash
   grep '^version' pyproject.toml
   grep '__version__' src/touchstone_mcp.py
   ```
   If the measurement code changed, bump `src/clarethium_touchstone/_version.py::__version__` too. If the Standard advanced, update `__standard_version__` in that file and the `CITATION.cff` Standard reference.

3. **CHANGELOG.md has the dated entry** at the top of the file.

4. **Tests, lint, type-check, format pass.**
   ```bash
   ruff check src tests examples benchmarks
   ruff format --check src tests examples benchmarks
   mypy src
   pytest -q
   ```

5. **Coverage threshold met** (CI gate is `--cov-fail-under=95`).
   ```bash
   pytest --cov=clarethium_touchstone --cov=touchstone_mcp --cov-fail-under=95 -q
   ```

6. **Canon audit passes.** Both MUST exit 0; any hit is a blocker.
   ```bash
   bash scripts/canon_audit.sh --self-test
   bash scripts/canon_audit.sh
   ```

7. **Benchmark snapshots stable.** Either existing snapshots match, or the drift is intentional, captured in a new dated snapshot, and documented in the CHANGELOG.
   ```bash
   pytest tests/test_benchmarks.py -q
   ```

8. **Build artifacts produce cleanly.**
   ```bash
   rm -rf dist/ build/ src/*.egg-info/
   python -m build
   ls dist/                  # sdist + wheel
   ```

9. **Wheel content check.** The wheel MUST contain only the `clarethium_touchstone/` package, `touchstone_mcp.py`, and license/metadata. Any other path is a blocker.
   ```bash
   unzip -l dist/touchstone_mcp-*.whl | head -30
   ```

10. **Self-contained install check.** This is the regression that prompted the single-package consolidation: confirm the wheel installs and imports with no separate `clarethium-touchstone` package.
    ```bash
    python -m venv /tmp/ts-rel
    /tmp/ts-rel/bin/pip install dist/touchstone_mcp-*.whl
    /tmp/ts-rel/bin/python -c "import touchstone_mcp, clarethium_touchstone; from touchstone_mcp import build_server; build_server()"
    ```

## Cutting the release

11. **Commit the release prep** (DCO sign-off).
    ```bash
    git add -A
    git commit -s -m "Cut touchstone-mcp vX.Y.Z: <one-line summary>"
    ```

12. **Tag** with the `vX.Y.Z` tag that the publish workflow triggers on (`.github/workflows/publish.yml` runs on `tags: ['v*']`).
    ```bash
    git tag -a vX.Y.Z -m "touchstone-mcp vX.Y.Z"
    ```

13. **Push.**
    ```bash
    git push origin main
    git push origin vX.Y.Z
    ```

14. **Publish (automatic, no token).** Pushing the `vX.Y.Z` tag triggers `publish.yml`, which builds the wheel + sdist, generates a build-provenance attestation, and publishes to PyPI via Trusted Publishing (OIDC) from the protected `pypi` environment. There is no manual `twine upload` and no long-lived PyPI token. Watch the run under the Actions tab; the publish job fails closed if the `pypi` environment or the PyPI Trusted Publisher is not configured (one-time setup, documented in `publish.yml`).

15. **GitHub release.** Create a release linked to the tag with the CHANGELOG entry as the notes.
    ```bash
    gh release create vX.Y.Z --title "touchstone-mcp vX.Y.Z" --notes-from-tag
    ```

## Post-release

16. **Bump to next dev version** so the next pre-release commit is not mistaken for the released version. Update `pyproject.toml` `version` and `src/touchstone_mcp.py::__version__` together (e.g. `0.1.3.dev0`).

17. **Announce** once announce channels exist (mailing list, blog, social).

## Hotfix releases

A hotfix (0.1.x → 0.1.y) skips the new-feature scope of a normal minor release. The pre-release checklist is unchanged; the CHANGELOG entry MUST name the specific bug fixed and the regression test that prevents recurrence.

## Coordinating Standard and library bumps

When the Standard advances:

- A Standard minor bump (1.0 → 1.1) is additive; a package release that newly implements 1.1 features bumps the package minor version and the library `_version`.
- A Standard major bump (1.x → 2.0) is breaking; conforming releases coordinate the bump.

`CITATION.cff` carries the structured Standard-version reference; update it in the same commit that updates the Standard text.
