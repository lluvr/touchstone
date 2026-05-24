# API reference

Stable public surface of the `clarethium_touchstone` library. Everything
documented here is exported from the top-level package and covered by the
versioning rules in `STANDARDS/touchstone-1.0.md` §10.

For methodology background read `docs/methodology.md` first; for deployment
guidance read `docs/production_readiness.md`. This page is the lookup
reference once those have been internalised.

## Index

- [Production-shaped API: `Verifier`](#verifier)
  - [`Verifier(calibration, mode)`](#verifiercalibration-mode)
  - [`Verifier.score(text, source, ...) -> VerifierResult`](#verifierscoretext-source---verifierresult)
  - [`Verifier.with_calibration(calibration)`](#verifierwith_calibrationcalibration)
- [`VerifierResult`](#verifierresult)
- [`UnsupportedSpan`](#unsupportedspan)
- [`VerifierMode` and `VERIFIER_MODES`](#verifiermode-and-verifier_modes)
- [Low-level API: `measure()`](#measure)
- [Layer-11 regime classifier: `assess_derivation_regime()`](#assess_derivation_regime)
- [`EXTERNAL_ENTITIES_DEFAULT`](#external_entities_default)
- [Conventions and scope](#conventions-and-scope)
- [Touchstone MCP](#touchstone-mcp)

---

## `Verifier`

The production-shaped entry point. Calibrated logistic regression over the
substrate features defined in Standard §13.3, with optional blending against
external baselines (MiniCheck, AlignScore) or a frontier LLM judge.

```python
from clarethium_touchstone import Verifier

v = Verifier()
result = v.score(text="...", source="...")
```

The default calibration is fitted on the RAGTruth Summary test split
(70/30 stratified, `n_train=629`). On any other input distribution adopters
SHOULD recalibrate via `Verifier.with_calibration(...)`. The honest accuracy
envelope is documented in `docs/production_readiness.md` §4.2.

### `Verifier(calibration, mode)`

Constructor.

| Argument | Type | Default | Description |
|---|---|---|---|
| `calibration` | `dict \| None` | `DEFAULT_CALIBRATION_2026_05_17` | Custom calibration dict in the embedded format. See `src/clarethium_touchstone/_calibration.py` for the schema. |
| `mode` | `VerifierMode \| None` | `None` (auto-select) | Explicit mode selector. Omit to let `score()` infer from which baseline arguments are supplied. |

### `Verifier.score(text, source, ...) -> VerifierResult`

Score one `(text, source)` pair. The mode is auto-selected from which
optional baseline arguments are supplied; explicit `mode=` on the
constructor overrides auto-selection.

| Argument | Type | Default | Description |
|---|---|---|---|
| `text` | `str` | required | The AI-generated output to verify. |
| `source` (keyword) | `str` | required | The grounding source the output should be supported by. |
| `minicheck_supported_prob` | `float \| None` | `None` | MiniCheck supported-probability in [0, 1] (caller invokes MiniCheck themselves). Higher means more supported. |
| `alignscore_supported_prob` | `float \| None` | `None` | AlignScore supported-probability in [0, 1]. Higher means more supported. |
| `judge_hallucinated_prob` | `float \| None` | `None` | LLM-judge probability that the output is **hallucinated** in [0, 1]. Sign convention is inverted relative to MiniCheck/AlignScore because frontier judges return the detector-side probability directly. |
| `judge_alpha` | `float` | `0.3` | Substrate weight in the substrate+judge linear blend. Tune on your held-out data; default is the cross-corpus mean from `production_readiness.md` §4.3.1. |
| `top_k_unsupported` | `int` | `3` | Maximum number of unsupported spans to return. |

**Mode auto-selection rules** (in priority order):

1. `judge_hallucinated_prob` supplied → `substrate_plus_judge`. Cannot be combined with MiniCheck or AlignScore in the same call.
2. Both `minicheck_supported_prob` AND `alignscore_supported_prob` supplied → `substrate_plus_minicheck_alignscore`.
3. Only `minicheck_supported_prob` supplied → `substrate_plus_minicheck`.
4. Neither supplied → `substrate_only`.

### `Verifier.with_calibration(calibration)`

Class-method constructor that takes a calibration dict directly. Equivalent
to `Verifier(calibration=...)`. Used by adopters who have re-fitted the
logistic regression on their own held-out training data.

---

## `VerifierResult`

Frozen dataclass returned from `Verifier.score()`.

| Field | Type | Description |
|---|---|---|
| `prob_hallucinated` | `float` in [0, 1] | Calibrated probability that the output is hallucinated. |
| `mode` | `VerifierMode` | Which calibration mode produced this score. |
| `scope` | `"validated" \| "limited_signal" \| "insufficient_input"` | Signal-quality classification. See [Scope](#scope) below. |
| `scope_notes` | `list[str]` | Diagnostics naming which substrate signals fired, which preconditions failed, and any text-level reasons (e.g. insufficient length). In a baseline-composition or judge-blend mode on the default calibration, also carries a reminder that the composed weights are not recalibrated per distribution. |
| `signal_breakdown` | `dict[str, float]` | Per-feature contribution to the logit (intercept + coefficient×feature terms). Sums to `logit(prob_hallucinated)` for substrate-only mode; for `substrate_plus_judge` the breakdown additionally exposes `substrate_prob`, `judge_hallucinated_prob`, and `judge_alpha`. |
| `top_unsupported` | `list[UnsupportedSpan]` | Span-level localization; P-classified sentences first, then F-classified ranked by ascending grounding_score, capped by `top_k_unsupported`. |
| `layer_outputs` | `MeasureResult` | Raw `measure()` output for drill-down. Same shape as `clarethium_touchstone.measure()` returns. |

### `should_flag(threshold=0.5, *, fail_open=False)`

Convenience boolean for the binary flag/no-flag decision.

| Argument | Type | Default | Description |
|---|---|---|---|
| `threshold` | `float` | `0.5` | Probability cut-off. `production_readiness.md` §2 reports F1-optimal thresholds of 0.07-0.27 on the external corpora; **the default 0.5 under-flags for any production deployment** and is provided as a safety-tilted out-of-box default. Tune on held-out data before deploying. |
| `fail_open` | `bool` (keyword) | `False` | If True, ignore `scope` and flag purely on `prob_hallucinated`. Set this only when the surrounding pipeline independently inspects `scope_notes` for low-signal results. With the default False, `insufficient_input` and `limited_signal` results never auto-flag. |

### Scope

A `VerifierResult` is classified into one of three scopes that gate
whether `should_flag()` will act on the probability:

- **`"validated"`** — Layer 6 plus at least one of Layers 4 / 5 / 11
  produced informative readings. Calibrated on this regime; act on
  `prob_hallucinated`.
- **`"limited_signal"`** — The input was substantive (above the
  character floor and at least one substrate signal fired) but the
  validated combination (Layer 6 plus one of L4/L5/L11) did not hold.
  The probability may be intercept-dominated. Treat as low-confidence;
  route to human review.
- **`"insufficient_input"`** — One of: (1) text is empty or
  whitespace-only after stripping; (2) no substrate signal had its
  precondition met regardless of length; (3) text is below
  `MIN_INPUT_CHARS` non-whitespace characters AND fewer than two
  substrate signals fired. Do not act on `prob_hallucinated`.

Per-signal preconditions:

| Signal | Precondition |
|---|---|
| `l4` (source matching) | At least one digit-formatted number extracted. |
| `l5` (entity provenance) | At least five entities extracted. |
| `l6` (vocabulary proximity) | At least one sentence with scoreable content words. |
| `l11` (G/F/P decomposition) | At least one sentence classified. |

Non-English text is OUT OF VALIDATED SCOPE per Standard §9.2; in practice
non-English inputs typically classify as `"limited_signal"` because the
English-only Layer 6 stopword list and content-word filters strip most
non-Latin content.

---

## `UnsupportedSpan`

Frozen dataclass: one entry in `VerifierResult.top_unsupported`.

| Field | Type | Description |
|---|---|---|
| `sentence` | `str` | The sentence text, trimmed. |
| `sentence_index` | `int` | Zero-indexed position in the order `measure()` segments the output. |
| `layer11_primary` | `"P" \| "F"` | Layer 11 G/F/P classification (G is excluded from `top_unsupported`). |
| `p_markers` | `list[str]` | If `layer11_primary == "P"`, the triggering markers: `"unsourced_numbers"`, `"external_entities"`, `"unsourced_years"`. Empty for `"F"`. |
| `grounding_score` | `float \| None` | Layer 11 grounding score in [0, 1] for F-classified sentences; `None` for P. |

---

## `VerifierMode` and `VERIFIER_MODES`

```python
from clarethium_touchstone import VerifierMode, VERIFIER_MODES
```

`VerifierMode` is a `Literal` of the four mode strings.

`VERIFIER_MODES` is a tuple of those same strings for runtime iteration:

```python
import argparse
from clarethium_touchstone import VERIFIER_MODES

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=VERIFIER_MODES, default="substrate_only")
```

The four modes:

| Mode | Required baseline arguments | When to use |
|---|---|---|
| `"substrate_only"` | None | Default. No external dependencies. Sub-100 ms per 5 KB document. Default-calibrated AUC ≈ 0.67-0.76 on the three external summarization corpora. |
| `"substrate_plus_minicheck"` | `minicheck_supported_prob` | Add the MiniCheck Flan-T5-Large supported-probability. AUC ≈ 0.76. |
| `"substrate_plus_minicheck_alignscore"` | `minicheck_supported_prob` + `alignscore_supported_prob` | Add both LLM-based baselines. AUC ≈ 0.77. |
| `"substrate_plus_judge"` | `judge_hallucinated_prob` | Linear-blend the substrate probability with a frontier LLM judge probability. AUC on the §4.2 corpora ranges 0.78-0.94 depending on judge vendor and cued/blind variant. Mutually exclusive with MiniCheck/AlignScore in the same call. |

---

## `measure()`

Low-level orchestrator that runs every Section 5 measurement layer whose
preconditions are met.

```python
from clarethium_touchstone import measure

result = measure(text="...", source="...")
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `text` | `str` | required | The AI-generated output. |
| `source` | `str \| None` | `None` | Source material. Layers 4, 5, 6, 8, 11 require source; they return `None` in the result dict when source is absent. |
| `topic` | `str \| None` | `None` | Topic string for Layer 1a heading defaultness. Pair with `baseline_generator`. |
| `baseline_generator` | `Callable[[str], str \| None] \| None` | `None` | Vendor-neutral LLM callable. Returns generated baseline document or `None` on failure. |
| `n_baselines` | `int` | `3` | Number of baseline documents Layer 1a samples from `baseline_generator`. Minimum for stable word-union estimation; higher (5-10) gives a more stable baseline word set at the cost of more LLM calls. |
| `comparisons` | `list[str] \| None` | `None` | Other versions of the output for Layer 3 temporal instability. |
| `external_entities` | `Iterable[str] \| None` | `EXTERNAL_ENTITIES_DEFAULT` | Layer 11 secondary P-signal regex list. |

Returns a `MeasureResult` (TypedDict) keyed by layer name. Each key maps to
either the layer's structured output or `None` when its precondition is
unmet. See `src/clarethium_touchstone/types.py` for the full schema.

Per-layer keys: `structural_profile` (Layer 1), `claim_density` (Layer 2),
`temporal_instability` (Layer 3), `source_matching` (Layer 4),
`entity_provenance` (Layer 5), `vocabulary_proximity` (Layer 6),
`presentation_features` (Layer 7), `epistemic_calibration` (Layer 8),
`information_novelty` (Layer 9), `quality_profile` (Layer 10),
`grounding_decomposition` (Layer 11).

---

## `assess_derivation_regime()`

Layer-11 standalone regime classifier. Useful for UIs that want to surface
a "trust this signal" hint before running the full measurement.

```python
from clarethium_touchstone import assess_derivation_regime

assessment = assess_derivation_regime(source_num_count=14)
# {"derivation_regime": "saturated",
#  "cross_reference_layer_4_for_numbers": True,
#  "note_user_facing": "...", ...}
```

| Argument | Type | Description |
|---|---|---|
| `source_num_count` | `int` | Count of digit-formatted numbers in the source. |

Returns a dict with the regime classification (`"diagnostic" \| "transition" \| "saturated"`) and user-facing guidance text. Boundaries are empirically validated against EXP-095 Monte Carlo data (< 5 = diagnostic, [5, 10) = transition, ≥ 10 = saturated).

---

## `EXTERNAL_ENTITIES_DEFAULT`

```python
from clarethium_touchstone import EXTERNAL_ENTITIES_DEFAULT
```

Tuple of regex patterns (case-insensitive) used as the default Layer 11
secondary P-signal entity list. Empirically seeded from the three EXP-095
source domains (GLP-1 drugs, Apple products, BLS labor terms); biased
toward pharmaceuticals, tech products, and US labor terminology.

Adopters extending Touchstone to new domains MUST author their own list
(Standard §5.11). Replace entirely or extend with iterable unpacking:

```python
result = measure(
    text,
    source=source,
    external_entities=[*EXTERNAL_ENTITIES_DEFAULT, r"\bextra-pattern\b"],
)
```

---

## Conventions and scope

- **Layer outputs are NEVER inferred from inputs the layer was not designed
  to handle.** A layer with unmet preconditions returns `None` in the
  `MeasureResult` dict; the Verifier zeros the corresponding feature so it
  contributes nothing to the logit.
- **Default threshold under-flags.** `should_flag(threshold=0.5)` is a
  safety-tilted out-of-box default. F1-optimal thresholds on the published
  external corpora are 0.07-0.27. Tune on your own held-out data.
- **Scope gating is the production-safe default.** `should_flag()` returns
  False on `"insufficient_input"` and `"limited_signal"` scopes unless the
  caller opts in via `fail_open=True`. This prevents pipeline-bursting
  false positives on degenerate inputs.
- **English-only validated scope.** Layer 6 stopwords and content-word
  filters are English. Non-English text typically classifies as
  `"limited_signal"`. Adopters extending to other languages MUST document
  their validation per Standard §9.2.
- **Calibration is corpus-conditional.** The shipped calibration is fitted
  on RAGTruth Summary. The fitted `l4_unsourced` coefficient is **negative**
  on this corpus, a documented finding (see `methodology.md` §3.4) that
  reflects RAGTruth's specific hallucination distribution; on adversarial
  fabricated-number corpora the coefficient should be positive. Adopters
  with a different input distribution MUST recalibrate; the
  `with_calibration()` constructor accepts the re-fitted coefficients.

---

## Touchstone MCP

Touchstone MCP is the Model Context Protocol server, shipped inside the
[`touchstone-mcp`](https://pypi.org/project/touchstone-mcp/) package as
`src/touchstone_mcp.py`. Install:

```bash
pip install touchstone-mcp
```

The package bundles the `clarethium_touchstone` library and installs
with `fastmcp` as its only third-party dependency. This
registers the `touchstone-mcp` console script (stdio transport by
default) so any MCP host can attach it. Four tools exposed: `verify`,
`measure`, `assess_derivation_regime`, `list_modes`. Each mirrors the
corresponding Python API documented on this page.

Programmatic use:

```python
from touchstone_mcp import build_server

server = build_server()
server.run()                 # stdio transport (default)
```

Full host-wiring instructions (Claude Desktop, Claude Code, Cursor,
custom) and the tool catalog are in [`mcp.md`](mcp.md). The
`clarethium_touchstone` library itself imports without any third-party
dependency; FastMCP is the package's only third-party requirement.

---

## Source-of-truth precedence

When library behaviour and the Standard disagree, **the Standard takes
precedence**. The Standard text in `STANDARDS/touchstone-1.0.md` is the
canonical reference. This API page documents the reference implementation;
the conformance surface is defined by the Standard.
