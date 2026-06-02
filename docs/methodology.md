# Touchstone methodology summary

A single-document walkthrough of the substrate hypothesis, the falsification protocol, the empirical evidence (including the trivial-baseline anchor that is the most important methodological discipline in this report), and the named limitations. Intended for readers evaluating Touchstone for adoption, contribution, or methodological critique. The README is the user-facing entry point; this document is the methods reference.

## 1. Substrate hypothesis (and what the data actually shows)

LLM-as-judge approaches measure AI output quality by invoking another LLM to score the output. Touchstone is built on the contrary hypothesis that a meaningful fraction of "is this output supported by its source" can be measured with a substrate that does NOT invoke any LLM on the output: regex pattern matching, exact string search, vocabulary-overlap arithmetic, and structural decomposition. Where an LLM is needed (Layer 1a heading defaultness), it generates baseline documents on the same topic, not a score for the output under measurement.

**Honest finding from the empirical work (§3 below):** Simple lexical features, including a 3-line raw word-overlap baseline, capture roughly 70% of the discriminative signal that budget-tier LLM-based discriminators (MiniCheck Flan-T5-Large, AlignScore-base) extract on three English-news-summarization corpora. Touchstone's Layer 6 inverse_proximity is statistically indistinguishable from a trivial WordOverlapInv baseline. The substrate-independence claim is true but should be attributed to **simple lexical features in general**, not to Touchstone's structured packaging. Touchstone's value is the calibrated falsification protocol, the multi-layer composite with explicit gating, the bootstrap-CI discipline on every reported AUC, the reference suite at `tests/reference/cases/`, and the Standard document, not Layer 6 doing something a trivial baseline doesn't.

The construct claim, stated formally in Standard §3.1, is that the scoring substrate is *independent of the model under measurement*. The reference implementation runs identically on text from any generator; a measurement that shifts systematically with generator identity (beyond what Layer 1b/1c/10 are explicitly designed to surface) would falsify the substrate-independence claim.

## 2. Falsification protocol

Each of the Standard's measurement layers carries an explicit falsifiable construct claim listing the evidence that would invalidate it (Standard §3.5). For the substantive claims (Layers 4, 10, 11) and the substrate-independence claim itself, the §3.5 entries also record status notes referencing the current empirical evidence; the remaining layers (1a, 1b, 1c, 2, 3, 5, 6, 7, 8, 9) carry the falsification criterion without an empirical status yet.

The falsification protocol distinguishes:

- **Full falsification.** A confirmed empirical case where the construct claim is false. Triggers either a Standard amendment (layer redefinition) or a layer retirement under the §10 versioning rules.
- **Partial falsification.** The construct holds in one input regime but not another. Triggers a §9.2 scope update rather than a layer retirement; the layer's validity claim becomes conditional on input regime.

Layer 10's `quality_profile.gap` is the canonical instance of partial falsification: it holds within the calibrated long-form analytical regime (EXP-081 internal corpus, d = -5.238) but does NOT generalize to short summary outputs across any of three external corpora tested (AUC 95% CIs all overlap 0.5000). The §9.2 scope statement is updated to reflect this.

## 3. Empirical evidence

### 3.1 Internal regression benchmarks

Two project-authored corpora ship in the repository, each pinned to byte-exact JSON snapshots verified by pytest:

- **EXP-081** (12 documents, single-vendor): tests whether the composite `quality_profile.gap` discriminates faithful-vs-embellished outputs on the same source. Touchstone records d = -5.238 (Hedges' g = -4.835, 95% bootstrap CI on Cohen's d = [-8.926, -4.498]) against an earlier internal detector's recorded baseline of d = -5.43. This is a regression baseline, not an external replication; the embellishment instruction's textual features (external citations, statistics, forward references) overlap with what Layers 4/5/11 detect.
- **EXP-095** (13 hand-classified outputs, three model families): tests Layer 11's G/F/P decomposition. P-existence direction agreement with manual classification is 100% (13/13); aggregate G/F/P MAE is 0.02-0.04 vs `detector_v031`, 0.12-0.13 vs full manual classification (n=7 outputs with complete annotations).

Both internal benchmarks are reproducible from a fresh clone.

### 3.2 External corpus validation

Three permissively-licensed external corpora streamed from HuggingFace Hub at runtime:

