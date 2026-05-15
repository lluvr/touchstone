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

Two internal regression benchmarks plus three external corpus comparisons ship in `benchmarks/`. The internal benchmarks (`exp_081_discrimination/`, `exp_095_grounding/`) reproduce the recorded numbers exactly from a clone; the external benchmarks (`external/ragtruth_summary/`, `external/summeval/`, `external/halueval_summarization/`) stream third-party permissively-licensed corpora from HuggingFace at runtime and compare Touchstone head-to-head against MiniCheck (Tang et al. 2024). The internal benchmarks are regression baselines on project-authored corpora; the external benchmarks are construct-generalization tests, with results recorded under each benchmark's `results/` subdirectory.

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

### RAGTruth Summary external comparison

First external corpus comparison. n=900 Summary outputs from the test split of `wandb/RAGTruth-processed` (MIT license; mirror of RAGTruth, Wu et al. 2024) spanning six model families (gpt-3.5-turbo-0613, gpt-4-0613, llama-2-{7B,13B,70B}-chat, mistral-7B-instruct). Per-output binary ground truth: at least one annotated hallucination span vs none.

| System | AUC-ROC | n used | Runtime (CPU, n=900) |
|---|---|---|---|
| MiniCheck Flan-T5-Large (Tang et al. 2024) | **0.7125** | 900 | ~98 min |
| Touchstone Layer 6 inverse_proximity | **0.6723** | 900 | 2.3 s |
| Touchstone Layer 5 entity_unsourced_rate | 0.8167 | 23 | (signal gated; only 23 outputs have ≥5 entities) |
| Touchstone Layer 4 unsourced_rate | 0.5514 | 628 | (signal gated; 272 outputs have no digit-formatted numbers) |
| Touchstone Layer 11 P proportion | 0.5374 | 900 | |
| Touchstone Layer 10 gap (composite) | **0.4981** | 900 | (chance) |

The Layer 10 composite falls to chance because the substance-side components do not fire on these short summaries: `source_fidelity` activates on 0.7% of outputs, `entity_grounding` on 2.6%, `epistemic_calibration` on 0.1%. The composite reduces to presentation-only and carries no fidelity information on this corpus.

Layer 6 inverse vocabulary proximity is the strongest surviving Touchstone signal out-of-domain, ~0.04 AUC below MiniCheck at ~2500x less compute. This is consistent with the Standard's §3.5 partial-falsification finding for Layer 10 (the construct holds within the calibrated long-form regime but not on short summaries) and the substrate-independence claim for §3.1 (per-model AUC ranges 0.59-0.73, within noise from per-model hallucination-rate imbalance). See `benchmarks/external/ragtruth_summary/README.md` for methodology, construct caveats, and per-model breakdown.

### SummEval external comparison

Second external corpus. n=1600 (article, summary) pairs from the test split of `mteb/summeval` (MIT license; CNN/DM articles with per-summary 1-5 Likert consistency ratings; Fabbri et al. TACL 2021). 100 articles, 16 machine summaries per article, 16 older summarization-system architectures. Binarization: `consistency < 4` = "not supported" (10.1% positive class). Spearman correlation against the continuous rating reported alongside, because the 1-5 scale is heavily skewed toward "supported" (median 5.0) and binarization throws away rank information that Spearman preserves.

| System | AUC-ROC | Spearman ρ vs continuous rating | n used | Runtime (CPU, n=1600) |
|---|---|---|---|---|
| MiniCheck Flan-T5-Large* | 0.8978 | +0.4066 | 1600 | ~69 min |
| Touchstone Layer 6 inverse_proximity | **0.7530** | **-0.3481** | 1600 | 2.1 s |
| Touchstone Layer 4 unsourced_rate | 0.5688 | -0.2566 | 967 | |
| Touchstone Layer 11 P proportion | 0.5207 | -0.1227 | 1600 | |
| Touchstone Layer 10 gap (composite) | **0.5000** | **0.0000** | 1600 | (chance) |
| Touchstone Layer 5 entity (gated) | — | — | 0 | (no summary has ≥5 entities) |

