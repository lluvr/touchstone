# Touchstone production readiness

A blunt operational report. The README and methodology doc describe what Touchstone is and what the AUC numbers say. This document answers a different question: **if you deployed Touchstone in production right now, what would actually happen?** Read this before you ship.

The conclusion lives in §6. The rest is the supporting evidence.

## 1. Why AUC is misleading

AUC is a research metric. Production teams care about precision and recall at specific decision thresholds, false-positive burden on human reviewers, and behaviour on the hallucination categories that real LLMs produce. AUC compresses all of that into one number. It tells you "the model can rank positives above negatives some of the time"; it does not tell you whether deploying at threshold X actually solves your problem.

Touchstone substrate-only AUC on three external corpora ranges 0.67-0.76. Without an operational lens that translates into "barely better than chance." With an operational lens it translates into specific use cases that work and specific use cases that don't.

## 2. Operational metrics on the three external corpora

Full numbers are in `benchmarks/external/operational_metrics_2026-05-17.json`. Headline reading:

**RAGTruth Summary (n=900, 23% base rate):**

| System | F1-optimal threshold | Precision at recall 0.9 | Recall at precision 0.9 |
|---|---|---|---|
| MiniCheck Flan-T5-Large | thr 0.20, F1 0.477 | precision 0.257 (2.9 false alarms per catch) | catches 3 of 204 |
| AlignScore-base | thr 0.22, F1 0.497 | precision 0.300 (2.3 false alarms per catch) | catches 1 of 204 |
| Touchstone L6 (WordOverlapInv) | thr 0.26, F1 0.454 | precision 0.271 (2.7 false alarms per catch) | catches 1 of 204 |

**SummEval (n=1600, 10% base rate):**

| System | F1-optimal threshold | Precision at recall 0.9 | Recall at precision 0.9 |
|---|---|---|---|
| MiniCheck (training-test leakage caveat) | thr 0.75, F1 0.646 | precision 0.243 (3.1 false alarms per catch) | catches 11 of 161 |
| AlignScore | thr 0.33, F1 0.449 | precision 0.172 (4.8 false alarms per catch) | catches 4 of 161 |
| Touchstone L6 | thr 0.09, F1 0.434 | precision 0.117 (7.5 false alarms per catch) | catches 5 of 161 |

**HaluEval summarization (n=1000, 50% base rate, adversarial):**

| System | F1-optimal threshold | Precision at recall 0.9 |
|---|---|---|
| MiniCheck | thr 0.07, F1 0.696 | precision 0.563 |
| AlignScore | thr 0.07, F1 0.684 | precision 0.548 |
| Touchstone L6 | thr 0.13, F1 0.712 | precision 0.575 |

**What this means for deployment:**

- **No system, including the trained discriminators, achieves "audit-grade" precision-recall on naturalistic corpora.** At precision 0.9 on RAGTruth Summary, MiniCheck catches 3 of 204 hallucinations (recall 1.5%). At precision 0.9 on SummEval, MiniCheck catches 11 of 161 (recall 7%). This is true of EVERY system tested, not specifically of Touchstone.
- **F1-optimal thresholds are 0.07-0.27, not 0.5.** The Verifier's default `should_flag(threshold=0.5)` is wrong for any deployment scenario; it under-flags by a wide margin. Production teams MUST tune the threshold on their own held-out data.
- **Touchstone L6 is operationally comparable to AlignScore-base on these corpora**, at vastly less compute. That's a real Touchstone value — but it's a value about COMPUTE, not about ACCURACY.

## 3. Triage / review-queue prioritization (the real production use case)

A team that processes 1000 LLM outputs per day and has human review capacity for ~100 doesn't ask "is THIS output hallucinated?" — they ask "WHICH 10% should we review?" That's a ranking problem, not a classification problem. AUC and lift-at-top-K are the right metrics here.

**Top-10% triage on each corpus:**

