# Changelog

All notable changes to Touchstone (Standard and library) are documented here.

The Standard and library are versioned independently. Standard versions track methodology evolution; library versions track implementation releases.

---

## 2026-05-03: Library reference implementation feature-complete

All eleven measurement layers from Standard Section 5 are implemented in `clarethium-touchstone`. The top-level `measure()` orchestrator composes them end-to-end.

Layers extracted (in order):

- Layer 4 source matching (number provenance via 8 type-aware regex patterns; 0% FPR on self-source documents validated by EXP-081)
- Layer 2 claim density (numerical and causal claim counts per 1000 words)
- Layer 1b mechanism ratio + 1c assertion ratio (1a reserved for LLM injection)
- Layer 7 presentation features (TTR, FK grade, formatting density, assertiveness, named-concept count)
- Layer 9 information novelty (cumulative-vocabulary novelty, OLS decay slope)
- Layer 6 vocabulary proximity (per-sentence content-word overlap with source)
- Layer 10 quality profile composite (substance vs presentation index + overclaiming gap)
- Layer 5 entity provenance (5 regex patterns: persons, organisations, attributions, citations, CamelCase orgs)
- Layer 8 epistemic calibration (cross-layer per-sentence assertion grounding via 3 independent grounds)
- Layer 3 temporal instability (cross-version number stability across regenerations)
- Layer 11 grounding decomposition (per-sentence Grounded / Framed / Projected classification with arithmetic-derivation checker)
- `measure()` orchestrator (composes all 11 layers, returns `MeasureResult` per `types.py`)
- Layer 1a heading defaultness (vendor-neutral via `BaselineGenerator = Callable[[str], str | None]` — caller supplies their own LLM client)

The library is vault-faithful: regex patterns, thresholds, filtering rules, and validation caveats are preserved from the operator's research vault. Vault-faithful surprises are pinned with explicit tests so future drift is visible.

Test coverage: 338 tests pass on Python 3.10, 3.11, 3.12. Lint (ruff), format (ruff format), type check (mypy strict), and build (`python -m build`) all green in CI.

Outstanding before first PyPI release:
- PyPI Clarethium organization application approval
- Operator-authored Standard sections (Terminology, References, Appendices A and B)

## 2026-05-02: Initial bootstrap

Repository created at `Clarethium/touchstone`. Initial structure:

- `README.md` — repository orientation
- `CHANGELOG.md` (this file)
- `STANDARDS/touchstone-1.0.md` — Touchstone Standard 1.0 (in drafting)
- Library scaffold (`src/clarethium_touchstone/`) with TypedDicts in `types.py` and stub functions in `measure.py` / `align.py`
- CI workflow (lint, type check, test matrix, build distribution)
- Custom domain `touchstone.clarethium.com` via GitHub Pages

PyPI organization application pending approval. Library extraction from research vault in progress.

Architecture committed:
- Touchstone is a Clarethium sub-brand at `touchstone.clarethium.com`
- Repository under `github.com/Clarethium/touchstone` organization
- Standard document under CC-BY 4.0
- Library under Apache 2.0 (or MIT, pending final decision)
- PyPI package name: `clarethium-touchstone` (or fallback if `touchstone` namespace becomes available)

## Standard versioning policy

Touchstone Standard follows semantic versioning:

- **Major (1.0 → 2.0):** Breaking changes to required fields, methodology, or thresholds. Existing implementations require updates to remain conformant.
- **Minor (1.0 → 1.1):** Additive changes — new optional layers, new requirement types, new measurement dimensions. Existing implementations remain conformant for the previous version.
- **Patch (1.0 → 1.0.1):** Editorial changes, clarifications, typo corrections, expanded examples. No methodology changes.

## Library versioning policy

The `clarethium-touchstone` library follows semantic versioning independently:

- Library version aligns with the Standard version it implements (e.g., library 1.0.x implements Standard 1.0.x)
- Library patches can ship without Standard changes
- Library may temporarily implement features ahead of Standard ratification (flagged as experimental)
- Library deprecations announced one minor version before removal

---

## Pending releases

- **Standard 1.0** — drafting in progress (May 2026 target)
- **`clarethium-touchstone` 0.1.0** — initial library release (Q3 2026 target, dependent on PyPI approval and substrate extraction)
