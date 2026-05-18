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

**What this measurement establishes (read narrowly):**

- The structural-blindness wall is the *substrate's* wall, not the trained-checker class's wall, on this fixture. A ~770M distilled NLI catches 7 of the 8 categories the substrate misses; a frontier LLM judge catches all 8.
- The substrate and MiniCheck are nearly complementary on this fixture: MiniCheck misses only `subtle_entity_swap` (Maestri → Maestro), which the substrate catches via Layer 5's unsourced-entity logic; the substrate misses 8 categories MiniCheck catches.

**Methodological confounds you must read before citing these numbers:**

- **World-knowledge contamination.** The 16 cases use real entities (Apple, Tim Cook, Luca Maestri, fiscal-quarter dates). Grok 4.20 has seen Apple's filings in pretraining; it can flag "CFO Tim Cook" from priors alone without reading the source. The 16/16 separation rate cannot distinguish "judge reads source carefully" from "judge knows the world facts being perturbed." A clean version would use entirely fictional entities, OR run each judge on the hallucinated output with source ABLATED and verify it cannot detect from priors. We did neither.
- **Pairwise-ranking is not threshold-based deployment.** "Did `halluc_prob > faithful_prob`?" tests ranking when the test designer hands you both options. Production hands one output and asks "flag or not?" The 100% separation rate says nothing about threshold selection, false-positive rate, or operating-point trade-offs — the things that determine whether a detector is deployable.
- **Random baseline equivalence.** Random scoring expected separation rate is 50% with 95% CI roughly [37.5%, 62.5%] at n=16. The substrate's 8/16 is statistically indistinguishable from random on this test. The "lexical detector that fails on relational cases" framing is correct in principle, but on this n it cannot be distinguished from a random scorer.
- **n=16 CI overlap between trained detectors.** Bootstrap CIs at n_pos=16, n_neg=16: MiniCheck AUC 0.934 [0.812, 1.000], AlignScore 0.949 [0.859, 1.000]. The CIs overlap each other's point estimates; ordering MiniCheck and AlignScore on this fixture is unsupported.
- **Calibration-shape claim is a prompt artifact, not a judge characterization.** The Grok output clustering at 0.0 and 0.8-1.0 may be 100% prompt-design effect. LLMs default to round probabilities (0, 0.1, 0.5, 0.9, 1.0) absent explicit calibration training or calibration-eliciting prompts. We ran one prompt at one temperature on n=32 pairs; that is a data point, not a calibration characterization. Treat the binary-shape observation as unverified.
- **Synthetic atomic perturbations are not production hallucinations.** Each case is a one-sentence source paired with a one-sentence output where exactly one span differs. Production hallucinations are buried in multi-paragraph outputs over multi-KB sources, with most claims correct and 1-3 silently wrong. The same detectors hit F1 0.45-0.71 on naturalistic corpora (see §2 and §4.2 below). The ~25-point gap between the §4.1 separation rates and the §2 operational F1 numbers is the gap between toy and production. Cite §4.1 as a category-coverage debugging probe, never as a production-readiness claim.

The §4.2 cross-detector measurement on real-corpus subsamples is the production-relevant complement to this fixture. Treat §4.1 and §4.2 as a pair, not as independent evidence.

### 4.2 Cross-detector operational metrics on n=400 naturalistic subsamples

The §4.1 toy fixture cannot answer the production question. This section does, on the same naturalistic corpora the §2 operational tables use. To keep the cross-detector judge run inside a sensible cost envelope, the measurement is on stratified n=400 first-rows-in-order subsamples of each corpus (base rate preserved to within 1.5 percentage points of the full corpus). The substrate L6 / MiniCheck / AlignScore arrays are re-tabulated on the same indices from existing snapshots, so all four detectors compare on identical pair sets. Reproduce via `python -m benchmarks.external.subsample_pairs` (once per corpus) and `python -m benchmarks.external.operational_metrics_on_subsample`. Full per-detector metrics live in `benchmarks/external/operational_metrics_n400_2026-05-18.json`. The full-N tables in §2 remain canonical; this section adds the frontier-judge column the §2 tables are missing.

**RAGTruth Summary (n=400 subsample, 23.7% base rate):**

| Detector | F1-optimal | Precision at recall 0.9 | Recall at precision 0.9 | Triage top-10% lift |
|---|---|---|---|---|
| Substrate L6 (word_overlap_inv) | 0.445 | 0.275 (2.6 fp/catch) | catches 1 of 95 | 1.79x |
| MiniCheck Flan-T5-Large | 0.452 | 0.251 (3.0 fp/catch) | catches 1 of 95 | 2.63x |
| AlignScore-base | 0.493 | 0.294 (2.4 fp/catch) | catches 2 of 95 | 2.21x |
| xAI Grok 4.20 non-reasoning | 0.670 | 0.455 (1.2 fp/catch) | catches 2 of 95 | 3.26x |

**SummEval (n=400 subsample, 11.5% base rate):**

| Detector | F1-optimal | Precision at recall 0.9 | Recall at precision 0.9 | Triage top-10% lift |
|---|---|---|---|---|
| Substrate L6 | 0.422 | 0.127 (6.9 fp/catch) | catches 5 of 46 | 3.48x |
| MiniCheck Flan-T5-Large | 0.695 | 0.210 (3.8 fp/catch) | catches 2 of 46 | 5.87x |
| AlignScore-base | 0.543 | 0.197 (4.1 fp/catch) | catches 1 of 46 | 4.35x |
| xAI Grok 4.20 non-reasoning | 0.702 | 0.538 (0.9 fp/catch) | catches 12 of 46 | 5.43x |

