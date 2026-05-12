# Touchstone

Model-independent verification for AI-coupled work.

## What this is

Touchstone names the practice of measuring AI outputs without invoking an AI model to score the AI output. It is one of two open reference artifacts published by Clarethium:

- **Touchstone** validates work against quality standards.
- **Lodestone** orients practice.

The Touchstone Standard specifies eleven measurement layers for output profiling: structural composition, claim density, source matching, grounding decomposition, and others. Ten of the eleven are deterministic regex, structural analysis, string search, and arithmetic; one (Layer 1a, optional) calls an LLM to generate baseline documents on the same topic, not to score the output. The scoring substrate is independent of the model under measurement.

This is a reference specification plus reference implementation. The Standard is the canonical text. The `clarethium-touchstone` library is the reference Python implementation.

## What's here

This repository contains:

- **Touchstone Standard** - the canonical specification (CC-BY 4.0) at `STANDARDS/touchstone-1.0.md`
- **`clarethium-touchstone`** - Python reference implementation (Apache 2.0)

The Standard defines the methodology. The library implements it. Other implementations conforming to the Standard are welcome.

## Status

Pre-launch on PyPI. All eleven Section 5 measurement layers are implemented and tested (385 tests; CI green on ruff lint + format, mypy strict, and the pytest matrix across Python 3.10/3.11/3.12). Test coverage is at 97% with a 95% CI gate. Two internal regression benchmarks ship with the source; they reproduce exactly from a clone. External-corpus validation against TRUE, LLM-AggreFact, HaluBench, and HaluEval is open work; see Limitations.

PyPI organization application is pending. Until then, install from source. On modern Debian/Ubuntu/Mac-homebrew Pythons, install into a virtual environment so PEP-668 does not block the editable install:

```bash
git clone https://github.com/Clarethium/touchstone.git
cd touchstone
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

For development (tests, lint, type check), add the `dev` extra:

```bash
pip install -e ".[dev]"
pytest -q
```

## Quick example

```python
from clarethium_touchstone import measure

text = "Revenue grew 12% to $143M with 25% margins reported."
source = "Revenue grew 12% to $143M with 25% margins."

result = measure(text, source=source)

# Layer 4: number provenance
result["source_matching"]["unsourced_rate"]   # 0.0 - every number in source

# Layer 11: per-sentence Grounded / Framed / Projected decomposition
result["grounding_decomposition"]["proportions"]   # {"G": 1.0, "F": 0.0, "P": 0.0}
result["grounding_decomposition"]["has_projection"]  # False
```

The composite quality profile (Layer 10) requires ≥10 numbers in text for the source-fidelity contribution to qualify. For the substance vs presentation gap signal, supply a longer document:

```python
text = (
    "Revenue grew 12% to $143M with 25% margins reported. "
    "Costs declined 8% across 5,000 employees over 18 months. "
    "Headcount reached 2,500 with $45,000 average compensation paid. "
    "Customer acquisition cost dropped to $1,200 from baseline. "
    "Retention improved 7.5% to 94.2% across all major segments."
)

result = measure(text, source=text)
result["quality_profile"]["substance_index"]   # 1.0 (self-source, all numbers grounded)
result["quality_profile"]["gap"]               # negative - substance exceeds presentation
result["quality_profile"]["components_available"]  # ["source_fidelity", "assertiveness", ...]
```

Layer 11's `scope_assessment` field tells you which signal to trust on a given source. The derivation checker saturates as the source's unique-number count grows; on number-dense sources (≥10 unique numbers), the primary unsourced-numbers P-signal effectively saturates and you should cross-reference Layer 4 source matching for numerical fabrication. The classifier is also exposed standalone:

```python
from clarethium_touchstone import assess_derivation_regime

assessment = assess_derivation_regime(source_num_count=14)
assessment["derivation_regime"]                      # "saturated"
assessment["cross_reference_layer_4_for_numbers"]    # True
assessment["note_user_facing"]                       # UX-safe explanation
```

Boundaries are empirically validated against EXP-095 Monte Carlo data: < 5 = diagnostic, [5, 10) = transition, ≥ 10 = saturated.

For Layer 1a (heading defaultness), supply your own LLM client as a callable (vendor-neutral):

```python
def baseline_generator(prompt: str) -> str | None:
    # Your LLM call here. Return generated text or None on failure.
    return your_llm_client.generate(prompt, temperature=1.0)

