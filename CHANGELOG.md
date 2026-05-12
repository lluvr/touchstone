# Changelog

All notable changes to Touchstone (Standard and library) are documented here.

The Standard and library are versioned independently. Standard versions track methodology evolution; library versions track implementation releases.

---

## 2026-05-12: production-readiness round

Follows the same-day polish pass below. Closes a structured gap list identified in an external-perspective stress test: completes Standard sections that were marked pending, adds small-N statistical corrections to the benchmark headline, cleans up dead-end API surface, exposes Layer 11 extensibility, expands adopter documentation, and adds release / CI discipline.

**Standard (1.0.0-draft.3 → 1.0.0-draft.4):**

- **§2 Terminology** written. Operational definitions for Output, Source, Claim, Evidence, Layer, Conforming implementation, Threshold, Baseline generator, Regression baseline.
- **§3.5 Falsifiable construct claims** added. Names the evidence that would invalidate Layer 4, Layer 10, Layer 11, and the §3.1 model-independence claim. Reports of falsification evidence route through the Suggestion process.
- **§5.11** amended. The "Conservative and liberal P-detection modes MAY be implemented" sentence is replaced; only conservative ships in v1.0. Additional modes can land via Suggestion process. The external-entity P-marker set is named as adopter-configurable, with `EXTERNAL_ENTITIES_DEFAULT` as the documented extension point.
- **§8 Reference test cases** fully written. Normative framing: passing the bands asserts reproduction on the packaged corpora to within stated tolerances, NOT construct generalization. Fast-tier corpus caveat is in the section text, not in a pending-callout. Future `tests/reference/` extraction reserved for Standard 1.0.1.
- **§11 Conformance** expanded to §11.1 (requirements), §11.2 (declaration mechanism), §11.3 (invalidation criteria), §11.4 (transitional state). Conformance now routes through `tests/` AND `benchmarks/` together; the canonical test-suite extraction is reserved for Standard 1.0.1.
- **§12 References** restructured into §12.1 (internal benchmarks), §12.2 (normative external references), §12.3 (field positioning, with a table of named prior art), §12.4 (validation citations).
- **Drafting status block** updated. All Section 5-11 content is now substantively complete; the "draft" qualifier remains because independent editor review has not yet happened.
- Standard header version bumped to `1.0.0-draft.4`; `__standard_version__` and `CITATION.cff` synced.

**Benchmark statistical rigor (EXP-081):**

- `benchmarks/exp_081_discrimination/run.py` now computes Hedges' g (small-N correction to Cohen's d) and a 95% bootstrap CI on Cohen's d (stratified percentile, 2000 resamples, fixed seed=0 for determinism).
- Headline numbers added: Hedges' g = -4.835 (vs raw d = -5.238); 95% bootstrap CI on Cohen's d = [-8.926, -4.498]. The CI confirms the effect's sign is stable across resamples; the magnitude is uncertain at N=6/6.
- New `tests/test_benchmarks.py::test_exp_081_aggregate_statistics_stable` pins all three values so a regression in either the gap signal or the aggregation math is caught by CI.
- New dated snapshot `snapshot_2026-05-12.json` saved; the EXP-081 snapshot test path now points at it. Per-output predictions are unchanged from the prior 2026-05-03 snapshot.
- README, getting-started, and the EXP-081 sub-README updated to report the new statistics alongside Cohen's d.

**API stability cleanup (library):**

- **Removed `p_detection_mode` parameter** from the `measure()` and `grounding_decomposition()` public signatures. The parameter was marked `noqa: ARG001 (reserved)` and only ever accepted "conservative"; a dead-end parameter is theater, not API. The `p_detection_mode` field on the return dict remains (informational; always "conservative") with its TypedDict literal narrowed accordingly.
- **Added `external_entities` parameter** to `measure()` and `grounding_decomposition()`. Accepts a sequence of regex pattern strings or `None`. When `None` (default), uses `EXTERNAL_ENTITIES_DEFAULT`. Adopters extending to new domains replace or extend the list; the `EXTERNAL_ENTITIES_DEFAULT` constant is now a public re-export so this is mechanical rather than monkey-patching a private name.
- Six new tests in `test_grounding_decomposition.py` pin: default-list constant, None-uses-default, empty-silences-secondary-signal, replacement, extension via unpacking, end-to-end thread-through `measure()`.
- One internal-file reference subtracted from `measure.py` comments (a name pointing at an internal-only methodology doc); semantics reframed to point at Standard §5.11 instead.

**Adopter experience:**

- `docs/getting-started.md` Layer 1a section gains a "Baseline-generator quality guidance" subsection naming the dimensions that affect reproducibility (model class, temperature, n_baselines, topic specificity, recoverable failures).
- New "Layer 11 external entities" subsection documenting the `external_entities` parameter and the `EXTERNAL_ENTITIES_DEFAULT` extension pattern.
- "What measurements mean" expanded from 3 layer entries to a full table covering all 11 layers, each with the construct, what "high" means, and what it does NOT assert.
- README "Use cases" rewritten with explicit separation of (a) what's actually exercised, (b) what's plausibly suited, (c) what's not yet a production claim.
- New `examples/` directory with `verify_a_summary.py`: a runnable end-to-end script profiling a faithful and an embellished summary against the same source, demonstrating Layer 4 / 10 / 11 outputs and surfacing the Layer 11 scope_assessment when the source is in the saturated regime.

