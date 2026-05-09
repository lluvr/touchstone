# Changelog

All notable changes to Touchstone (Standard and library) are documented here.

The Standard and library are versioned independently. Standard versions track methodology evolution; library versions track implementation releases.

---

## v0.1.0 - 2026-05-09

Initial public release of Touchstone. Includes:

- **Touchstone Standard 1.0** at `STANDARDS/touchstone-1.0.md` (CC-BY 4.0). v0.1
  scope is Section 5 (output profiling, eleven measurement layers). Section 6
  (Specification Compliance) is reserved for a future release.
- **`clarethium-touchstone` Python reference implementation** (Apache 2.0).
  Dependency-free; Layer 1a accepts a vendor-neutral `BaselineGenerator`
  callable so the user supplies their own LLM client.
- **Two reproducibility benchmarks** in `benchmarks/`. EXP-081 (adversarial
  discrimination) reproduces the published Cohen's d=-5.43 finding with
  Touchstone d=-5.238, 100% per-output gap-direction agreement, MAE 0.014
  on unsourced rate. EXP-095 (grounding decomposition) reaches 100%
  P-direction agreement on existence (P>0 vs P=0) across 13 hand-classified
  outputs from 3 model families against 3 source documents; per-output P
  magnitude differs from manual range on 4/13 outputs.
- **375 tests** pass on Python 3.10 / 3.11 / 3.12; CI green; snapshot drift
  detection on both benchmarks pinned via byte-match pytest assertion.

Patches 2 and 3 (multi-currency extraction; scaled-integer forms with raw-form
source-match cascade fix) and Layer 11 `scope_assessment` (derivation-regime
classifier) are included. For the per-patch development sequence that landed
into this release, see the dated entries below.

---

## 2026-05-03: Patch 2 (multi-currency) + Patch 3 (scaled-integer) shipped