- **RAGTruth Summary** (Wu et al. ACL 2024, MIT): 900 (article, summary) pairs across six instruction-tuned LLM families (gpt-3.5-turbo-0613, gpt-4-0613, llama-2-{7B,13B,70B}-chat, mistral-7B-instruct).
- **SummEval** (Fabbri et al. TACL 2021, MIT): 1600 (article, summary) pairs from 100 CNN/DM articles × 16 machine summaries each, with per-summary 1-5 Likert consistency ratings.
- **HaluEval summarization** (Li et al. EMNLP 2023, Apache-2.0): 1000 (article, summary) pairs from a stratified random sample of 500 documents with ChatGPT-synthesized adversarial hallucinated variants. Perfect 50/50 class balance.

### 3.3 Cross-baseline head-to-head

Two independently-trained LLM-based baselines run against the same input pairs as Touchstone on all three external corpora:

- **MiniCheck Flan-T5-Large** (Tang et al. EMNLP 2024, Apache-2.0): fine-tuned discriminator on LLM-AggreFact. 770M parameters.
- **AlignScore-base** (Zha et al. ACL 2023, MIT): RoBERTa-base alignment-prediction discriminator. 125M parameters. Trained on a different aggregation that does NOT include SummEval.

### 3.4 Cross-corpus cross-baseline finding (with trivial-baseline anchor)

All AUCs reported with 95% percentile bootstrap CIs (1000 stratified resamples, fixed seed). Trivial baselines are computed in `benchmarks/external/trivial_lexical_baselines.py` (a ~250-line stdlib-only script).

| System | RAGTruth Summary | SummEval | HaluEval summarization | Mean | SD |
|---|---|---|---|---|---|
| MiniCheck Flan-T5-Large | 0.7125 [0.6683, 0.7573] | 0.8978 [0.8661, 0.9275]* | 0.6752 [0.6436, 0.7069] | 0.762 | 0.098 |
| AlignScore-base | 0.7368 [0.7006, 0.7699] | 0.8091 [0.7714, 0.8455] | 0.6879 [0.6567, 0.7187] | 0.745 | 0.050 |
| Touchstone Layer 6 inverse_proximity | 0.6723 [0.6296, 0.7116] | 0.7530 [0.7145, 0.7951] | 0.7593 [0.7285, 0.7879] | 0.728 | 0.039 |
| **Trivial WordOverlapInv (3 lines)** | **0.6827 [0.6410, 0.7238]** | **0.7284 [0.6810, 0.7774]** | **0.7431 [0.7136, 0.7712]** | **0.718** | **0.026** |
| Trivial JaccardContentInv | 0.6677 [0.6234, 0.7081] | 0.7089 [0.6622, 0.7547] | 0.4715 [0.4363, 0.5073] | 0.616 | 0.106 |
| Trivial TFIDFCosineInv | 0.6163 [0.5739, 0.6639] | 0.6987 [0.6553, 0.7421] | 0.5385 [0.5032, 0.5740] | 0.618 | 0.065 |
| Touchstone Layer 10 gap (composite) | 0.4981 [0.4830, 0.5111] | 0.5000 [0.5000, 0.5000] | 0.5020 [0.4950, 0.5090] | 0.500 | 0.002 |

*Training-test leakage on SummEval: MiniCheck was trained on AggreFact-CNN, which is SummEval-derived; the SummEval MiniCheck figure is NOT held-out. AlignScore does not have this conflict on SummEval.

Three findings, all statistically grounded:

1. **Touchstone Layer 6 is statistically indistinguishable from WordOverlapInv on every corpus** (CIs heavily overlap on each cell). The "substrate independence" finding belongs to simple lexical features in general, not specifically to Touchstone's structured Layer 6. **WordOverlapInv has the lowest cross-corpus SD (0.026) of any signal tested.** The most substrate-independent baseline in this report is plain word overlap, not Touchstone's preprocessing.
2. **JaccardContentInv collapses on HaluEval** (AUC 0.4715, CI [0.4363, 0.5073], below chance). Filtering stopwords removes the very signal HaluEval's adversarial construction introduces. This is the cleanest evidence in the report that trivial-baseline behaviour is highly preprocessing-dependent and corpus-specific. Touchstone Layer 6 does NOT collapse on HaluEval (AUC 0.7593, CI disjoint from chance), so the per-sentence + content-word formulation produces a more stable signal across preprocessing variants than any single trivial baseline, but at AUC cost.
3. **Layer 10 gap composite is partially falsified.** AUC 0.498-0.513 across all five unique (corpus, task) cells; 95% CIs all *include* 0.5000. The cause is documented: substance components (`source_fidelity`, `entity_grounding`, `epistemic_calibration`) fire on a negligible fraction of short summary outputs (3% maximum on RAGTruth, 0% on SummEval, near-zero on HaluEval), so the composite reduces to presentation-only and carries no fidelity information.