**Process and CI:**

- New `.pre-commit-config.yaml` running ruff (lint + format), YAML/TOML/large-file/EOF hygiene, and the canon audit (self-test + working tree) on every commit.
- New `RELEASING.md` documenting the pre-release checklist, cut sequence, post-release bump, hotfix flow, and Standard/library coordination.
- CI lint scope extended from `src tests` to `src tests examples benchmarks` so example scripts and benchmark runners are held to the same lint+format gate as the library.
- CI test job now enforces `--cov-fail-under=95`; current coverage is 96.78%. Coverage regressions below 95% will block merges.

**Leak sweep follow-through:**

- A forbidden-vocabulary instance caught by the canon audit on this round's own RELEASING.md (in the wheel-content step) and removed before commit. The audit is doing its job: novel leak shapes hit the canon_audit pattern set before they reach the public surface, exactly the AGENTS.md §5b loop.

**What this round did not do (named, deferred):**

- External corpus validation (TRUE, LLM-AggreFact, HaluBench, HaluEval). Multi-day work; the falsification protocol in Standard §3.5 names this as the evidence that would invalidate or extend Layer 10's construct claim.
- Head-to-head benchmarks against AlignScore, MiniCheck, HHEM 2.1, SelfCheckGPT, G-Eval, Lynx. Requires their packages and a shared input set.
- Inter-annotator agreement on EXP-095. Requires a second annotator; Standard §3.5 names IAA below Cohen's κ = 0.7 as the falsification threshold for Layer 11.
- PyPI publication and `v0.1.0` git tag. Release actions to be performed against the project's PyPI organization once approval is granted; the `RELEASING.md` checklist is the source of truth for the cut.
- Constitution of an editor body. Standard §11.4 names this as the transitional state to be resolved.

Tests: 385 pass (6 new for `external_entities`, 1 new for bootstrap pinning; one prior test relaxation tightened). Coverage 96.78% (gate 95%). Lint, format, mypy strict, canon audit (self-test + working tree) all green. EXP-081 snapshot moved to 2026-05-12 (per-output predictions unchanged; new aggregate statistics added).

---

## 2026-05-12: post-release polish pass

Honest-framing and defensive-contract cleanup driven by an external-perspective stress test. No library API or measurement output changes; benchmark snapshots are byte-identical.

**Framing fixes (Standard, README, docs/index.md, sub-READMEs):**

- The EXP-081 reproduction is reframed throughout from "Touchstone reproduces the published d=-5.43" to "internal regression baseline against the recorded `detector_v031` snapshot." There is no external publication of EXP-081; the expected values live in `benchmarks/exp_081_discrimination/ground_truth.json` and are authored by this project.
- Standard §8.1 and §9.2 corrected: the EXP-081 corpus is single-vendor (xAI grok-4-1-fast, 12 documents), not the four-vendor plural ("Anthropic, Gemini, OpenAI, and xAI/Grok families") previously claimed. EXP-095 multi-vendor framing kept.
- The "auditor cannot be made of the same material as the audited" slogan is replaced with a precise claim ("scoring substrate does not invoke an LLM on the output being measured; Layer 1a calls an LLM for baseline generation, not output scoring") in README, Standard §1.1, and docs/index.md. The slogan overclaimed against AlignScore-class small-discriminator counterexamples; the narrower claim is defensible.
- README adds a §Limitations section naming what is not demonstrated: no external corpus validation (TRUE, LLM-AggreFact, HaluBench, HaluEval), no head-to-head baselines (AlignScore, MiniCheck, HHEM, SelfCheckGPT, G-Eval), single-vendor EXP-081 corpus, small-N statistics without Hedges' g or bootstrap CI, Layer 11 entity list domain-biased to three source domains, no constituted editor body.
- EXP-095 surfaces the MAE vs full manual classification (0.12-0.13 across G/F/P) as a top-level metric alongside MAE vs the prior detector (0.02-0.04). Both are recorded; the manual-classification number is the honest external comparison; the prior-detector number is the regression check.

**Falsifiable-claim fixes:**

