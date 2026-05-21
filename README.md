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
- **Reference test suite** at `tests/reference/cases/` - language-agnostic JSON cases that second-party implementations MUST pass to claim conformance
- **Internal regression benchmarks** at `benchmarks/exp_081_discrimination/` and `benchmarks/exp_095_grounding/`
- **External corpus comparisons** at `benchmarks/external/` against RAGTruth, SummEval, HaluEval with MiniCheck and AlignScore baselines
- **Methodology summary** at `docs/methodology.md` (substrate hypothesis, falsification protocol, cross-corpus evidence, caveats) — intended for readers evaluating Touchstone for adoption or methodological critique

The Standard defines the methodology. The library implements it. Other implementations conforming to the Standard are welcome.

## Status

Pre-launch on PyPI. All eleven Section 5 measurement layers are implemented and tested (441 tests; CI green on ruff lint + format, mypy strict, and the pytest matrix across Python 3.10/3.11/3.12). Test coverage is at 97% with a 95% CI gate. Two internal regression benchmarks plus three external corpus comparisons (RAGTruth Summary, SummEval, HaluEval summarization) ship with the source. The internal benchmarks reproduce exactly from a clone; the external runners stream the corpora from HuggingFace at runtime. The cross-corpus Touchstone signal pattern is internally consistent across three corpora and three task types with 95% bootstrap CIs; see §Empirical validation. Validation against TRUE, LLM-AggreFact held-out, and HaluBench remains open work; see Limitations.

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

## Read before deploying: `docs/production_readiness.md`

Touchstone alone is NOT a standalone production hallucination detector. A 16-case stress test on subtle hallucinations (direction reversal, attribute swap, scoping shift, relation reversal, time-frame shift, imputed cause — the categories real LLMs actually produce) found Touchstone separates the hallucinated from the faithful case at **50% (random)** and flags zero of 16 at the default threshold. The substrate is structurally blind to hallucinations that preserve vocabulary and only change semantic relationships.

What Touchstone IS useful for in production:

- **Triage / review-queue prioritization**: 2-4× lift over random review on English news summarization corpora (lift of 4.22× on SummEval top-10% review).
- **Cheap first-pass filter** in a two-stage pipeline ahead of an LLM-based judge.
- **Drift detection** on stable production streams.
- **Lexical-feature half of a production hallucination detector** — combine with a trained semantic discriminator via `Verifier(mode="substrate_plus_minicheck").score(text, source, minicheck_supported_prob=mc_prob)`, or with a frontier LLM judge via `Verifier().score(text, source, judge_hallucinated_prob=judge_prob)` (mode auto-selects to `substrate_plus_judge`; linear blend with `judge_alpha` defaulting to 0.3 per §4.3.1).

Full operational analysis with precision/recall/F1/lift numbers, the 16-case stress test results, and the production architecture recommendation: see `docs/production_readiness.md` and `docs/methodology.md`. Read both before shipping anything that depends on Touchstone's output.

## Quick example: the calibrated `Verifier` API

The `Verifier` is the production-shaped API: one `score()` call, calibrated probability + explainable signal breakdown + span-level localization. Use it as the lexical half of a two-stage architecture, not as a standalone detector.

```python
from clarethium_touchstone import Verifier

v = Verifier()  # substrate-only mode; no extra deps, sub-100 ms per pair
result = v.score(
    text="Apple reported Q1 revenue of $185 billion. McKinsey forecasts 47% growth.",
    source="Apple reported Q1 revenue of $143 billion.",
)
print(f"prob_hallucinated = {result.prob_hallucinated:.3f}")  # → 0.796
print(f"should flag (>0.5)? {result.should_flag()}")          # → True
for span in result.top_unsupported:
    print(f"  {span.layer11_primary}: {span.sentence!r}  {span.p_markers}")
# → P: 'Apple reported Q1 revenue of $185 billion.'  ['unsourced_numbers']
# → P: 'McKinsey forecasts 47% growth.'              ['unsourced_numbers']
```