| Corpus | System | Precision at top 10% | Recall at top 10% | Lift vs random |
|---|---|---|---|---|
| RAGTruth Summary | MiniCheck | 0.500 | 0.221 | **2.21x** |
| RAGTruth Summary | Touchstone L6 | 0.433 | 0.191 | **1.91x** |
| SummEval | MiniCheck | 0.613 | 0.609 | **6.09x** |
| SummEval | Touchstone L6 | 0.425 | 0.422 | **4.22x** |
| HaluEval | MiniCheck | 0.780 | 0.156 | 1.56x (low ceiling due to 50% base rate) |
| HaluEval | Touchstone L6 | 0.820 | 0.164 | 1.64x |

**This is a deployable use case.** A team reviewing the top 10% by Touchstone-ranked score catches **2-4× more hallucinations than random review** on naturalistic corpora. That is a real production value-add for a team that has bounded review capacity.

## 4. The subtle-case stress test (where Touchstone breaks)

The corpora above contain a mix of obvious and subtle hallucinations. To isolate where Touchstone breaks, this report ships 16 hand-crafted (source, faithful, hallucinated) triples covering the subtle-hallucination categories that real LLM deployments produce. Run via `python -m benchmarks.adversarial_subtle.run`.

Headline: **Touchstone substrate-only Verifier correctly separates the hallucinated case from the faithful case on 8 of 16 categories (50% — random)**. At the default threshold of 0.5, the Verifier flags **zero** of the 16 hallucinated cases as suspicious.

| Category | Touchstone catches? | Why |
|---|---|---|
| Number swap ($143B → $134B) | yes | Layer 4 catches the unsourced new number |
| Percentage shift (12% → 21%) | yes | Same |
| Magnitude shift (million → billion) | yes | Source text "million" doesn't appear in output that says "billion" |
| False precision (vague → specific) | yes | New numbers in output are unsourced |
| Fabricated affiliation (adds Steve Jobs) | yes | Layer 5 catches the unsourced entity |
| Counterfactual extension (projects Q2 $155B) | yes | Layer 11 catches "Q2", $155B as projected |
| Subtle entity swap (Maestri → Maestro) | yes (modest) | Layer 5 catches the small entity difference |
| Role/title swap (CEO → CFO) | yes (modest) | Small vocabulary shift |
| **Quarter shift (Q1 → Q3)** | **no** | Touchstone has no temporal-coreference signal |
| **Direction reversal (grew ↔ declined)** | **no** | Same vocabulary, opposite meaning |
| **Imputed cause ("grew, X happened" → "grew due to X")** | **no** | Same words, different relation |
| **Time-frame shift (Q1 was X, up from Q4 Y → reverse)** | **no** | Same numbers, swapped binding |
| **Attribute swap (iPhone grew / Mac declined → reverse)** | **no, and inverts** | Touchstone scored hallucinated LOWER |
| **Scoping shift (segment → total)** | **no** | Same numbers, different scope |
| **Numerical conflation (12% to $143B / 8% growth → swapped)** | **no** | Same numbers, swapped assignment |
| **Relation reversal (Apple acquired X → X acquired Apple)** | **no** | Same words, swapped subject/object |

**The wall is structural.** Touchstone is a regex / arithmetic / lexical-overlap substrate. By construction, it CANNOT detect hallucinations that preserve vocabulary and only change semantic relationships. Those hallucinations require either an NLI model, an LLM judge, or a structured semantic representation.

The 8 categories Touchstone catches are exactly the ones where the hallucination introduces NEW LEXICAL CONTENT (a number not in source, an entity not in source, a year/quarter not in source). The 8 it misses are the ones where the hallucination REARRANGES EXISTING LEXICAL CONTENT.

### 4.1 How the strongest available detectors handle the same 16 cases

The §4 wall claim above states that the substrate's blind spots require "an NLI model, an LLM judge, or a structured semantic representation" to detect. That claim was theoretical when first written. It has now been measured: MiniCheck-Flan-T5-Large, AlignScore-base, and the xAI Grok 4.20 non-reasoning judge were run against the same 16 (source, faithful, hallucinated) triples on 2026-05-18. Reproduce via `python -m benchmarks.adversarial_subtle.join_detectors` after running each detector against `benchmarks/adversarial_subtle/pairs.json`. Full per-case scores live in `benchmarks/adversarial_subtle/cross_detector_2026-05-18.json`.