*Training-test leakage caveat applies: MiniCheck was trained on LLM-AggreFact, which includes AggreFact-CNN derived from SummEval. MiniCheck's source distribution is in its training set; its absolute AUC on this corpus is not held-out. Touchstone has not been calibrated on any SummEval-derived data.

Layer 6 lands in the "substantive generalization" band (≥0.75) on SummEval, ~0.14 below MiniCheck (with the leakage caveat). **Layer 10 gap is identically AUC = 0.5000 and Spearman ρ = 0.0000** — second-corpus confirmation of the §3.5 partial out-of-domain falsification. 0/1600 outputs have any substance components firing on this corpus, vs 3% on RAGTruth: SummEval's even shorter summaries (median 338 chars vs RAGTruth's 626) leave the substance side completely dark. See `benchmarks/external/summeval/README.md` for methodology and construct caveats.

### HaluEval summarization external comparison

Third external corpus. n=1000 (article, summary) pairs from 500 randomly sampled documents in the HaluEval summarization subset (Li et al., EMNLP 2023; `pminervini/HaluEval` mirror, Apache-2.0). Each document contributes one `right_summary` (real CNN/DM summary) and one `hallucinated_summary` (ChatGPT-synthesized variant with intentionally introduced errors). Perfect 50/50 class balance by construction; primary readout is **paired-ranking accuracy** (does the signal rank the hallucinated summary higher than the right one on the same document?), which is robust to any synthetic-vs-real distributional confound that absolute AUC would inherit.

| System | AUC-ROC | Paired-ranking accuracy | n used | Runtime (CPU, n=1000) |
|---|---|---|---|---|
| **Touchstone Layer 6 inverse_proximity** | **0.7593** | **0.8030 (401/500 pairs)** | 1000 | 1.9 s |
| MiniCheck Flan-T5-Large | 0.6752 | 0.6980 (349/500 pairs) | 1000 | ~100 min |
| Touchstone Layer 4 unsourced_rate | 0.4993 | 0.5189 (159 pairs usable) | 474 | |
| Touchstone Layer 10 gap (composite) | 0.5020 | 0.5020 (490/500 ties) | 1000 | |
| Touchstone Layer 11 P proportion | 0.4941 | 0.4960 (474/500 ties) | 1000 | |
| Touchstone Layer 5 entity (gated) | 0.4286 | 0.5000 | 12 | |

The HaluEval finding requires careful framing: **Touchstone L6 outperforms MiniCheck on this corpus, but for a corpus-construction reason, not a methodology-superiority reason.** HaluEval is adversarially constructed (ChatGPT-synthesized hallucinations on CNN/DM articles); the hallucinated summaries are by design lexically distributed away from the source article. Layer 6 measures exactly this kind of vocabulary distance, so it is well-aligned with what the adversarial process produces. MiniCheck, a fine-tuned semantic fact-checker, drops to AUC 0.68 because HaluEval's adversarial hallucinations are easier to detect via vocabulary distance than via semantic NLI. The substantive finding remains the **three-corpus consistency** of the Touchstone signals, not the headline ordering on any single corpus. See `benchmarks/external/halueval_summarization/README.md` for the adversarial-construction caveat in full.

### Cross-corpus comparison

The three external corpora consistently show:

| Signal | RAGTruth Summary AUC | SummEval AUC | HaluEval AUC |
|---|---|---|---|
| Touchstone Layer 6 inverse_proximity | 0.6723 | 0.7530 | **0.7593** |
| Touchstone Layer 10 gap (composite) | 0.4981 | 0.5000 | 0.5020 |
| MiniCheck Flan-T5-Large | 0.7125 | 0.8978* | 0.6752 |