Three operating modes (auto-selected from which baseline scores you pass):

- **Substrate-only** (default; no extras, sub-100 ms): default-calibrated AUC ≈ 0.67-0.76 on three external summarization corpora. Research-tier signal. For drift detection, regression testing, or as a cheap first-pass filter ahead of an LLM-based judge.
- **Substrate + MiniCheck** (caller invokes MiniCheck and passes `minicheck_supported_prob`): AUC ≈ 0.76. Adds the MiniCheck cost (~5 s/pair on CPU).
- **Substrate + MiniCheck + AlignScore** (pass both): AUC ≈ 0.77. Adds the AlignScore cost.

Honest accuracy/latency envelope and recalibration guidance: see `docs/methodology.md` and `examples/production_verifier.py` for the end-to-end demo.

### Low-level: raw `measure()` for layer-level analysis

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

Two internal regression benchmarks plus three external corpus comparisons plus one cross-task generalization analysis ship in `benchmarks/`. The internal benchmarks (`exp_081_discrimination/`, `exp_095_grounding/`) reproduce the recorded numbers exactly from a clone. The external benchmarks (`external/ragtruth_summary/`, `external/summeval/`, `external/halueval_summarization/`) stream third-party permissively-licensed corpora from HuggingFace at runtime and compare Touchstone head-to-head against MiniCheck (Tang et al. 2024). The task-type generalization analysis (`external/ragtruth_task_type_generalization.py`) extends Touchstone to RAGTruth's QA and Data2Txt subsets, testing whether the cross-corpus pattern also holds across task types.

### Headline finding (cross-corpus, cross-task, anchored to trivial baselines)

Across three independent external corpora (RAGTruth Summary, SummEval, HaluEval summarization) and three task types within RAGTruth (Summary, QA, Data2Txt), Touchstone's measurement layers are compared against two LLM-based discriminators (MiniCheck Flan-T5-Large, AlignScore-base) AND against three **trivial lexical baselines** (raw word overlap, Jaccard of content words, TF-IDF cosine). The trivial-baseline anchor is the most important methodological discipline in this report: it tells the reader exactly how much of the discriminative signal is captured by a 5-line bag-of-words computation that any reader can reproduce from the snapshot JSONs in seconds. All AUCs are reported with 95% percentile bootstrap CIs (1000 stratified resamples, fixed seed).

**Cross-corpus on summarization-task outputs:**

| Signal | RAGTruth Summary | SummEval | HaluEval summarization | Mean | SD |
|---|---|---|---|---|---|
| MiniCheck Flan-T5-Large (Tang et al. EMNLP 2024) | 0.7125 [0.6683, 0.7573] | 0.8978 [0.8661, 0.9275]* | 0.6752 [0.6436, 0.7069] | 0.762 | 0.098 |
| AlignScore-base (Zha et al. ACL 2023) | 0.7368 [0.7006, 0.7699] | 0.8091 [0.7714, 0.8455] | 0.6879 [0.6567, 0.7187] | 0.745 | 0.050 |
| Touchstone Layer 6 inverse_proximity | 0.6723 [0.6296, 0.7116] | 0.7530 [0.7145, 0.7951] | 0.7593 [0.7285, 0.7879] | 0.728 | 0.039 |
| **Trivial: WordOverlapInv (3 lines)** | **0.6827 [0.6410, 0.7238]** | **0.7284 [0.6810, 0.7774]** | **0.7431 [0.7136, 0.7712]** | **0.718** | **0.026** |
| Trivial: JaccardContentInv | 0.6677 [0.6234, 0.7081] | 0.7089 [0.6622, 0.7547] | 0.4715 [0.4363, 0.5073] | 0.616 | 0.106 |
| Trivial: TFIDFCosineInv | 0.6163 [0.5739, 0.6639] | 0.6987 [0.6553, 0.7421] | 0.5385 [0.5032, 0.5740] | 0.618 | 0.065 |
| Touchstone Layer 10 gap (composite) | 0.4981 [0.4830, 0.5111] | 0.5000 [0.5000, 0.5000] | 0.5020 [0.4950, 0.5090] | 0.500 | 0.002 |