| Detector | Class | Separated | AUC on the 32 pair rows (95% CI) |
|---|---|---|---|
| Touchstone substrate (L1-L11, default Verifier) | Lexical / arithmetic | 8 of 16 (50%) | n/a (single composite score) |
| MiniCheck Flan-T5-Large | Distilled NLI (~770M) | 15 of 16 (94%) | 0.934 [0.812, 1.000] |
| AlignScore-base | NLI+QA+regression (~125M) | 14 of 16 (88%) | 0.949 [0.859, 1.000] |
| xAI Grok 4.20 non-reasoning | Frontier LLM judge | 16 of 16 (100%) | 0.998 [0.988, 1.000] |

Per-category catch matrix (Y = `halluc_prob > faithful_prob`):

| Category | Touchstone | MiniCheck | AlignScore | Grok 4.20 |
|---|---|---|---|---|
| number_swap_same_scale | Y | Y | Y | Y |
| percentage_shift_plausible_range | Y | Y | Y | Y |
| quarter_shift | . | Y | Y | Y |
| role_title_swap | Y | Y | Y | Y |
| direction_reversal | . | Y | Y | Y |
| imputed_cause | . | Y | . | Y |
| magnitude_shift | Y | Y | Y | Y |
| false_precision | Y | Y | Y | Y |
| time_frame_shift | . | Y | Y | Y |
| attribute_swap | . | Y | Y | Y |
| fabricated_affiliation | Y | Y | Y | Y |
| scoping_shift | . | Y | Y | Y |
| counterfactual_extension | Y | Y | Y | Y |
| numerical_conflation | . | Y | Y | Y |
| subtle_entity_swap | Y | . | Y | Y |
| relation_reversal | . | Y | . | Y |

**What this measurement establishes:**

- The structural-blindness wall is the *substrate's* wall, not the trained-checker class's wall. A ~770M distilled NLI catches 7 of the 8 categories the substrate misses. A frontier LLM judge catches all 8.
- The substrate and MiniCheck are nearly complementary: MiniCheck misses only `subtle_entity_swap` (Maestri → Maestro), which the substrate catches via Layer 5's unsourced-entity logic; the substrate misses 8 categories MiniCheck catches.
- Grok 4.20 non-reasoning is operationally a binary classifier on this prompt: faithful pairs cluster at probability 0.0 and hallucinated pairs at 0.8-1.0. The AUC is near-perfect but the ranking signal within each class is degenerate. A judge with this calibration shape is appropriate for binary flagging but cannot itself drive triage / top-K prioritization without a secondary ranker; combining its verdict with the substrate's continuous score recovers ranking inside each verdict bucket.

**What this measurement does NOT establish:**

- These 16 cases are hand-authored by one author. Detector performance here is necessary, not sufficient, evidence of robustness on naturalistic relational hallucinations. The corresponding measurement on RAGTruth, SummEval, and HaluEval (where every system tested gets AUC 0.67-0.77 and F1 0.45-0.71) is the operational reality check; this table is a category-coverage probe.
- The judge prompt was minimal and unparameterised. Different prompt scaffolding could change the calibration shape (continuous vs binary) without changing the AUC, and would change the production cost-per-call profile.

## 5. The honest production architecture

Touchstone alone is NOT a sufficient hallucination detector for production deployment in the general case. For real-world AI output verification, the production architecture is:

1. **Stage 1: Touchstone substrate (Verifier substrate-only)** — runs in <100 ms per output. Catches: lexically-distinguishable hallucinations (new numbers, new entities, new years, vocabulary drift). Routes outputs into a review queue ordered by suspicion score.
2. **Stage 2: An LLM-based judge (MiniCheck / AlignScore / GPT-4 / Claude / domain-specific NLI)** on the top X% of stage-1 outputs OR on every output if compute budget allows. Catches: semantically-distinguishable hallucinations (direction reversal, attribute swap, scoping shift, relation reversal).
3. **Stage 3: Human review** on the top Y% of stage-1+stage-2 outputs by combined score, with span-level localization from Touchstone Layer 11 to focus reviewer attention.