- `CITATION.cff` abstract: removed the "five layers for specification compliance verification (Section 6)" sentence. Section 6 is reserved for Standard 1.1 with no per-layer breakdown; the claim of "five layers" was not in the Standard text.
- `docs/index.md`: dropped the same "five layers, Section 6" table; replaced with a sentence pointing at Standard 1.1 as the venue where Section 6 lands.
- `src/clarethium_touchstone/_version.py`: `__version__` set to `"0.1.0"` to match `pyproject.toml`. The installed package previously reported `"0.1.0.dev0"`, contradicting the wheel metadata and CHANGELOG headers. `__standard_version__` set to `"1.0.0-draft.3"` to match the Standard header.
- Standard §5.3, §10, Appendix C: language on the `fabrication_rate` alias amended. The alias was removed during pre-1.0 greenfield cleanup (per CHANGELOG 2026-05-03); previous Standard text said the alias "MUST be retained at v1.0 and removed in v2.0," making the reference implementation non-conformant against its own Standard. Amended to record that the alias is not part of Standard 1.0 and `instability_rate` is the canonical field name.
- Standard Appendix C Layer 4 row: "0% FPR validated" sharpened to "97.1% extraction recall on 70 manually annotated digit-formatted claims; 0/309 numbers incorrectly flagged unsourced on self-source documents (string-equality regression check, not independent validation)." The "0% FPR" framing was tautological on self-source files. The same sharpening landed in the in-code docstring at `measure.py:source_matching`.

**Defensive-contract fixes (library):**

- `_compute_heading_defaultness` now wraps the caller-supplied `baseline_generator` in a try/except and validates that the return value is a string. Exceptions raised by the user's LLM client (rate limits, network errors, content filters, arbitrary SDK quirks) are caught and counted as failed calls rather than propagated out of `measure()`. Non-string returns are also treated as failed. Three new tests in `test_structural_profile.py` pin the defensive paths (exception, mixed failures, non-string return). Public docstrings updated to document the permissive contract.

**Documentation fixes:**

- `README.md` and `docs/getting-started.md` install paths lead with a Python virtualenv so PEP-668 does not block the editable install on modern Debian/Ubuntu/Mac-homebrew Pythons.
- `docs/getting-started.md` adds a "Scope and locale" section naming the English-only and Markdown-only validated scope, plus the empty-input behavior (returns `"low"` precision, does not raise).
- `README.md` Citation section now ships BibTeX entries for both the Standard and the library, with explicit `note = {Version 1.0.0-draft.3}` for the Standard so adopter citations reflect the draft state. The "BibTeX entry will be provided with the first published release" placeholder is retired.
- `_GFP_EXTERNAL_ENTITIES` documentation: the hardcoded entity list is named as empirically seeded from the three EXP-095 source domains (Apple Q1 FY2026, BLS March 2026, OASIS-4 / Wegovy). The function docstring for `grounding_decomposition` surfaces the domain bias so adopters on new domains know to author a parallel list with false-positive control.

**Governance language:**

- `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CONTRIBUTING.md`, and `SUGGESTIONS/PROCESS.md` no longer route enforcement, disclosure, or review through "the editor body" as if that body operates today. The Standard reserves formal certification by an editor body to a future version once one is constituted (§11); until then, all responsibilities sit with the project maintainers. Security disclosure and code-of-conduct reports route through GitHub Security Advisory.
- Standard §11 adds a transitional clause naming the current state honestly: until an editor body is constituted, the reference test suite at (1) is authored by the same maintainers who author the Standard, so self-certification against it is consistency with the reference implementation, not independent verification.
- Other public-canon leak shapes ("operator-authored," "Operator finalization required," "operator's research corpus") rewritten or removed per the AGENTS.md discipline. Subtraction was preferred over substitution where the surrounding paragraph stood without the offending clause.

**What this pass did not do (named, deferred):**

- Run Touchstone on an external corpus (TRUE, LLM-AggreFact, HaluBench, HaluEval). Days-to-weeks of work; required to move from regression baseline to construct-validity evidence.
- Head-to-head benchmarking against AlignScore, MiniCheck, HHEM 2.1, SelfCheckGPT, G-Eval, or Lynx.
- Hedges' g correction or bootstrap confidence intervals on the EXP-081 effect size.
- Cutting a `v0.1.0` git tag (none exists today).
- Constituting an editor body.
- Resolving the touchstone.clarethium.com docs site state.

**Follow-up sweep (same day):**

- `tests/reference/README.md` rewritten. The previous "Validation pedigree" block carried stale claims (out-of-date test counts; "148 align self-tests" after `align()` was removed; a four-vendor plural for EXP-081; "Studies 8-9 discriminant validity (100 pairs)" referencing internal study identifiers with no public resolver). The replacement describes the directory's planned role honestly without the stale specifics.
- `CHANGELOG.md` polish-pass entry: a reference to "§3c" (a section in an internal discipline document) was rewritten to point at AGENTS.md, the public-canon discipline doc that ships in the repo.
- `SECURITY.md` and `docs/getting-started.md`: removed a "Section 9 of the methodology" reference for gaming vectors. Standard §9 (Implementation guidance) does not enumerate gaming vectors; the references were either stale (pointing at an earlier draft) or ambiguous (pointing at the separate Lodestone methodology canon without naming it). Both replaced with a direct statement that Touchstone's pattern set is public and an actor aware of the regex can evade it.

Tests: 378 pass (3 new defensive tests for Layer 1a). Lint, format, type check, canon audit (self-test + working tree) all green. Both benchmark snapshots byte-identical (no measurement-output drift).

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