**Cross-task within RAGTruth (every AUC with 95% bootstrap CI):**

| Signal | Summary (n=900) | QA (n=900) | Data2Txt (n=900) |
|---|---|---|---|
| MiniCheck Flan-T5-Large | 0.7125 [0.6683, 0.7573] | 0.6437 [0.5978, 0.6920] | **0.4871 [0.4494, 0.5283]** (chance) |
| Touchstone Layer 4 unsourced_rate (when gated in) | 0.5514 [0.5054, 0.5977] | **0.7603 [0.6907, 0.8260]** | 0.5177 [0.4810, 0.5488] |
| Touchstone Layer 6 inverse_proximity | 0.6723 [0.6296, 0.7116] | 0.6984 [0.6579, 0.7361] | 0.6397 [0.6001, 0.6757] |
| Touchstone Layer 10 gap (composite) | 0.4981 [0.4830, 0.5111] | 0.5127 [0.4985, 0.5295] | 0.5041 [0.4908, 0.5170] |
| Touchstone Layer 11 P proportion | 0.5374 [0.5094, 0.5676] | 0.5591 [0.5283, 0.5895] | 0.5026 [0.5000, 0.5060] |

*Training-test leakage on SummEval (MiniCheck was trained on AggreFact-CNN, which is SummEval-derived); see the benchmark README for the full caveat.

**What this table actually shows (load-bearing honesty):**