The honest one-sentence summary: **simple lexical features capture ~70% of the discriminative signal on hallucination detection across three English-news-summarization corpora at this signal-strength tier; Touchstone packages them with a falsification protocol, bootstrap CIs, multi-layer integration, and a Standard.**

### 3.5 Cross-task generalization within RAGTruth

| Signal | Summary (n=900) | QA (n=900) | Data2Txt (n=900) |
|---|---|---|---|
| MiniCheck Flan-T5-Large | 0.7125 [0.6683, 0.7573] | 0.6437 [0.5978, 0.6920] | **0.4871 [0.4494, 0.5283]** (chance) |
| Touchstone Layer 4 unsourced_rate | 0.5514 [0.5054, 0.5977] | **0.7603 [0.6907, 0.8260]** | 0.5177 [0.4810, 0.5488] |
| Touchstone Layer 6 inverse_proximity | 0.6723 [0.6296, 0.7116] | 0.6984 [0.6579, 0.7361] | 0.6397 [0.6001, 0.6757] |
| Touchstone Layer 10 gap (composite) | 0.4981 [0.4830, 0.5111] | 0.5127 [0.4985, 0.5295] | 0.5041 [0.4908, 0.5170] |
| Touchstone Layer 11 P proportion | 0.5374 [0.5094, 0.5676] | 0.5591 [0.5283, 0.5895] | 0.5026 [0.5000, 0.5060] |

Two cross-task findings, both load-bearing on the substrate-independence claim:

- **Touchstone Layer 6 is stable across task types.** AUC 0.64-0.70 across Summary, QA, and Data2Txt; the CIs all sit strictly above the chance level.
- **MiniCheck Flan-T5-Large is highly task-dependent.** AUC ranges from 0.71 (Summary) to 0.49 (Data2Txt). On Data2Txt the MiniCheck CI [0.4494, 0.5283] **squarely includes the 0.5000 chance level**: MiniCheck is statistically indistinguishable from chance on RAGTruth Data2Txt. On QA, Touchstone Layer 4 unsourced_rate (0.7603 [0.6907, 0.8260]) statistically outperforms MiniCheck (0.6437 [0.5978, 0.6920]) with CIs disjoint by a small margin; the QA task has high enough output number-density that Layer 4 fires on 277/900 examples.

The cross-task variability of MiniCheck (SD 0.16 across the three task types) compared with Touchstone Layer 6 (SD 0.03) is the strongest single piece of evidence in the report for the substrate-independence claim of Standard §3.1. The zero-LLM-cost substrate produces a more uniform signal across input regimes than a fine-tuned discriminator trained primarily on summarization-style hallucinations.

## 4. Compute disclosure

All external benchmark runs executed on a single CPU (no GPU). Per-corpus wall-clock runtimes:

| Corpus | n_pairs | Touchstone | MiniCheck Flan-T5-L | AlignScore-base |
|---|---|---|---|---|
| RAGTruth Summary | 900 | 2.3 s | 5867 s (~98 min) | 7830 s (~131 min) |
| SummEval | 1600 | 2.1 s | 4124 s (~69 min) | 4128 s (~69 min) |
| HaluEval summarization | 1000 | 1.9 s | 5971 s (~100 min) | 6238 s (~104 min) |

Touchstone:MiniCheck wall-clock ratio is approximately **1:2500** on this CPU. Touchstone:AlignScore is approximately **1:3500**. `measure()` is linear in document size on the band tested: 5 kB / 50 kB / 500 kB documents measure in 16 ms / 161 ms / 1.78 s respectively after the round-3 perf fix (bisect-based overlap check in `_extract_numbers_for_matching` plus hoisted `_content_words(source)` set in `grounding_decomposition`).

## 5. Caveats