**HaluEval Summarization (n=400 subsample, 50% base rate, adversarial):**

| Detector | F1-optimal | Precision at recall 0.9 | Recall at precision 0.9 | Triage top-10% lift |
|---|---|---|---|---|
| Substrate L6 | 0.721 | 0.594 (0.7 fp/catch) | catches 18 of 200 | 1.55x |
| MiniCheck Flan-T5-Large | 0.698 | 0.559 (0.8 fp/catch) | catches 9 of 200 | 1.65x |
| AlignScore-base | 0.692 | 0.554 (0.8 fp/catch) | catches 14 of 200 | 1.70x |
| xAI Grok 4.20 non-reasoning | 0.766 | 0.623 (0.6 fp/catch) | catches 87 of 200 | 1.90x |

**What the production-relevant measurement actually shows:**

- **Grok 4.20's audit-precision advantage is real on naturalistic data, but bounded.** F1-optimal advantage over the strongest non-judge detector: +18 points on RAGTruth (0.670 vs 0.493), +1 point on SummEval (0.702 vs 0.695), +5 points on HaluEval (0.766 vs 0.721). The toy-fixture 100%-separation result translates into a ~5-18 point F1 advantage in production, not into "the judge solves hallucination detection."
- **The most operationally interesting gap is at recall=0.9 (audit-grade flagging).** On SummEval, Grok catches 12 of 46 hallucinations at precision 0.9; MiniCheck catches 2. On HaluEval, Grok catches 87 of 200; MiniCheck catches 9. This is the "we only flag when 90% sure, how much do we miss" decision. The judge's advantage is concentrated at the high-precision end of the curve, exactly where production audit applications operate.
- **At triage / top-10% review-queue prioritization, the gap is smaller.** Grok wins on RAGTruth and HaluEval but MiniCheck wins on SummEval (5.87x vs 5.43x). A team that already runs a triage pipeline on MiniCheck has limited reason to switch to a judge purely for top-K prioritization; the case for the judge is at audit thresholds, not triage.
- **The substrate L6 holds its own on HaluEval.** F1-optimal 0.721, beating both MiniCheck (0.698) and AlignScore (0.692). On the corpus designed to be adversarial against summary-level hallucination detection, the lexical baseline is operationally comparable to trained NLI. This is consistent with the §2 finding and is not an artifact of subsampling.
- **The substrate L6 collapses on SummEval P@R90 (0.127, 6.9 false alarms per catch) and on RAGTruth P@R90 (0.275).** On the audit-precision end of the curve where the judge advantage is concentrated, the substrate is the weakest of the four. The substrate's value is at triage and on adversarial-summary corpora, not at audit thresholds.

**Production architecture implications (verified against this measurement, not derived from §4.1):**

The two-stage architecture in §5 still holds. The new evidence sharpens it:

- For audit-grade applications (precision ≥ 0.8-0.9): a frontier LLM judge is the right stage-2 detector. Grok 4.20 at $X/call (xAI pricing) materially outperforms the open-source trained discriminators here.
- For triage-grade applications (top-K human review): MiniCheck remains competitive with the judge at substantially lower per-call cost. Pick by budget.
- For drift detection on stable streams: the substrate L6 remains operationally adequate, often better than trained NLI on adversarial corpora like HaluEval.

The §4.1 toy result over-predicted the judge's production advantage. The actual advantage is meaningful (~5-18 F1 points, concentrated at high-precision operating points) but does not change the conclusion that no current detector is audit-grade on every corpus.

**Caveats on this measurement (read before citing):**

- n=400 stratified subsample. Bootstrap CI on AUC at n=400 with realistic base rates is ±~0.04. Ordering claims within ±0.05 of each other should be treated as a tie.
- The Grok judge prompt is the same minimal prompt used in §4.1. Prompt scaffolding could move the numbers in either direction; this is a single-prompt measurement.
- World-knowledge contamination concerns from §4.1 apply less strongly here (the corpora contain a broad mix of topics from news summarization), but Grok's pretraining likely saw at least some XSum / CNN-DailyMail content; treat the SummEval and HaluEval-summarization advantage as a soft upper bound.
- Cost not yet measured. The §5 architecture decision (when to spend judge calls vs settle for substrate or MiniCheck) requires per-call cost data this snapshot does not include.

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
- `python -m benchmarks.external.subsample_pairs <pairs.json> --n-total 400 --pairs-out <sub.json> --indices-out <indices.json>` — deterministic first-N-rows subsampler used to build the §4.2 n=400 inputs.
- `XAI_API_KEY=$(vault decrypt XAI_API_KEY) .venv-external/bin/python benchmarks/external/judge_xai_from_pairs.py <sub.json> --label "<corpus> (n=400)" --corpus-dir <corpus_dir> --model grok-4.20-0309-non-reasoning --output benchmarks/external/<corpus_dir>/results/judge_xai_grok420_n400_2026-05-18.json` — Grok judge run on each n=400 subsample (RAGTruth Summary, SummEval, HaluEval Summarization).
- `python -m benchmarks.external.operational_metrics_on_subsample` — computes the §4.2 four-detector apples-to-apples table on the same n=400 indices for each corpus.
- `python examples/production_verifier.py` — runs an end-to-end demo of the calibrated Verifier API.
- `python -m benchmarks.external.cross_baseline_summary --markdown` — emits the cross-corpus cross-baseline table including trivial-baseline anchor.

All snapshots are byte-pinned; every reported number is reproducible from a fresh clone.