1. **A 3-line raw word-overlap baseline is statistically indistinguishable from Touchstone Layer 6 on every corpus tested.** WordOverlapInv vs Touchstone L6: CIs overlap heavily on RAGTruth Summary, on SummEval, and on HaluEval. The "Layer 6 substrate-independence" finding from prior drafts reduces empirically to: **simple lexical features (with or without Touchstone's per-sentence segmentation) carry the same out-of-domain hallucination signal in this signal-strength tier.**
2. **WordOverlapInv has the lowest cross-corpus SD (0.026) of any signal in the table.** Touchstone Layer 6 SD is 0.039, AlignScore 0.050, MiniCheck 0.098. The "most substrate-independent" baseline in this report is plain word overlap, not Touchstone's structured Layer 6.
3. **JaccardContentInv collapses on HaluEval** (AUC 0.4715, CI [0.4363, 0.5073] — below chance!). Stripping stopwords removes the very signal HaluEval's adversarial construction introduces. This is the cleanest evidence in the report that lexical-baseline behaviour is highly preprocessing-dependent; the "right" preprocessing is corpus-dependent.
4. **Layer 10 gap CIs all overlap chance** (the only signal in the table whose CIs include 0.5000 on every corpus). The §3.5 partial out-of-domain falsification is real and statistically defensible.

**What this means for Touchstone's positioning:**

This report does NOT show that Touchstone has a methodologically superior signal over trivial lexical baselines. It shows that **simple lexical features capture roughly 70% of the discriminative signal on hallucination detection at this signal-strength tier, with the rest captured by LLM-based discriminators at orders-of-magnitude higher compute cost**. Touchstone's value is not Layer 6's AUC; it is the **calibrated falsification protocol** (Standard §3.5 with five corpus×task cells × two baselines × three trivial baselines), the **bootstrap-CI discipline** on every reported AUC, the **falsification-of-Layer 10 finding** as a concrete instance of the protocol working as designed, and the **packaged library + Standard + reference suite** that makes the regime studyable and the methodology portable.

**Cross-(corpus, task) cells, expanded with task-type evidence:**

- Layer 6 AUC across all five (corpus, task) cells lives in [0.64, 0.76].
- Layer 10 gap AUC across all five cells lives in [0.498, 0.513] with CIs that overlap 0.50 in every cell.
- Layer 4 unsourced_rate spikes to AUC 0.7603 [0.6907, 0.8260] on RAGTruth QA — the first task type where output number density is high enough for Layer 4 to fire on a usable fraction (n=277/900). On summary task outputs the signal is gated out for most examples.
- MiniCheck Flan-T5-Large is at chance on RAGTruth Data2Txt (AUC 0.4871 [0.4494, 0.5283]; CI squarely includes 0.5000). The fine-tuned discriminator does not generalize across task types.

**Honest scope statement.** All three external corpora are English-news-summarization derivatives. Both LLM-based baselines tested are budget-tier (MiniCheck Flan-T5-Large at 770M, AlignScore-base at 125M); SOTA methods (Bespoke-MiniCheck-7B, GPT-4-as-judge) are not tested and would score higher AUC. **Touchstone is positioned as a research substrate for studying hallucination-detection methodology at low compute cost, NOT as a production-grade hallucination detector.** Auditors, compliance regimes, and platforms requiring high-recall production behaviour should use Touchstone alongside (not instead of) LLM-based methods.

### Compute disclosure

All external benchmark runs in this repository were executed on a single CPU (no GPU). Per-corpus runtimes recorded in the snapshot JSONs:

| Corpus | n_pairs | Touchstone (CPU) | MiniCheck Flan-T5-Large (CPU) |
|---|---|---|---|
| RAGTruth Summary | 900 | 2.3 s | 5867 s (~98 min) |
| SummEval | 1600 | 2.1 s | 4124 s (~69 min) |
| HaluEval summarization | 1000 | 1.9 s | 5971 s (~100 min) |

The Touchstone-to-MiniCheck wall-clock ratio is approximately 1:2500. `measure()` scales linearly in document size: 5 kB / 50 kB / 500 kB documents measure in 16 ms / 161 ms / 1.78 s respectively, after a finalization-round perf fix that replaced an O(n²) per-sentence content-words recomputation in `grounding_decomposition` with a single hoisted set, and replaced an O(n²) `claimed_ranges` linear scan in `_extract_numbers_for_matching` with a bisect-based overlap check on parallel sorted lists.

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

| System | AUC-ROC (95% CI where computed) | n used | Runtime (CPU, n=900) |
|---|---|---|---|
| AlignScore-base (Zha et al. ACL 2023) | **0.7368 [0.7006, 0.7699]** | 900 | 7830 s (~131 min) |
| MiniCheck Flan-T5-Large (Tang et al. EMNLP 2024) | **0.7125** | 900 | ~98 min |
| Touchstone Layer 6 inverse_proximity | **0.6723 [0.6296, 0.7116]** | 900 | 2.3 s |
| Touchstone Layer 5 entity_unsourced_rate | 0.8167 [0.5000, 1.0000] | 23 | (signal gated; only 23 outputs have ≥5 entities) |
| Touchstone Layer 4 unsourced_rate | 0.5514 [0.5054, 0.5977] | 628 | (signal gated; 272 outputs have no digit-formatted numbers) |
| Touchstone Layer 11 P proportion | 0.5374 [0.5094, 0.5676] | 900 | |
| Touchstone Layer 10 gap (composite) | **0.4981 [0.4830, 0.5111]** | 900 | (chance) |

The Layer 10 composite falls to chance because the substance-side components do not fire on these short summaries: `source_fidelity` activates on 0.7% of outputs, `entity_grounding` on 2.6%, `epistemic_calibration` on 0.1%. The composite reduces to presentation-only and carries no fidelity information on this corpus.

Layer 6 inverse vocabulary proximity is the strongest surviving Touchstone signal out-of-domain, ~0.04 AUC below MiniCheck at ~2500x less compute. This is consistent with the Standard's §3.5 partial-falsification finding for Layer 10 (the construct holds within the calibrated long-form regime but not on short summaries) and the substrate-independence claim for §3.1 (per-model AUC ranges 0.59-0.73, within noise from per-model hallucination-rate imbalance). See `benchmarks/external/ragtruth_summary/README.md` for methodology, construct caveats, and per-model breakdown.

### SummEval external comparison

Second external corpus. n=1600 (article, summary) pairs from the test split of `mteb/summeval` (MIT license; CNN/DM articles with per-summary 1-5 Likert consistency ratings; Fabbri et al. TACL 2021). 100 articles, 16 machine summaries per article, 16 older summarization-system architectures. Binarization: `consistency < 4` = "not supported" (10.1% positive class). Spearman correlation against the continuous rating reported alongside, because the 1-5 scale is heavily skewed toward "supported" (median 5.0) and binarization throws away rank information that Spearman preserves.

| System | AUC-ROC (95% CI where computed) | Spearman ρ vs continuous rating | n used | Runtime (CPU, n=1600) |
|---|---|---|---|---|
| MiniCheck Flan-T5-Large* | 0.8978 | +0.4066 | 1600 | ~69 min |
| AlignScore-base | **0.8091 [0.7714, 0.8455]** | (not reported here) | 1600 | 4128 s (~69 min) |
| Touchstone Layer 6 inverse_proximity | **0.7530 [0.7145, 0.7951]** | **-0.3481** | 1600 | 2.1 s |
| Touchstone Layer 4 unsourced_rate | 0.5688 [0.5341, 0.6060] | -0.2566 | 967 | |
| Touchstone Layer 11 P proportion | 0.5207 [0.5048, 0.5366] | -0.1227 | 1600 | |
| Touchstone Layer 10 gap (composite) | **0.5000 [0.5000, 0.5000]** | **0.0000** | 1600 | (chance) |
| Touchstone Layer 5 entity (gated) | — | — | 0 | (no summary has ≥5 entities) |

*Training-test leakage caveat applies: MiniCheck was trained on LLM-AggreFact, which includes AggreFact-CNN derived from SummEval. MiniCheck's source distribution is in its training set; its absolute AUC on this corpus is not held-out. Touchstone has not been calibrated on any SummEval-derived data.

Layer 6 lands in the "substantive generalization" band (≥0.75) on SummEval, ~0.14 below MiniCheck (with the leakage caveat). **Layer 10 gap is identically AUC = 0.5000 and Spearman ρ = 0.0000** — second-corpus confirmation of the §3.5 partial out-of-domain falsification. 0/1600 outputs have any substance components firing on this corpus, vs 3% on RAGTruth: SummEval's even shorter summaries (median 338 chars vs RAGTruth's 626) leave the substance side completely dark. See `benchmarks/external/summeval/README.md` for methodology and construct caveats.