- **Adversarial construction caveat on HaluEval.** Touchstone L6's edge over the LLM-based baselines on HaluEval is corpus-construction-aligned, not a methodology-superiority finding. HaluEval's hallucinated summaries are ChatGPT-synthesized to be lexically distributed away from the source article; Layer 6 measures exactly this distance. The two-baseline confirmation (MiniCheck and AlignScore both at AUC ~0.68 vs Layer 6 at 0.76) establishes that this is a baseline-class limitation on adversarial vocabulary-shift corpora rather than a MiniCheck-specific weakness, but it does not promote Layer 6 as the "better" method.
- **Training-test leakage caveat on SummEval.** MiniCheck was trained on LLM-AggreFact, which includes AggreFact-CNN derived from SummEval. MiniCheck's SummEval AUC is NOT held-out. AlignScore does not have this conflict; its SummEval AUC is held-out.
- **All three external corpora are CNN/DM-derived** at some layer of preprocessing. The construct-generalization claim is on summarization-task English news content; legal, medical, code, or non-English text are out of validated scope.
- **MiniCheck CIs**: when the original MiniCheck runners did not retain per-example probabilities in the snapshot, the cross-baseline table reports MiniCheck as a point AUC. The `benchmarks/external/minicheck_from_pairs.py` runner produces snapshots with per-example probs and bootstrap CIs; rows where it has been run carry CIs.
- **Single-annotator on EXP-095.** Inter-annotator agreement is open work; Standard §3.5 names κ ≥ 0.7 as the falsification threshold for Layer 11.
- **No editor body constituted.** Standard §11.4 names this as transitional state; conformance today is self-certification by passing the reference suite at `tests/reference/` plus the unit tests under `tests/`.

## 6. Open work

In priority order for follow-on contributions:

1. **More corpora.** TRUE (Honovich et al. 2022), LLM-AggreFact held-out (Tang et al. 2024), HaluBench / Lynx (Patronus 2024). Each new corpus is roughly one day of CPU compute on the existing runner template.
2. **More baselines.** HHEM 2.1 (Vectara; `trust_remote_code` API rename conflict with current transformers, fixable by pinning transformers OR patching the model's modeling file), SelfCheckGPT (Manakul et al. 2023), G-Eval (Liu et al. 2023), Bespoke-MiniCheck-7B (SOTA MiniCheck variant; requires GPU). AlignScore-large (355M, vs the 125M base shipped here) would deepen the AlignScore data point.
3. **Inter-annotator agreement on EXP-095.** Recruit a second annotator on the existing 13-output corpus; report Cohen's κ alongside the existing manual classifications.
4. **Editor body.** §11.4 transitional state; constituting an independent editor body for the Standard would move the version from "draft" to "ratified".
5. **Construct generalization beyond English summarization.** Legal, medical, code, non-English would each be a separate scope-extension study.

## 7. Reproducibility

Every reported number reproduces from a fresh clone:

- Internal benchmarks: `python -m benchmarks.exp_081_discrimination.run` and `python -m benchmarks.exp_095_grounding.run` produce byte-exact snapshots verified by pytest.
- External benchmarks: `pip install -e ".[external]"` then `python -m benchmarks.external.<corpus>.run` streams the corpus from HuggingFace at runtime and produces a dated snapshot. Bootstrap CIs are added in a second pass by `python -m benchmarks.external.add_bootstrap_cis`.
- AlignScore baselines: separate Python 3.10 venv per `benchmarks/external/alignscore_baselines.py` docstring; runs against pair JSONs exported from the main venv.
- MiniCheck baselines with CIs: `benchmarks/external/minicheck_from_pairs.py` reads the same pair JSONs.
- Reference test suite: `pytest tests/reference/` runs 16 language-agnostic JSON cases covering all required layers (1b, 1c, 2, 3, 4, 5, 6, 7), both experimental layers (8, 9), and Layer 11; cases verify byte-pinned canonical layer outputs.
- Cross-baseline aggregate: `python -m benchmarks.external.cross_baseline_summary --markdown` reads every snapshot and produces the unified table.

## 8. Citation and licensing

- Standard: CC-BY 4.0; cite as `Touchstone Standard 1.0.0-draft.15 (Clarethium, 2026)`.
- Library: Apache-2.0; cite via `CITATION.cff` at the repository root.
- External corpora retain their upstream licenses (RAGTruth MIT, SummEval MIT, HaluEval Apache-2.0); no corpus content is committed to this repository.
- Baseline models retain their upstream licenses (MiniCheck Apache-2.0, AlignScore MIT); no model weights are committed.