After two earlier sessions deferring these patches (concerned that
Frame Check's port introduced cascade bugs), the benchmarks shipped
mid-session provide regression cover. Both patches landed with the
proper substrate-quality designs:

- **Patch 3 (scaled-integer):** "1.5 trillion", "6 million" forms
  now extract correctly. Cascade bug Frame Check ships (extracted
  "8 trillion" gets normalized to "8000000000000" string, then
  source matching searches that exact digit string in source text
  and fails when source uses the same scale form) is FIXED in
  Touchstone via a raw-form fallback path. See test_source_matching::
  test_scale_word_extraction_with_raw_form_source_match.
- **Patch 2 (multi-currency):** ``[$€£¥₹]`` symbols now match. Doc
  "€30" + source "€30" → grounded; doc "€30" + source "$30" →
  unsourced (DIFFERENT currencies, correct flag). UnsourcedNumber
  TypedDict gains optional ``currency`` field surfaced in
  unsourced_details for downstream consumers.

Both patches are backward-compatible with USD-only corpora (EXP-081
benchmark unchanged: Cohen's d=-5.238). EXP-095 output #16 (xAI BLS
run 3) moved P 0.026 → 0.051 toward manual estimate [0.10, 0.15] -
direct evidence that stricter source-side derivation (now that
"7.2 million" extracts as 7200000 instead of decimal 7.2) reduces
the derivation-checker false-positive rate documented in the
methodology.

Cross-scale matching (doc "1500 billion" vs source "1.5 trillion",
same magnitude) is pinned as a known limitation in
test_known_limitation_cross_scale_false_negative; proper
magnitude-aware redesign is a future patch.

## 2026-05-03: scope_assessment for Layer 11 + EXP-095 benchmark suite

- **Patch 1 landed (deferred from earlier session):** Layer 11
  ``grounding_decomposition`` now returns a ``scope_assessment`` field
  classifying the source's derivation-checker regime. Boundaries are
  empirically validated (< 5 diagnostic, [5,10) transition, ≥ 10 saturated)
  and align with the methodology doc and Monte Carlo FPR data
  (53% at N=5, 97% at N=10). New public helper
  ``assess_derivation_regime(source_num_count)`` returns the same
  ``ScopeAssessment`` dict for any caller wanting the regime
  classification standalone (e.g., a UI that displays "trust this
  signal" guidance before measurement begins).

  This addresses the documented EXP-095 output #16 drift case: when
  Touchstone reports P=0.026 for a 14-number source (saturated
  regime), the scope_assessment field now explicitly tells consumers
  to cross-reference Layer 4 for numerical fabrication. The drift is
  no longer silent.

- **EXP-095 benchmark suite shipped:** ``benchmarks/exp_095_grounding/``
  validates Layer 11 against 13 hand-classified outputs from the
  EXP-095 corpus. Results: P-direction agreement with manual
  classification is 100%; MAE vs documented detector v0.3.1 is
  0.02-0.04 in aggregate (with documented per-output drift surfaced
  honestly in the README). Snapshot file pinned via byte-match
  pytest assertion; CI catches silent drift on any future change
  affecting Layer 11 predictions.

## 2026-05-03: v0.1 scope locked to Section 5 measurement; align/profile dropped from public API

- Frame Check fork-patch port: paragraph-aware sentence splitter for
  Layer 2 (Patch 4 from CLARETHIUM_MEASURE_SYNC.md)
- Greenfield cleanup: ``fabrication_rate`` legacy alias removed
  (Patch 5; no v0.x deprecation window to honour)
- Public API trimmed: ``align()``, ``profile()``, and the entire
  ``clarethium_touchstone.align`` module dropped from v0.1.
  Standard Section 6 (Specification Compliance) is reserved for a
  future release. The pre-port stubs raised ``NotImplementedError``
  on every call; cleaner to remove the API surface than ship
  misleading entry points. Section 6 will return in Standard 1.1
  with the same pinned-behaviour discipline as Section 5.

Multi-currency, scaled-integer, and Layer 11 ``scope_assessment``
fork patches (Patches 1, 2, 3 from the diff) are deferred. Each
requires a deeper redesign than a direct port: currency and scale
should be first-class fields on extracted numbers (not lossy
type-tag overloads), and the regime classifier should be a
standalone function with documented constants. A discrimination
benchmark suite (separate session) precedes any further detection-
accuracy patches.

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
- Layer 1a heading defaultness (vendor-neutral via `BaselineGenerator = Callable[[str], str | None]` - caller supplies their own LLM client)

The library pins regex patterns, thresholds, filtering rules, and validation caveats so future drift is visible. Surprising behaviours are explicitly tested; any change is intentional and version-bumped.

Test coverage: 338 tests pass on Python 3.10, 3.11, 3.12 (375 by v0.1.0). Lint (ruff), format (ruff format), type check (mypy strict), and build (`python -m build`) all green in CI.

## 2026-05-02: Initial bootstrap

Repository created at `Clarethium/touchstone`. Initial structure:

- `README.md` - repository orientation
- `CHANGELOG.md` (this file)
- `STANDARDS/touchstone-1.0.md` - Touchstone Standard 1.0 (in drafting)
- Library scaffold (`src/clarethium_touchstone/`) with TypedDicts in `types.py` and stub functions in `measure.py` / `align.py`
- CI workflow (lint, type check, test matrix, build distribution)
- Custom domain `touchstone.clarethium.com` via GitHub Pages

PyPI organization application pending approval. Reference implementation in progress.

Architecture committed:
- Touchstone is a Clarethium sub-brand at `touchstone.clarethium.com`
- Repository under `github.com/Clarethium/touchstone` organization
- Standard document under CC-BY 4.0
- Library under Apache 2.0 (or MIT, pending final decision)
- PyPI package name: `clarethium-touchstone` (or fallback if `touchstone` namespace becomes available)

## Standard versioning policy

Touchstone Standard follows semantic versioning:

- **Major (1.0 → 2.0):** Breaking changes to required fields, methodology, or thresholds. Existing implementations require updates to remain conformant.
- **Minor (1.0 → 1.1):** Additive changes - new optional layers, new requirement types, new measurement dimensions. Existing implementations remain conformant for the previous version.
- **Patch (1.0 → 1.0.1):** Editorial changes, clarifications, typo corrections, expanded examples. No methodology changes.

## Library versioning policy

The `clarethium-touchstone` library follows semantic versioning independently:

- Library version aligns with the Standard version it implements (e.g., library 1.0.x implements Standard 1.0.x)
- Library patches can ship without Standard changes
- Library may temporarily implement features ahead of Standard ratification (flagged as experimental)
- Library deprecations announced one minor version before removal