### HaluEval summarization external comparison

Third external corpus. n=1000 (article, summary) pairs from 500 randomly sampled documents in the HaluEval summarization subset (Li et al., EMNLP 2023; `pminervini/HaluEval` mirror, Apache-2.0). Each document contributes one `right_summary` (real CNN/DM summary) and one `hallucinated_summary` (ChatGPT-synthesized variant with intentionally introduced errors). Perfect 50/50 class balance by construction; primary readout is **paired-ranking accuracy** (does the signal rank the hallucinated summary higher than the right one on the same document?), which is robust to any synthetic-vs-real distributional confound that absolute AUC would inherit.

| System | AUC-ROC (95% CI where computed) | Paired-ranking accuracy | n used | Runtime (CPU, n=1000) |
|---|---|---|---|---|
| **Touchstone Layer 6 inverse_proximity** | **0.7593 [0.7285, 0.7879]** | **0.8030 (401/500 pairs)** | 1000 | 1.9 s |
| AlignScore-base | **0.6879 [0.6567, 0.7187]** | (not reported here) | 1000 | 6238 s (~104 min) |
| MiniCheck Flan-T5-Large | 0.6752 | 0.6980 (349/500 pairs) | 1000 | ~100 min |
| Touchstone Layer 4 unsourced_rate | 0.4993 [0.4659, 0.5320] | 0.5189 (159 pairs usable) | 474 | |
| Touchstone Layer 10 gap (composite) | 0.5020 [0.4950, 0.5090] | 0.5020 (490/500 ties) | 1000 | |
| Touchstone Layer 11 P proportion | 0.4941 [0.4832, 0.5049] | 0.4960 (474/500 ties) | 1000 | |
| Touchstone Layer 5 entity (gated) | 0.4286 [0.2857, 0.5000] | 0.5000 | 12 | |