The Verifier API supports this architecture: `Verifier(use_minicheck=True).score(...)` combines the cheap substrate signal with the caller-supplied trained-discriminator score into a single calibrated probability + signal breakdown + span localization.

Touchstone alone is sufficient for: drift detection on stable production streams, regression testing of LLM output pipelines, education / methodology research, and triage/prioritization for human review queues at the 2-4× lift-vs-random level.

## 6. The honest scope statement

What Touchstone IS:

- A research substrate with calibrated falsification protocol, bootstrap CIs, multi-corpus evaluation, and a reference test suite.
- A triage / review-queue prioritization tool that delivers 2-4× lift over random review on English news summarization.
- A drift detector for stable production streams: aggregate Touchstone scores tracked over time flag distribution shifts.
- A cheap first-pass filter ahead of an LLM-based judge, where the substrate runs in <100 ms and the judge runs only on the top X% suspect outputs.
- The lexical-feature half of a production hallucination detector. Combine with the semantic half (any trained discriminator or LLM judge).

What Touchstone IS NOT:

- A standalone production hallucination detector. The substrate is structurally blind to direction reversal, attribute swap, scoping shift, relation reversal, time-frame shift, and imputed cause — half of all real-world LLM hallucinations.
- An audit-grade verification tool. At precision 0.9, the substrate (and every trained discriminator tested) catches 1-7% of real hallucinations on naturalistic corpora.
- A drop-in replacement for an LLM-based judge. The two are complementary; the substrate is the cheap filter, the judge is the semantic check.

What changes this story:

- Adding a trained semantic discriminator to the Stage-2 architecture moves the production-grade conversation forward. The Verifier ALREADY supports this via `substrate_plus_minicheck` and `substrate_plus_minicheck_alignscore` modes. The 16-case cross-detector measurement in §4.1 is the empirical backing for "the substrate's blind spots are solved by an existing trained checker."
- Building Touchstone-on-its-own up the operational metrics curve is bounded by the substrate's structural limitations (§4). Further investment in pure-substrate AUC has diminishing returns.

## 7. Reproducing every number in this document

- `python -m benchmarks.external.operational_metrics` — recomputes precision/recall/F1/lift on all three corpora from the existing snapshots. Reads only.
- `python -m benchmarks.adversarial_subtle.run` — runs the 16-case subtle-hallucination stress test against the substrate-only Verifier.
- `python -m benchmarks.adversarial_subtle.build_pairs` — emits the 32-row pairs JSON consumed by the cross-detector scorers.
- `.venv-external/bin/python benchmarks/external/minicheck_from_pairs.py benchmarks/adversarial_subtle/pairs.json --label "Adversarial Subtle 16-case" --corpus-dir adversarial_subtle --output benchmarks/adversarial_subtle/minicheck_2026-05-18.json` — re-runs MiniCheck on the 16-case pairs.
- `.venv-alignscore/bin/python benchmarks/external/alignscore_from_pairs.py benchmarks/adversarial_subtle/pairs.json --label "Adversarial Subtle 16-case" --corpus-dir adversarial_subtle --output benchmarks/adversarial_subtle/alignscore_2026-05-18.json` — re-runs AlignScore on the 16-case pairs.
- `XAI_API_KEY=$(vault decrypt XAI_API_KEY) .venv-external/bin/python benchmarks/external/judge_xai_from_pairs.py benchmarks/adversarial_subtle/pairs.json --label "Adversarial Subtle 16-case" --corpus-dir adversarial_subtle --model grok-4.20-0309-non-reasoning --output benchmarks/adversarial_subtle/judge_xai_2026-05-18.json` — re-runs the xAI Grok judge on the 16-case pairs.
- `python -m benchmarks.adversarial_subtle.join_detectors` — joins substrate + MiniCheck + AlignScore + Grok per-case scores into the §4.1 table.
- `python examples/production_verifier.py` — runs an end-to-end demo of the calibrated Verifier API.
- `python -m benchmarks.external.cross_baseline_summary --markdown` — emits the cross-corpus cross-baseline table including trivial-baseline anchor.

All snapshots are byte-pinned; every reported number is reproducible from a fresh clone.
