# Contributing to Touchstone

Touchstone is a small, single-maintainer open-source project by Lovro Lucic.
This document covers how the codebase is laid out, how to set it up, and the
conventions and tests a change should follow.

Touchstone has two parts:

- **The Touchstone Standard** (in `STANDARDS/`) is the specification. Changes
  are deliberate and versioned per Section 10 of the Standard.
- **The `clarethium_touchstone` library** is the reference implementation of
  the Standard.

## Development setup

```bash
git clone https://github.com/Clarethium/touchstone.git
cd touchstone
pip install -e ".[dev]"
pytest
```

Tests should pass before any change lands. Type checking and linting use
`mypy` and `ruff`:

```bash
ruff check src tests
mypy src
```

## Standard and library

The library implements the Standard. Where library behavior diverges from the
Standard, the Standard takes precedence and the library is the bug. New
measurement layers are added to the Standard first, then implemented in the
library: the Standard is the deliberate specification and the library follows
it.

## Code style

- Python 3.10+
- Type hints everywhere; `mypy` strict mode
- `ruff` for formatting and linting
- Docstrings on all public functions
- TypedDicts for return types per `types.py`
- No AI-attribution in commit messages; no em-dashes or smart quotes in
  committed content

## Test discipline

The library's value depends on being correct:

- All public functions have unit tests.
- The reference test suite under `tests/reference/` is versioned with the
  Standard; do not modify it without a corresponding Standard change.
- Cross-layer integration tests verify behaviour across layers that share
  helpers (`tests/test_cross_layer.py`); the empirical-validation benchmarks
  live under `benchmarks/`.

## Contact

Questions or security reports: `hello@clarethium.com`.