result = measure(
    text,
    source=source,
    topic="quarterly earnings analysis",
    baseline_generator=baseline_generator,
)
result["structural_profile"]["heading_defaultness"]
# {"jaccard_overlap": 0.33, "is_default": False, "n_baseline_documents": 3}
```

## Library layers

The reference implementation covers every layer in Standard Section 5:

| Layer | Function | Requires |
|------|----------|----------|
| 1a heading defaultness | `structural_profile` | `topic` + `baseline_generator` |
| 1b mechanism ratio | `structural_profile` | text |
| 1c assertion ratio | `structural_profile` | text |
| 2 claim density | `claim_density` | text |
| 3 temporal instability | `temporal_instability` | text + `comparisons` |
| 4 source matching | `source_matching` | text + `source` |
| 5 entity provenance | `entity_provenance` | text + `source` |
| 6 vocabulary proximity | `vocabulary_proximity` | text + `source` |
| 7 presentation features | `presentation_features` | text |
| 8 epistemic calibration | `epistemic_calibration` | text + `source` |
| 9 information novelty | `information_novelty` | text |
| 10 quality profile composite | `quality_profile` | text (substance from L3/L4/L5/L8) |
| 11 grounding decomposition | `grounding_decomposition` | text + `source` |

The top-level `measure()` orchestrator runs every layer whose preconditions are met. Layers without preconditions return `None` for that key in the `MeasureResult` dict.

Standard Section 6 (Specification Compliance) is **not** part of v0.1. The `align()` and `profile()` APIs are reserved for Standard 1.1. Touchstone v0.1 ships measurement only.

## Empirical validation

Two internal regression benchmarks ship in `benchmarks/`. Anyone with a repo clone can run `python -m benchmarks.exp_081_discrimination.run` and `python -m benchmarks.exp_095_grounding.run` and reproduce the recorded numbers exactly. The benchmarks are internal regression baselines, not external replications; the corpora and expected values are authored by this project. Construct generalization to externally curated corpora is open work (see Limitations).

### EXP-081 adversarial discrimination

EXP-081 is the project's internal adversarial-discrimination corpus: 12 documents (N=6 faithful, N=6 embellished) generated by xAI grok-4-1-fast on three source topics under two contrasting system instructions. The faithful instruction grounds every claim in the source; the embellished instruction adds external citations, statistics, and forward references. The composed `quality_profile.gap` signal should discriminate the two conditions.

Expected per-document metrics are recorded in `benchmarks/exp_081_discrimination/ground_truth.json`. An earlier internal detector (`detector_v031`) produced Cohen's d = -5.43 (CI [-9.077, -4.681]) on this corpus. Touchstone v0.1 reproduces the effect on the same corpus, reported with the standard small-N corrections:

| Metric | Faithful (N=6) | Embellished (N=6) |
|---|---|---|
| Mean gap (Touchstone) | -0.4377 | +0.1585 |
| Mean gap (detector_v031) | -0.443 | +0.169 |
| Cohen's d | **-5.238** vs detector_v031 **-5.43** | |
| **Hedges' g** (small-N corrected) | **-4.835** | |
| **95% bootstrap CI on Cohen's d** | **[-8.926, -4.498]** (2000 resamples, fixed seed) | |
| Per-doc gap-direction agreement with detector_v031 | 100% (12/12) | |
| MAE on unsourced_rate / gap / substance / presentation | 0.014 / 0.010 / 0.010 / 0.000 | |

This is an internal regression baseline against recorded expected values, not third-party replication. Embellishment instructions overlap textually with what Layers 4/5/11 detect (external citations, unsourced statistics, forward references), so the d statistic measures the system catching what the instructions told the generator to add, with the magnitude of the effect bounded by that construct overlap. The wide bootstrap CI (~4.4 units) reflects the small sample (N=6/6); the effect's sign is stable but its magnitude is uncertain at this N.

### EXP-095 grounding decomposition

Layer 11 (`grounding_decomposition`) classifies each sentence as Grounded / Framed / Projected. Internal validation against 13 hand-classified outputs across 3 source documents and 3 model families (gpt-4o, gemini-3-flash-preview, grok-4-1-fast):

- **P-direction agreement: 100% on existence (P>0 vs P=0)** - Touchstone never disagrees with manual classification on whether projected content exists in an output. Per-output P magnitude differs from manual range on 4/13 outputs.
- **MAE vs an earlier internal detector (`detector_v031`): 0.02-0.04** across G/F/P categories in aggregate (regression baseline; the reference is a prior version of this detector, not an independent ground truth).
- **MAE vs full manual classification (n=7 with complete annotations): 0.12-0.13** across G/F/P. The detector consistently over-counts G relative to manual, because mixed sentences (source number plus interpretation) are classified as G structurally but as F by human readers when the primary function is interpretive. See `benchmarks/exp_095_grounding/README.md` for the per-output breakdown.

### Snapshot drift detection

Both benchmarks pin a dated JSON snapshot via byte-match pytest assertion. CI catches silent regression on any future change affecting per-doc predictions.

## Limitations

What this release does **not** demonstrate:

- **No external corpus.** Both benchmarks are internal: corpus authored by this project, expected values recorded in this repo, no independent annotation. Validation against TRUE (Honovich et al. 2022), LLM-AggreFact / MiniCheck (Tang et al. 2024), HaluBench / Lynx (Patronus 2024), or HaluEval (Li et al. 2023) is open work.
- **No head-to-head baselines.** Touchstone has not been benchmarked head-to-head against AlignScore (Zha et al. 2023), MiniCheck, HHEM 2.1 (Vectara), SelfCheckGPT (Manakul et al. 2023), or G-Eval (Liu et al. 2023) on a common input set.
- **EXP-081 corpus is single-vendor.** All 12 documents are xAI grok-4-1-fast. Cross-vendor generalization within the fast tier and to flagship-tier model outputs is open research.
- **Small-N statistics.** N=6/6 yields a wide bootstrap CI on Cohen's d ([-8.926, -4.498] at 95%). The sign of the effect is stable across resamples; the magnitude is uncertain at this corpus size. Hedges' g (-4.835) is reported alongside.
- **Layer 11 entity list is domain-biased.** The hardcoded external-entity P-markers (`_GFP_EXTERNAL_ENTITIES` in `measure.py`) cover GLP-1 drugs, Apple products, and BLS labor terms (the three EXP-095 source domains). On new domains, the secondary P-signal goes silent; adopters extending to new domains must author new entity lists with their own false-positive control.
- **No constituted editor body.** Standard §11 references an editor body for formal certification; that body is not yet constituted. Conformance today is self-certification by passing the test suite in this repo.

## Use cases

What this release has actually been exercised on:

- Regression testing of AI-output verification implementations (the use case the bundled benchmarks demonstrate).
- Research-style profiling of analytical documents against their sources (the use case the layer functions enable).

What this release is plausibly suited for, with the caveat that it has not yet been deployed against an externally curated corpus:

- AI integrity research and benchmarking, including head-to-head comparison against published faithfulness metrics.
- Educational use in AI methodology courses where the regex-and-arithmetic substrate is the pedagogical point.

What this release does NOT yet support production claims for:

- Internal AI-quality verification at organizations operating at scale (no batch API, no performance characterization; see §Limitations).
- Substrate enforcement on AI-coupled work platforms (no adversarial-robustness claim; the patterns are public and evadable).
- Independent third-party verification of AI vendor claims (no external-corpus validation; no head-to-head baselines).

The §Limitations section names what each of these aspirational use cases requires before it becomes a real production claim.

## Why model-independent

LLM-as-judge approaches use AI to evaluate AI output. Touchstone uses regex, structural analysis, source matching, and arithmetic. The substrate does not depend on the model being measured. This matters when the auditor cannot be made of the same material as the audited.

## Licensing

- **Standard:** CC-BY 4.0 (content)
- **Library:** Apache 2.0

## Companions

Touchstone composes with the other Clarethium open reference artifacts:

- **[Lodestone](https://github.com/Clarethium/lodestone)**: methodology canon. The first-person practice that pairs with Touchstone's third-person measurement.
- **[cma](https://github.com/Clarethium/cma)**: executable compound-practice loop. Companion to Lodestone, surfacing relevant prior captures at the moment of action.
- **[Sealstone](https://github.com/Clarethium/sealstone)**: verification methodology for AI-assisted publish-class work. A specialization in the Lodestone tradition for the publish boundary; integrates Touchstone-class measurement at Tier 0 of its three-tier verification ladder.

Touchstone is also the substrate underneath [Frame Check](https://frame.clarethium.com), Clarethium's applied frame-validation tool.

## Related

- [Clarethium](https://blog.clarethium.com): methodology umbrella, mothership.
- Documentation: https://touchstone.clarethium.com

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution process. Standard changes follow the [Suggestion workflow](SUGGESTIONS/PROCESS.md) modeled on PEP-1 and BIP-1.

## Citation

The Standard is currently in draft (1.0.0-draft.4). When citing it, please
indicate the draft state and the version:

```bibtex
@misc{touchstone_standard_2026,
  author       = {{Clarethium}},
  title        = {Touchstone Standard 1.0 (draft)},
  year         = {2026},
  howpublished = {\url{https://github.com/Clarethium/touchstone/blob/main/STANDARDS/touchstone-1.0.md}},
  note         = {Version 1.0.0-draft.4},
  license      = {CC-BY-4.0}
}
```

When citing the reference implementation:

```bibtex
@software{lucic_touchstone_2026,
  author  = {Lucic, Lovro},
  title   = {Touchstone: reference implementation},
  year    = {2026},
  version = {0.1.0},
  url     = {https://github.com/Clarethium/touchstone},
  license = {Apache-2.0}
}
```

`CITATION.cff` carries the structured metadata equivalent.
