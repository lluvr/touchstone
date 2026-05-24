# Releasing

How to cut a `clarethium-touchstone` release. This document is for the project maintainers.

## Cadence

Library releases follow semantic versioning per Standard §10:

- **Patch (0.1.x → 0.1.y):** bug fixes, documentation, internal cleanup. No API changes.
- **Minor (0.x → 0.y):** additive API changes, new layers exposed, new optional parameters. No breaking changes.
- **Major (0.x → 1.0, 1.x → 2.x):** breaking API or measurement-output changes. Coordinates with a Standard version bump per §10.

Pre-1.0 (0.x): the library may include intentional breaking changes between minor versions. CHANGELOG entries flag those explicitly.

## Pre-release checklist

Run every step. Each one is a gate; a failure blocks the release.

1. **Working tree is clean.**
   ```bash
   git status                # nothing uncommitted
   git diff main..HEAD       # only the changes you intend to release
   ```

2. **Version bumped consistently.** Both files MUST match.
   ```bash
   grep '^version' pyproject.toml
   grep '__version__' src/clarethium_touchstone/_version.py
   ```
   If the Standard advances too, update `__standard_version__` in the same file and `CITATION.cff`'s standard reference.

3. **CHANGELOG.md has the dated entry.** New section at the top of the file:
   ```
   ## vX.Y.Z - YYYY-MM-DD

   <bullet list of changes; see prior entries for style>
   ```

4. **Tests, lint, type-check, format pass.**
   ```bash
   ruff check src tests examples benchmarks
   ruff format --check src tests examples benchmarks
   mypy src
   pytest -q
   ```

5. **Canon audit passes.**
   ```bash
   bash scripts/canon_audit.sh --self-test
   bash scripts/canon_audit.sh
   ```
   Both MUST exit 0. Any hit is a release blocker.

6. **Benchmark snapshots stable.** Either:
   - Existing snapshots match (no measurement-output drift); or
   - The drift is intentional, captured in a new dated snapshot file, and the test path updated to point at it. Document the drift in CHANGELOG.

   ```bash
   pytest tests/test_benchmarks.py -q
   ```

7. **Coverage threshold met.** The CI gate requires `--cov-fail-under=95`. Run locally to verify:
   ```bash
   pytest --cov=clarethium_touchstone --cov-fail-under=95 -q
   ```

8. **Build artifacts produce cleanly.**
   ```bash
   rm -rf dist/ build/ src/*.egg-info/
   python -m build
   ls dist/                  # should contain sdist + wheel
   ```

9. **Wheel content check.** The wheel MUST contain only the public-canon surface. Verify no out-of-scope files slipped in:
   ```bash
   unzip -l dist/clarethium_touchstone-*.whl | head -30
   ```
   Only `clarethium_touchstone/` package files and license/metadata should appear. Any other path is a release blocker.

## Cutting the release

10. **Commit the release prep.**
    ```bash
    git add -A
    git commit -m "Cut vX.Y.Z release: <one-line summary>"
    ```

11. **Tag.**
    ```bash
    git tag -a vX.Y.Z -m "vX.Y.Z"
    ```

12. **Push.**
    ```bash
    git push origin main
    git push origin vX.Y.Z
    ```

13. **Publish to PyPI.** Inject the PyPI API token at child-process scope only; never write it to `~/.pypirc`, never export it into the shell environment, never paste it into chat or logs:

    ```bash
    TWINE_USERNAME=__token__ \
        TWINE_PASSWORD=<your PyPI token> \
        python -m twine upload dist/*
    ```

    TestPyPI smoke run first (recommended for any release):

    ```bash
    TWINE_USERNAME=__token__ \
        TWINE_PASSWORD=<your TestPyPI token> \
        python -m twine upload --repository testpypi dist/*
    ```

    Maintainer-specific credential-loading invocation is documented in `AGENTS.md` under the Credentials and tokens section. Future agents working in this repository: read AGENTS.md before asking for tokens; the canonical token source for the maintainer is documented there.

14. **GitHub release.** Create a GitHub Release linked to the tag with the CHANGELOG entry as the release notes:

    ```bash
    gh release create vX.Y.Z --title "vX.Y.Z" --notes-from-tag
    ```

## Post-release

15. **Bump to next dev version.** Avoid the risk of the next pre-release commit being mistaken for the released version:
    ```python
    # src/clarethium_touchstone/_version.py
    __version__ = "0.1.1.dev0"
    ```
    Mirror in `pyproject.toml`.

16. **Announce.** Once announce channels exist (mailing list, blog, social), share the release notes.

## Hotfix releases

A hotfix release (0.1.0 → 0.1.1) skips the new-feature scope of a normal minor release. The pre-release checklist is unchanged; the CHANGELOG entry MUST name the specific bug fixed and the regression test that prevents recurrence.

## Coordinating Standard and library bumps

When the Standard advances:

- A Standard minor bump (1.0 → 1.1) is additive; existing library versions remain conformant against the prior Standard version. A library release that newly implements 1.1 features bumps the library minor version.
- A Standard major bump (1.x → 2.0) is breaking; conforming library releases coordinate the bump.

`CITATION.cff` carries the structured Standard-version reference; update it in the same commit that updates the Standard text.