The HaluEval finding requires careful framing: **Touchstone L6 outperforms both LLM-based baselines on this corpus, but for a corpus-construction reason, not a methodology-superiority reason.** HaluEval is adversarially constructed (ChatGPT-synthesized hallucinations on CNN/DM articles); the hallucinated summaries are by design lexically distributed away from the source article. Layer 6 measures exactly this kind of vocabulary distance, so it is well-aligned with what the adversarial process produces. MiniCheck and AlignScore are both semantic NLI-style fact-checkers; both drop to AUC ~0.68 on HaluEval because adversarial lexical-distribution shifts are easier to detect via vocabulary distance than via semantic NLI. The two-baseline confirmation (independent training, independent architecture, near-identical AUC ~0.68) makes this a baseline-class limitation on adversarial vocabulary-shift corpora, not a MiniCheck-specific weakness. The substantive finding remains the **three-corpus, two-baseline consistency** of the Touchstone signal pattern, not the headline ordering on any single corpus. See `benchmarks/external/halueval_summarization/README.md` for the adversarial-construction caveat in full.

### Snapshot drift detection

Both internal benchmarks pin a dated JSON snapshot via byte-match pytest assertion. CI catches silent regression on any future change affecting per-doc predictions. The external benchmark snapshot is dated and committed but not CI-gated (CI does not have HuggingFace auth or MiniCheck model weights).

## Limitations

What this release does **not** demonstrate:

- **Three external corpora, two budget-tier LLM-based baselines, three trivial lexical baselines.** See the §Empirical validation "Headline finding" subsection for the full table. Layer 6 is statistically indistinguishable from a 3-line WordOverlapInv baseline on every corpus tested; the substrate-independence finding is shared by trivial lexical features. SOTA LLM-based discriminators (Bespoke-MiniCheck-7B, GPT-4-as-judge) are NOT tested — they would score higher AUC and are the right next-step baselines for a methodology paper. Open work on corpora: TRUE (Honovich et al. 2022), LLM-AggreFact held-out (Tang et al. 2024), HaluBench / Lynx (Patronus 2024). Open work on baselines: HHEM 2.1 (`trust_remote_code` API rename conflict with current transformers), SelfCheckGPT (Manakul et al. 2023), G-Eval (Liu et al. 2023), Bespoke-MiniCheck-7B (requires GPU), AlignScore on RAGTruth QA / Data2Txt task types.
- **All three external corpora are English-news-summarization derivatives.** RAGTruth Summary, SummEval, HaluEval summarization all anchor on CNN/DM or similar English news content. The substrate-independence finding is on this single domain. Generalization to non-English text, legal documents, medical documents, code, or any non-summarization output task is OUT OF VALIDATED SCOPE. The cross-task evidence within RAGTruth (Summary / QA / Data2Txt) is the only multi-task evidence in the report; further task and language coverage is open work.
- **Layer 10 gap is input-regime-conditional.** The composite holds on long-form analytical Markdown with adequate claim density (EXP-081 internal corpus, d = -5.238). It does NOT hold on short summary outputs across any of the three external corpora tested: 95% bootstrap CIs all include 0.5000. Adopters running on short-form text should pair Touchstone with a different fidelity signal; on Touchstone alone, Layer 6 inverse_proximity is the surviving out-of-domain option (AUC 0.64-0.76 across three corpora × three task types, all CIs disjoint from chance).
- **EXP-081 corpus is single-vendor.** All 12 documents are xAI grok-4-1-fast. Cross-vendor generalization within the fast tier and to flagship-tier model outputs is open research.
- **Small-N statistics.** N=6/6 yields a wide bootstrap CI on Cohen's d ([-8.926, -4.498] at 95%). The sign of the effect is stable across resamples; the magnitude is uncertain at this corpus size. Hedges' g (-4.835) is reported alongside.
- **Layer 11 entity list is domain-biased.** The hardcoded external-entity P-markers (`_GFP_EXTERNAL_ENTITIES` in `measure.py`) cover GLP-1 drugs, Apple products, and BLS labor terms (the three EXP-095 source domains). On new domains, the secondary P-signal goes silent; adopters extending to new domains must author new entity lists with their own false-positive control.
- **No constituted editor body.** Standard §11 references an editor body for formal certification; that body is not yet constituted. Conformance today is self-certification by passing the test suite in this repo.