The Layer 6 generalization signal (0.67-0.76) and the Layer 10 composite degeneration (0.498-0.502) are both **stable across three independent corpora** spanning RAG-context summaries, CNN/DM news summaries, and adversarial CNN/DM summaries. MiniCheck's AUC varies by 0.22 across the three corpora; Touchstone L6's varies by 0.09. The Standard's §3.5 partial out-of-domain falsification of Layer 10 gap is now load-bearing on three independent corpora.

* SummEval MiniCheck figure inflated by training-test leakage (MiniCheck was trained on AggreFact-CNN, which is SummEval-derived).

### Snapshot drift detection

Both internal benchmarks pin a dated JSON snapshot via byte-match pytest assertion. CI catches silent regression on any future change affecting per-doc predictions. The external benchmark snapshot is dated and committed but not CI-gated (CI does not have HuggingFace auth or MiniCheck model weights).

## Limitations

What this release does **not** demonstrate:

- **Three external corpus runs; more open.** External validations land in `benchmarks/external/ragtruth_summary/` (RAGTruth Summary test split, n=900, MIT, six instruction-tuned LLM families), `benchmarks/external/summeval/` (SummEval test, n=1600 (article, summary) pairs, MIT, 16 older summarization systems), and `benchmarks/external/halueval_summarization/` (HaluEval summarization, n=1000 (article, summary) pairs from 500 documents with ChatGPT-synthesized adversarial hallucinations, Apache-2.0). Touchstone's strongest signal on all three corpora is Layer 6 inverse vocabulary proximity, at AUC 0.6723 / 0.7530 / 0.7593. MiniCheck Flan-T5-Large baseline AUC is 0.7125 / 0.8978 / 0.6752; MiniCheck on SummEval is inflated by training-test leakage, and MiniCheck on HaluEval underperforms Touchstone L6 because HaluEval's adversarial construction produces vocabulary distribution shifts that L6 measures directly. Layer 10 gap is falsified out-of-domain on all three corpora (AUC 0.498 / 0.500 / 0.502) per Standard §3.5. Validation against TRUE (Honovich et al. 2022), LLM-AggreFact (Tang et al. 2024), and HaluBench / Lynx (Patronus 2024) remains open work.
- **One head-to-head baseline; more open.** MiniCheck Flan-T5-Large (Tang et al. 2024) is the only baseline run so far. Touchstone has not yet been benchmarked against AlignScore (Zha et al. 2023), HHEM 2.1 (Vectara), SelfCheckGPT (Manakul et al. 2023), G-Eval (Liu et al. 2023), or Bespoke-MiniCheck-7B (the SOTA MiniCheck variant). Two candidate baselines investigated for this round (HHEM 2.1 and AlignScore) had install incompatibilities with modern Python that prevented inclusion; resolving these is open work.
- **Layer 10 gap is input-regime-conditional.** The composite holds on long-form analytical Markdown with adequate claim density (EXP-081 internal corpus, d = -5.238). It does not hold on short summary outputs across any of the three external corpora tested (RAGTruth Summary AUC 0.4981 with 3% substance fire; SummEval AUC 0.5000 with 0% substance fire; HaluEval AUC 0.5020 with 490/500 paired document scores tied at zero). Adopters running on short-form text should pair Touchstone with a different fidelity signal; on Touchstone alone, Layer 6 inverse_proximity is the surviving out-of-domain option (AUC 0.67-0.76 across the three corpora).
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

The Standard is currently in draft (1.0.0-draft.8). When citing it, please
indicate the draft state and the version:

```bibtex
@misc{touchstone_standard_2026,
  author       = {{Clarethium}},
  title        = {Touchstone Standard 1.0 (draft)},
  year         = {2026},
  howpublished = {\url{https://github.com/Clarethium/touchstone/blob/main/STANDARDS/touchstone-1.0.md}},
  note         = {Version 1.0.0-draft.8},
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
