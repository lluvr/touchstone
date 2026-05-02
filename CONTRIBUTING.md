# Contributing to Touchstone

Thanks for your interest in contributing.

Touchstone has two parts that evolve through different processes:

- **The Touchstone Standard** (in `STANDARDS/`) is the canonical specification. Changes are deliberate and versioned per Section 10 of the Standard.
- **The `clarethium-touchstone` library** is the reference implementation of the Standard.

## Quick start for code contributions

```bash
git clone https://github.com/Clarethium/touchstone.git
cd touchstone
pip install -e ".[dev]"
pytest
```

Tests should pass before opening a pull request. Type checking and linting use `mypy` and `ruff`:

```bash
ruff check src tests
mypy src
```

## Proposing changes to the Standard

Changes to the Standard go through the Suggestion process (modeled on Python Enhancement Proposals and Bitcoin Improvement Proposals). The process document will live at `SUGGESTIONS/PROCESS.md` once ratified.

In the interim, propose Standard changes by:

1. Opening an issue describing the proposed change and its motivation.
2. Discussing in the issue thread until the change is well-scoped.
3. Opening a pull request against `STANDARDS/touchstone-1.0.md` with the specific edit and reasoning.
4. The pull request is reviewed by named editors.

Standard changes follow semantic versioning per Section 10. Major changes (breaking) require version bumps; additive changes are minor.

## Proposing changes to the library

Library changes generally do not require Standard changes. Common library contributions:

- Bug fixes against the reference test cases
- Performance improvements
- Documentation improvements
- New integrations (frameworks, languages, runtimes)
- Worked examples

Open a pull request with:

- A clear description of the change
- Tests that cover the change
- Documentation updates where relevant

The library implements the Standard. Where library behavior diverges from the Standard, the Standard takes precedence and the library is the bug.

## Adding new measurement layers

New layers are not accepted into the library without first being added to the Standard. The Standard's authority comes from being the deliberate specification; bypassing it via the library would break that authority.

If you have an idea for a new layer:

1. Open an issue describing the layer and what it measures
2. Discuss whether the layer fits the Standard's scope (model-independent measurement; structural over semantic)
3. If aligned, propose the Standard change first via the Suggestion process
4. Once the Standard accepts the layer, implementation in the library follows

## Reporting discrepancies between library and Standard

If you find a case where the library produces results inconsistent with the Standard's specification, this is a library bug regardless of which behavior is "better." Open an issue with:

- The specific Standard section being implemented
- The library function being called
- Input that triggers the discrepancy
- Expected behavior per the Standard
- Actual library behavior

The library will be fixed to conform.

## Code style

- Python 3.10+
- Type hints everywhere; `mypy` strict mode
- `ruff` for formatting and linting
- Docstrings on all public functions
- TypedDicts for return types per `types.py`

## Test discipline

The library's value depends on being correct. Specifically:

- All public functions MUST have unit tests
- The reference test suite under `tests/reference/` (when populated) is versioned with the Standard; do not modify it without a corresponding Standard change
- Synthetic edge cases SHOULD have tests
- Integration tests SHOULD verify combined `profile()` behavior

## Conduct

Touchstone is an open project. Discussions stay technical. Personal attacks, harassment, and bad-faith behavior are not tolerated. If something feels off, contact the editor body.

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for the full Contributor Code of Conduct (Contributor Covenant 2.1).

## Recognition

Contributors are acknowledged in the changelog and on the Touchstone documentation site once it exists. Substantial contributions to the Standard receive co-author recognition where appropriate per editor body discretion.

## Questions

Open an issue tagged `question`. Email is not the right channel; the work is in public.