## Use cases

Touchstone is positioned as **a research substrate for studying hallucination-detection methodology at low compute cost.** Read the §Empirical validation "Headline finding" subsection before choosing this library for any production purpose: simple lexical features capture roughly 70% of the discriminative signal at this signal-strength tier, and Touchstone's structured Layer 6 is statistically indistinguishable from a 3-line word-overlap baseline. The library's value is the calibrated falsification protocol, the bootstrap-CI discipline, the reference suite, and the integration of a multi-layer composite with explicit fire-rate gating — not Layer 6's AUC.

**Exercised on:**

- Regression testing of AI-output verification implementations (the use case the bundled benchmarks demonstrate, with byte-pinned snapshots).
- Research-style profiling of analytical documents against their sources with multi-layer structured signals.
- Methodology benchmarking under the §3.5 falsification protocol against three external corpora, two LLM-based discriminators, and three trivial lexical baselines.

**Plausibly suited:**

- AI methodology research and benchmarking, especially where reproducibility and statistical rigour matter (snapshots are byte-pinned; every AUC carries a bootstrap CI).
- Educational use in AI methodology courses where the regex-and-arithmetic substrate is the pedagogical point and the falsification protocol is the methodology lesson.
- Drift detection on AI-output pipelines as a fast (sub-100ms per 5kB document) regression signal alongside an LLM-based judge.

**Does NOT yet support production claims for:**

- Adversarial-robustness use cases (the regex/arithmetic substrate is public and an adversary aware of the patterns can evade them).
- Independent third-party audit / compliance verification at the AUC/recall levels those regimes require. The empirical AUCs in this release (0.65-0.76) are research-tier, not audit-tier.
- Generalization beyond English news summarization (all three external corpora are CNN/DM-derived in some layer of preprocessing; legal, medical, code, non-English are out of validated scope).
- Production hallucination detection without an LLM-based judge as the primary signal. Touchstone Layer 6 ≈ raw word-overlap baseline; both are weaker than budget-tier LLM-based discriminators on naturalistic corpora.

Batch verification at scale is not a compute blocker: `measure()` is linear in document size (5 kB / 50 kB / 500 kB → 16 ms / 161 ms / 1.78 s on CPU), and the external runners demonstrate sustained throughput on 900-1600 example corpora.

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

The Standard is currently in draft (1.0.0-draft.15). When citing it, please
indicate the draft state and the version:

```bibtex
@misc{touchstone_standard_2026,
  author       = {{Clarethium}},
  title        = {Touchstone Standard 1.0 (draft)},
  year         = {2026},
  howpublished = {\url{https://github.com/Clarethium/touchstone/blob/main/STANDARDS/touchstone-1.0.md}},
  note         = {Version 1.0.0-draft.15},
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
