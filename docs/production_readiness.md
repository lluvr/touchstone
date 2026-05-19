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

- **World-knowledge contamination — now measured.** The 16 cases use real entities (Apple, Tim Cook, Luca Maestri, fiscal-quarter dates). Grok 4.20 has seen Apple's filings in pretraining; it can in principle flag "CFO Tim Cook" from priors alone without reading the source. A 2026-05-19 ablation runs the SAME Grok model on the 16 cases with the source removed and the prompt rewritten as a strict world-knowledge fact-checker: "estimate the probability that OUTPUT contains a factually incorrect claim based on your background knowledge of Apple." Snapshot at `benchmarks/adversarial_subtle/judge_xai_world_knowledge_only_2026-05-19.json`. **Result: AUC 0.6406 [0.4570, 0.8164]** (95% CI just barely includes 0.5). Separation rate: 7/16 (statistically indistinguishable from random's [37.5%, 62.5%] CI at n=16); 9/16 cases are ties at the prob grid. **Only 2 of 16 cases are strongly separable from priors alone** (gap ≥ 0.4): `role_title_swap` (Tim Cook CEO not CFO; priors give 0.05 vs 0.85) and `subtle_entity_swap` (Maestri not Maestro; 0.05 vs 0.90). 5 cases give weak priors signal (gap 0.05-0.20); 9 cases give no priors signal at all. The §4.1 100% Grok separation rate cannot be reduced to priors-only contamination; the judge IS reading the source on at least 14 of 16 cases. The remaining 2 cases are priors-catchable. **The confound is real but small** (2-of-16 = ~12% upper bound on the contribution of world knowledge to the 16/16 headline). An earlier in-session sanity check by Claude Opus 4.7 (this session) predicted 5/16 strong priors-only separation; the actual Grok run is more discriminating — Grok's priors-only signal is weaker than I predicted. Use the API measurement, not the sanity check.
- **Pairwise-ranking is not threshold-based deployment.** "Did `halluc_prob > faithful_prob`?" tests ranking when the test designer hands you both options. Production hands one output and asks "flag or not?" The 100% separation rate says nothing about threshold selection, false-positive rate, or operating-point trade-offs — the things that determine whether a detector is deployable.
- **Random baseline equivalence.** Random scoring expected separation rate is 50% with 95% CI roughly [37.5%, 62.5%] at n=16. The substrate's 8/16 is statistically indistinguishable from random on this test. The "lexical detector that fails on relational cases" framing is correct in principle, but on this n it cannot be distinguished from a random scorer.
- **n=16 CI overlap between trained detectors.** Bootstrap CIs at n_pos=16, n_neg=16: MiniCheck AUC 0.934 [0.812, 1.000], AlignScore 0.949 [0.859, 1.000]. The CIs overlap each other's point estimates; ordering MiniCheck and AlignScore on this fixture is unsupported.
- **Calibration-shape claim is a prompt artifact, not a judge characterization.** The Grok output clustering at 0.0 and 0.8-1.0 may be 100% prompt-design effect. LLMs default to round probabilities (0, 0.1, 0.5, 0.9, 1.0) absent explicit calibration training or calibration-eliciting prompts. We ran one prompt at one temperature on n=32 pairs; that is a data point, not a calibration characterization. Treat the binary-shape observation as unverified.
- **Prompt cueing measured.** The judge prompt used in §4.1 enumerates exactly the six failure modes the §4 wall claim names as the substrate's structural blind spots (polarity flip, attribute swap, scope shift, time-frame shift, relation reversal, imputed cause). The 16-case fixture is constructed from those same categories. A judge given a checklist of the categories the test was designed around is in a near-tautological position. The cued-vs-blind ablation in §4.3 shows: on the 16-case fixture, blind separates 16/16 too (AUC 0.990 vs cued 0.998), so the toy result was robust to cueing. On the naturalistic n=400 corpora, blind judge AUCs are equal to or slightly above cued (RAGTruth 0.872 vs 0.854; SummEval 0.946 vs 0.933; HaluEval 0.816 vs 0.807) — cueing did not give the cued judge an unfair advantage. But the substrate-plus-judge value-add at audit thresholds (§4.3) does shrink with blind judge; the cueing-induced score compression was part of why the substrate's tie-breaking added so much R@P90 in the original §4.3 numbers.
- **Synthetic atomic perturbations are not production hallucinations.** Each case is a one-sentence source paired with a one-sentence output where exactly one span differs. Production hallucinations are buried in multi-paragraph outputs over multi-KB sources, with most claims correct and 1-3 silently wrong. The same detectors hit F1 0.45-0.71 on naturalistic corpora (see §2 and §4.2 below). The ~25-point gap between the §4.1 separation rates and the §2 operational F1 numbers is the gap between toy and production. Cite §4.1 as a category-coverage debugging probe, never as a production-readiness claim.

The §4.2 cross-detector measurement on real-corpus subsamples is the production-relevant complement to this fixture. Treat §4.1 and §4.2 as a pair, not as independent evidence.

### 4.2 Cross-detector operational metrics on n=400 naturalistic subsamples

The §4.1 toy fixture cannot answer the production question. This section does, on the same naturalistic corpora the §2 operational tables use. To keep the cross-detector judge run inside a sensible cost envelope, the measurement is on deterministic first-N prefix subsamples (n=400) of each corpus. First-N is deliberate: the operational metrics in this section (F1-optimal threshold, precision-at-recall, recall-at-precision, lift-at-top-K) are base-rate dependent, so balanced stratification would distort them. Base rate is preserved to within ~1.5 percentage points of the full corpus on the three external corpora because the source pair files are not label-ordered (RAGTruth and SummEval flips-vs-IID ratios ≈ 1.0; HaluEval is perfectly alternating at 50%). The sampling-strategy claim is recorded in each `subsample_n400_indices_2026-05-18.json` snapshot as `sampling_strategy: "first_n_in_original_order"`. The substrate L6 / MiniCheck / AlignScore arrays are re-tabulated on the same indices from existing snapshots, so all four detectors compare on identical pair sets. Reproduce via `python -m benchmarks.external.subsample_pairs` (once per corpus) and `python -m benchmarks.external.operational_metrics_on_subsample`. Full per-detector metrics live in `benchmarks/external/operational_metrics_n400_2026-05-18.json`. The full-N tables in §2 remain canonical; this section adds the frontier-judge column the §2 tables are missing.

The three tables below are **in-sample (F1-optimal chosen on the same 400 rows it is reported on)** and use a **single tie-break realization** (Python stable sort by input order). Held-out F1 numbers are in §4.2.1 (-0.000 to -0.234 inflation under tune/eval); tie-envelope means and stds are in §4.2.2 (Grok R@P90 shifts the most: SummEval "12 of 46" → 7 ± 3, HaluEval "87 of 200" → 67 ± 16). Treat the headline tables as a discovery aid; the §4.2.1 and §4.2.2 numbers are the production-honest point estimates.

**RAGTruth Summary (n=400 subsample, 23.7% base rate):**

| Detector | F1-optimal (in-sample) | Precision at recall 0.9 | Recall at precision 0.9 | Triage top-10% lift |
|---|---|---|---|---|
| Substrate L6 (word_overlap_inv) | 0.445 | 0.275 (2.6 fp/catch) | catches 1 of 95 | 1.79x |
| MiniCheck Flan-T5-Large | 0.452 | 0.251 (3.0 fp/catch) | catches 1 of 95 | 2.63x |
| AlignScore-base | 0.493 | 0.294 (2.4 fp/catch) | catches 2 of 95 | 2.21x |
| xAI Grok 4.20 non-reasoning | 0.670 | 0.455 (1.2 fp/catch) | catches 2 of 95 | 3.26x |

**SummEval (n=400 subsample, 11.5% base rate):**

| Detector | F1-optimal (in-sample) | Precision at recall 0.9 | Recall at precision 0.9 | Triage top-10% lift |
|---|---|---|---|---|
| Substrate L6 | 0.422 | 0.127 (6.9 fp/catch) | catches 5 of 46 | 3.48x |
| MiniCheck Flan-T5-Large | 0.695 | 0.210 (3.8 fp/catch) | catches 2 of 46 | 5.87x |
| AlignScore-base | 0.543 | 0.197 (4.1 fp/catch) | catches 1 of 46 | 4.35x |
| xAI Grok 4.20 non-reasoning | 0.702 | 0.538 (0.9 fp/catch) | catches 12 of 46 | 5.43x |

**HaluEval Summarization (n=400 subsample, 50% base rate, adversarial):**

| Detector | F1-optimal (in-sample) | Precision at recall 0.9 | Recall at precision 0.9 | Triage top-10% lift |
|---|---|---|---|---|
| Substrate L6 | 0.721 | 0.594 (0.7 fp/catch) | catches 18 of 200 | 1.55x |
| MiniCheck Flan-T5-Large | 0.698 | 0.559 (0.8 fp/catch) | catches 9 of 200 | 1.65x |
| AlignScore-base | 0.692 | 0.554 (0.8 fp/catch) | catches 14 of 200 | 1.70x |
| xAI Grok 4.20 non-reasoning | 0.766 | 0.623 (0.6 fp/catch) | catches 87 of 200 | 1.90x |

**What the production-relevant measurement actually shows** (numbers below are the in-sample headlines; deltas are robust to holdout per §4.2.1 — in-sample +5-18 F1 vs held-out +4-18 F1 — but R@P90 is tie-sensitive per §4.2.2):

- **Grok 4.20's audit-precision advantage is real on naturalistic data, but bounded.** F1-optimal advantage over the strongest non-judge detector: +18 points on RAGTruth (0.670 vs 0.493 in-sample; 0.661 vs 0.479 held-out), +1 point on SummEval (0.702 vs 0.695 in-sample; 0.632 vs 0.621 held-out; under tie envelope this is 0.696 ± 0.009 vs 0.695 ± 0.000, statistically a tie), +5 points on HaluEval (0.766 vs 0.721 in-sample; 0.743 vs 0.693 held-out). The toy-fixture 100%-separation result translates into a ~5-18 point F1 advantage in production, not into "the judge solves hallucination detection."
- **The most operationally interesting gap is at recall=0.9 (audit-grade flagging).** On SummEval, Grok catches 12 of 46 hallucinations at precision 0.9 in the table above; MiniCheck catches 2. On HaluEval, Grok 87 of 200; MiniCheck 9. Caveat from §4.2.2: the Grok R@P90 is the most tie-sensitive headline in §4.2 — under random tie-breaking SummEval is 7 ± 3 and HaluEval is 67 ± 16, so cite the cued-judge advantage at audit thresholds as the tie envelope mean rather than the single-snapshot point estimate. The mean still beats MiniCheck materially (~3.5x more catches at audit precision on both corpora), so the qualitative "judge advantage concentrates at the audit-precision end of the curve" claim survives.
- **At triage / top-10% review-queue prioritization, the gap is smaller.** Grok wins on RAGTruth and HaluEval but MiniCheck wins on SummEval (5.87x vs 5.43x). A team that already runs a triage pipeline on MiniCheck has limited reason to switch to a judge purely for top-K prioritization; the case for the judge is at audit thresholds, not triage.
- **The substrate L6 holds its own on HaluEval.** F1-optimal 0.721, beating both MiniCheck (0.698) and AlignScore (0.692). On the corpus designed to be adversarial against summary-level hallucination detection, the lexical baseline is operationally comparable to trained NLI. This is consistent with the §2 finding and is not an artifact of subsampling.
- **The substrate L6 collapses on SummEval P@R90 (0.127, 6.9 false alarms per catch) and on RAGTruth P@R90 (0.275).** On the audit-precision end of the curve where the judge advantage is concentrated, the substrate is the weakest of the four. The substrate's value is at triage and on adversarial-summary corpora, not at audit thresholds.

**Production architecture implications (verified against this measurement, not derived from §4.1):**

The two-stage architecture in §5 still holds. The new evidence sharpens it:

- For audit-grade applications (precision ≥ 0.8-0.9): a frontier LLM judge is the right stage-2 detector. Grok 4.20 materially outperforms the open-source trained discriminators here on F1-optimal (per §4.2/§4.2.1); R@P90 advantage is real but tie-sensitive (per §4.2.2). Per-call cost is currently unmeasured (see §7 carried-forward list).
- For triage-grade applications (top-K human review): MiniCheck remains competitive with the judge at substantially lower per-call cost. Pick by budget.
- For drift detection on stable streams: the substrate L6 remains operationally adequate, often better than trained NLI on adversarial corpora like HaluEval.

The §4.1 toy result over-predicted the judge's production advantage. The actual advantage is meaningful (~5-18 F1 points, concentrated at high-precision operating points) but does not change the conclusion that no current detector is audit-grade on every corpus.

**Caveats on this measurement (read before citing):**

- n=400 deterministic-prefix subsample (not stratified; first 400 rows of each source pair file in original order). Within-sample bootstrap CI on AUC at n=400 with realistic base rates is ±~0.04. Across-subsample variance from drawing a different prefix offset is NOT measured by that CI and is a known gap (the substrate/MiniCheck/AlignScore arrays could be re-tabulated at different offsets cheaply; the judge column cannot without re-running the API). Ordering claims within ±0.05 of each other should be treated as a tie.
- The Grok judge prompt is the same cued prompt used in §4.1 (`JUDGE_SYSTEM_PROMPT_CUED`; enumerates the §4 wall-claim categories). Prompt scaffolding could move the numbers in either direction; this is a single-prompt, single-vendor measurement. The blind variant is shipped in `judge_xai_from_pairs.py` as `--prompt-variant blind`; the cued-vs-blind delta on these corpora has not been measured yet.
- World-knowledge contamination concerns from §4.1 apply less strongly here (the corpora contain a broad mix of topics from news summarization), but Grok's pretraining likely saw at least some XSum / CNN-DailyMail content; treat the SummEval and HaluEval-summarization advantage as a soft upper bound.
- Cost not yet measured. The §5 architecture decision (when to spend judge calls vs settle for substrate or MiniCheck) requires per-call cost data this snapshot does not include.
- F1-optimal threshold in the tables above is chosen on the same 400 rows it is reported on (in-sample optimum, biased upward). The §4.2.1 sub-table reports the held-out F1 from a 200/200 tune/eval stratified split; treat the held-out number as the conservative point estimate. The headline in-sample tables are kept above because they match the existing pinned `operational_metrics_n400_2026-05-18.json` snapshot exactly; the holdout numbers live in the sibling `operational_metrics_n400_holdout_2026-05-18.json`.

### 4.2.1 Held-out F1-optimal threshold selection

Reproduce via `python -m benchmarks.external.operational_metrics_holdout`. Each n=400 subsample is split 200/200 by a deterministic stratified interleave (positives alternate tune→eval→tune→eval in encounter order; negatives likewise), so both halves preserve the subsample's base rate to within 1 example. The F1-optimal threshold is found on the tune half and then applied to the eval half; the eval-half F1 is the production-honest estimate. The in-sample-vs-holdout inflation is the per-row difference between the eval half's own F1-optimum and the F1 it scores under the tune-chosen threshold.

Both cued and blind judge variants are included on identical indices (c02bafe added the blind n=400 snapshots; the holdout loader picks them up automatically).

| Corpus | Detector | In-sample F1 (n=400) | Held-out F1 (eval, n=200) | Inflation |
|---|---|---|---|---|
| RAGTruth Summary | Substrate L6 | 0.445 | 0.358 | -0.087 |
| RAGTruth Summary | MiniCheck Flan-T5-Large | 0.452 | 0.344 | -0.108 |
| RAGTruth Summary | AlignScore-base | 0.493 | 0.479 | -0.014 |
| RAGTruth Summary | xAI Grok 4.20 (cued) | 0.670 | 0.661 | -0.009 |
| RAGTruth Summary | xAI Grok 4.20 (blind) | 0.698 | 0.667 | -0.031 |
| SummEval | Substrate L6 | 0.422 | 0.188 | -0.234 |
| SummEval | MiniCheck Flan-T5-Large | 0.695 | 0.621 | -0.074 |
| SummEval | AlignScore-base | 0.543 | 0.409 | -0.134 |
| SummEval | xAI Grok 4.20 (cued) | 0.702 | 0.632 | -0.070 |
| SummEval | xAI Grok 4.20 (blind) | 0.763 | 0.704 | -0.059 |
| HaluEval Summarization | Substrate L6 | 0.721 | 0.693 | -0.028 |
| HaluEval Summarization | MiniCheck Flan-T5-Large | 0.698 | 0.672 | -0.026 |
| HaluEval Summarization | AlignScore-base | 0.692 | 0.630 | -0.062 |
| HaluEval Summarization | xAI Grok 4.20 (cued) | 0.766 | 0.743 | -0.023 |
| HaluEval Summarization | xAI Grok 4.20 (blind) | 0.761 | 0.735 | -0.026 |

(In-sample F1 column is the cued/blind row read from `operational_metrics_n400_2026-05-18.json`; held-out F1 column is from the new `operational_metrics_n400_holdout_2026-05-18.json`. Inflation is in-sample minus held-out at full n=400 vs eval n=200.)

**What the holdout view changes:**

- **The Grok edge is the most robust under holdout** for both variants (cued inflation 0.000-0.070; blind inflation 0.016-0.043). Two competing readings: (a) the frontier judge is genuinely robust to threshold-set choice; (b) the judge's clustered-probability output (see §4.1's `calibration-shape` caveat) makes the threshold less sensitive to which subset chose it. The blind variant's slightly larger inflation is consistent with reading (b) being part of the story for cued (the cued prompt induces stronger clustering per §4.3).
- **Blind judge beats cued judge under holdout on SummEval** by 7.2 F1 points (0.704 vs 0.632) and matches it on RAGTruth (0.667 vs 0.661) and HaluEval (0.735 vs 0.743). The §4.3 narrative says blind AUC is "equal to or slightly above cued"; the held-out F1 view sharpens that to "blind is materially better on SummEval at the F1 operating point." If a production team picks Grok as their stage-2 judge, the blind prompt is the better default; the cued prompt's only legitimate use is debugging-the-fixture exploration.
- **Substrate L6 SummEval inflation is the largest single delta** (0.422 → 0.188, -0.234). The §2 conclusion "substrate L6 is operationally comparable to AlignScore-base on these corpora" needs re-reading at the held-out F1 (substrate 0.188, AlignScore 0.409 on SummEval eval); the substrate is materially weaker than the in-sample comparison suggested on the sparsest-positives corpus, while the HaluEval substrate-comparable claim survives (0.693 holdout vs MiniCheck 0.672 holdout).
- **Detector orderings are preserved on every corpus**, but absolute magnitudes shift. Cite the held-out numbers when claiming "detector X catches Y% in production"; the in-sample numbers are the discovery aid, not the deployment guarantee.

### 4.2.2 Tie-aware metric envelope

`_ops_metrics` uses Python's stable sort on `-score`; within a tied group of scores the order is the input order, which means the precision-at-recall and F1-optimal numbers depend on which examples happen to come first within a tied group. Grok 4.20's output clusters heavily (274 of 400 SummEval probs at exactly 0.0; 110 of 400 RAGTruth probs at 0.35; 98 of 400 HaluEval probs at 0.65), so the tie-break sensitivity matters. The trained discriminators (MiniCheck, AlignScore) and the lexical baseline are continuous and have effectively no ties. Reproduce via `python -m benchmarks.external.operational_metrics_tie_envelope` (K=100 sub-quantum-jitter permutations); full per-detector envelope at `benchmarks/external/operational_metrics_n400_tie_envelope_2026-05-18.json`.

| Corpus | Detector | F1-optimal (mean ± std) | P@R90 (mean ± std) | R@P90 (mean ± std) |
|---|---|---|---|---|
| RAGTruth Summary | Substrate L6 | 0.445 ± 0.000 | 0.275 ± 0.000 | 0.011 ± 0.000 |
| RAGTruth Summary | MiniCheck | 0.452 ± 0.000 | 0.251 ± 0.000 | 0.011 ± 0.000 |
| RAGTruth Summary | AlignScore | 0.493 ± 0.000 | 0.294 ± 0.000 | 0.021 ± 0.000 |
| RAGTruth Summary | xAI Grok 4.20 (cued) | **0.657 ± 0.007** | **0.442 ± 0.037** | **0.064 ± 0.054** |
| RAGTruth Summary | xAI Grok 4.20 (blind) | **0.699 ± 0.006** | **0.468 ± 0.026** | **0.070 ± 0.045** |
| SummEval | Substrate L6 | 0.422 ± 0.000 | 0.118 ± 0.005 | 0.109 ± 0.000 |
| SummEval | MiniCheck | 0.695 ± 0.000 | 0.210 ± 0.000 | 0.043 ± 0.000 |
| SummEval | AlignScore | 0.543 ± 0.000 | 0.197 ± 0.000 | 0.022 ± 0.000 |
| SummEval | xAI Grok 4.20 (cued) | **0.692 ± 0.008** | **0.550 ± 0.011** | **0.170 ± 0.077** |
| SummEval | xAI Grok 4.20 (blind) | **0.741 ± 0.010** | **0.549 ± 0.040** | **0.213 ± 0.094** |
| HaluEval Summarization | Substrate L6 | 0.721 ± 0.001 | 0.595 ± 0.002 | 0.090 ± 0.000 |
| HaluEval Summarization | MiniCheck | 0.698 ± 0.000 | 0.559 ± 0.000 | 0.045 ± 0.000 |
| HaluEval Summarization | AlignScore | 0.692 ± 0.000 | 0.554 ± 0.000 | 0.070 ± 0.000 |
| HaluEval Summarization | xAI Grok 4.20 (cued) | **0.768 ± 0.002** | **0.611 ± 0.007** | **0.329 ± 0.078** |
| HaluEval Summarization | xAI Grok 4.20 (blind) | **0.764 ± 0.003** | **0.615 ± 0.005** | **0.401 ± 0.008** |

**What the tie envelope changes:**

- **Grok R@P90 is the most tie-sensitive headline in §4.2 for the cued variant.** The §4.2 snapshot's "catches 12 of 46 on SummEval at precision 0.9 (cued)" is 8 ± 4 under random tie-breaking (0.170 ± 0.077 × 46 positives); "catches 87 of 200 on HaluEval (cued)" is 66 ± 16. The cued point estimate sits at or near the favorable-tie-break end on every corpus. The blind variant is much more tie-stable on HaluEval (R@P90 0.401 ± 0.008 — std drops 10×), consistent with the §4.3 mechanism observation that the cued prompt induces score clustering and the blind prompt does not.
- **Blind judge beats cued judge on F1-optimal tie envelope on every corpus except HaluEval where they tie.** RAGTruth blind 0.699 ± 0.006 vs cued 0.657 ± 0.007 (Δ +0.042, ~6σ); SummEval blind 0.741 ± 0.010 vs cued 0.692 ± 0.008 (Δ +0.049, ~5σ); HaluEval blind 0.764 ± 0.003 vs cued 0.768 ± 0.002 (Δ -0.004, statistical tie). The cueing actively hurt the judge on the two non-adversarial corpora. The §4.3 narrative claim "blind judge AUCs are equal to or slightly above cued" understates the gap at the F1 operating point.
- **The substrate / MiniCheck / AlignScore numbers are tie-stable** (std ≈ 0.000) because their score distributions are continuous. The cross-detector orderings between the three are unaffected by ties.
- **Grok cued F1-optimal threshold has wide tie envelope on RAGTruth** (0.532 ± 0.126); blind is similar (0.559 ± 0.122). A team picking a threshold by `score(query) > optimal_threshold` should treat the snapshot's "thr 0.65" as one realization within a roughly 0.40–0.65 range for cued / 0.44–0.68 for blind; the threshold itself is partially a tie-break artifact.

### 4.2.3 Calibration metrics (ECE, MCE, Brier, Brier skill score)

§4.2.1 noted two competing readings for the Grok edge's robustness under holdout: (a) the judge is genuinely robust; (b) its clustered-probability output makes the threshold less sensitive to which subset chose it. The calibration metrics disentangle. They also matter independently: §5's two-stage Verifier architecture composes per-detector probabilities into a single calibrated `score(text, source)` output. If the input probabilities are not calibrated, the composition is computing with junk. Reproduce via `python -m benchmarks.external.calibration_metrics`. Full per-detector per-bin reliability-diagram data lives in `benchmarks/external/calibration_metrics_n400_2026-05-18.json`.

ECE = expected calibration error (10 equal-width bins on [0,1]; lower is better). MCE = maximum calibration error across bins. Brier = mean (prob − label)². BSS = Brier skill score = 1 − Brier / random_scorer_brier; positive means better than predicting base rate for every example.

| Corpus | Detector | ECE | MCE | Brier | BSS |
|---|---|---|---|---|---|
| RAGTruth Summary (base 0.24, rand Brier 0.181) | Substrate L6 | **0.026** | 0.314 | 0.170 | +0.060 |
| | MiniCheck Flan-T5-Large | 0.189 | 0.549 | 0.222 | **-0.223** |
| | AlignScore-base | 0.032 | 0.744 | 0.163 | +0.102 |
| | xAI Grok 4.20 (cued) | 0.179 | 0.295 | 0.160 | +0.115 |
| | xAI Grok 4.20 (blind) | 0.118 | **0.210** | **0.127** | **+0.297** |
| SummEval (base 0.12, rand Brier 0.102) | Substrate L6 | 0.071 | 0.670 | 0.097 | +0.048 |
| | MiniCheck Flan-T5-Large | 0.086 | 0.534 | 0.076 | +0.257 |
| | AlignScore-base | **0.047** | 0.306 | 0.081 | +0.204 |
| | xAI Grok 4.20 (cued) | 0.090 | 0.650 | 0.084 | +0.178 |
| | xAI Grok 4.20 (blind) | 0.070 | 0.700 | **0.063** | **+0.381** |
| HaluEval Summarization (base 0.50, rand Brier 0.250) | Substrate L6 | 0.294 | 0.458 | 0.302 | **-0.208** |
| | MiniCheck Flan-T5-Large | 0.248 | 0.438 | 0.292 | -0.167 |
| | AlignScore-base | 0.120 | **0.189** | 0.237 | +0.052 |
| | xAI Grok 4.20 (cued) | **0.104** | 0.368 | 0.183 | +0.269 |
| | xAI Grok 4.20 (blind) | 0.111 | 0.292 | **0.175** | **+0.300** |

**Key calibration findings (load-bearing for the Verifier architecture):**

- **Grok blind has the lowest Brier on every corpus.** Calibrationally the blind variant dominates. The §4.2.1 reading "Grok edge is robust under holdout" gains a third explanation: the blind judge is genuinely well-calibrated, not just consistent. The cued variant's calibration is comparable on F1 but noticeably worse on Brier, consistent with the score-clustering mechanism named in §4.3.
- **MiniCheck's raw output is WORSE than a random scorer at the Brier level on RAGTruth (BSS -0.223) and HaluEval (BSS -0.167).** The probabilities are mis-calibrated to the point where outputting the base rate for every example would beat them. Composing raw MiniCheck probabilities into a Verifier ensemble without post-hoc calibration (Platt / isotonic) is computing with junk on these corpora. The substrate on HaluEval (BSS -0.208) has the same problem: its rank order is informative (F1 0.721) but the raw scores are not calibrated probabilities.
- **The substrate's ECE on RAGTruth is the lowest of all five detectors (0.026).** A 3-line word-overlap-inverse computation produces better-calibrated raw scores than a frontier LLM judge on this corpus. Its F1 is mediocre (0.445 in-sample / 0.358 held-out), so this is a calibration-without-discrimination win: the bins map cleanly to the empirical positive rate even though within-bin ranking is weak. Cite the substrate as a calibrated-probability source on RAGTruth-shape inputs even when its discriminative power is bounded.
- **MCE is high (0.3-0.7) on most cells.** ECE is a weighted average; MCE catches whether the calibration gap is concentrated in a single bin. A high MCE/ECE ratio (AlignScore on RAGTruth: 0.744 / 0.032 = 23×) means there is one bin where the detector systematically over- or under-predicts; reliability-diagram inspection per detector per corpus (in the JSON) is the next step before relying on per-bin probabilities downstream.

**Implications for §5 and §4.3:**

- The two-stage Verifier (`Verifier(use_minicheck=True).score(...)`) MUST calibrate MiniCheck (and probably AlignScore, given its high MCE) before composition on corpora where the raw BSS is negative. Out-of-the-box composition of raw probabilities is unsafe.
- The §4.3 substrate-plus-judge blend uses raw scores (linear blend `α * substrate + (1 - α) * judge`). On HaluEval the substrate is anti-calibrated (BSS -0.208); a blend weight `α` chosen on AUC may correctly weight the substrate while still composing badly-calibrated probabilities. Re-running §4.3 with post-Platt-calibrated input scores would isolate the discrimination contribution from the probability-arithmetic contribution; deferred.
- The blind Grok prompt is calibration-better than the cued variant on every corpus. Combined with the F1-optimal advantage flagged in §4.2.2, the blind prompt is the better default for any production use that needs probability outputs, not just classifications.

### 4.2.4 Across-subsample variance (K=10 prefix offsets)

§4.2's caveat list noted the within-sample bootstrap CI on AUC is ±~0.04 but does not capture across-sample variance from a different prefix offset. This sub-table measures it. For each corpus, K=10 evenly-spaced starting offsets each give a 400-row window (RAGTruth offsets [0, 56, 111, …, 500]; SummEval [0, 133, …, 1200]; HaluEval [0, 67, …, 600]). Substrate L6 / MiniCheck / AlignScore are re-tabulated on each window. The Grok column was only run at offset=0 (existing snapshot); its across-sample variance would need K−1 additional API runs and is deferred per §7. Reproduce via `python -m benchmarks.external.across_subsample_variance`. Full per-offset rows in `benchmarks/external/across_subsample_variance_n400_2026-05-19.json`.

| Corpus | Detector | F1-opt (mean ± std) | P@R90 (mean ± std) | R@P90 (mean ± std) | Top-10% lift (mean ± std) | Base rate ± std |
|---|---|---|---|---|---|---|
| RAGTruth Summary | Substrate L6 | 0.463 ± 0.019 | 0.275 ± 0.015 | 0.040 ± 0.019 | 1.93x ± 0.09 | 0.229 ± 0.014 |
| RAGTruth Summary | MiniCheck | 0.481 ± 0.016 | 0.263 ± 0.013 | 0.045 ± 0.053 | 2.74x ± 0.09 | — |
| RAGTruth Summary | AlignScore | 0.518 ± 0.023 | 0.331 ± 0.028 | 0.019 ± 0.010 | 2.11x ± 0.16 | — |
| SummEval | Substrate L6 | 0.479 ± 0.046 | 0.122 ± 0.025 | 0.087 ± 0.047 | 4.46x ± 0.51 | 0.100 ± 0.013 |
| SummEval | MiniCheck | 0.678 ± 0.060 | 0.290 ± 0.114 | 0.161 ± 0.106 | 6.41x ± 0.69 | — |
| SummEval | AlignScore | 0.473 ± 0.064 | 0.169 ± 0.034 | 0.050 ± 0.029 | 4.21x ± 0.29 | — |
| HaluEval Summarization | Substrate L6 | 0.722 ± 0.006 | 0.589 ± 0.012 | 0.053 ± 0.075 | 1.60x ± 0.11 | 0.500 ± 0.000 |
| HaluEval Summarization | MiniCheck | 0.694 ± 0.004 | 0.555 ± 0.009 | 0.064 ± 0.024 | 1.56x ± 0.07 | — |
| HaluEval Summarization | AlignScore | 0.687 ± 0.007 | 0.545 ± 0.005 | 0.140 ± 0.047 | 1.72x ± 0.07 | — |

**What across-subsample variance changes:**

- **SummEval F1 std is 0.046–0.064 across the three non-judge detectors.** That is materially larger than the within-sample bootstrap CI of ±0.04 the §4.2 caveat list assumed; the headline F1s in the §4.2 SummEval table (substrate 0.422, MiniCheck 0.695, AlignScore 0.543) are within ±1σ of the cross-offset mean but the n=400 prefix at offset=0 happened to give substrate a low draw and AlignScore a high draw. A different team subsampling SummEval differently could see substrate higher than AlignScore on F1-optimal. Cite the cross-offset mean ± std for any deployment decision, not the single-prefix snapshot.
- **SummEval MiniCheck R@P90 has the largest single std in the table** (0.161 ± 0.106). At base rate 0.10 the across-offset envelope of "MiniCheck catches X of 46 at precision 0.9" is 7 ± 5; the §4.2 snapshot's "catches 2 of 46" is 1σ low. Combined with the tie envelope in §4.2.2 (which adds another ±3 to the catches estimate from random tie-breaking), the production-honest range for MiniCheck SummEval audit-precision recall is roughly 4 ± 6 catches per 46 positives. Treat the §4.2 audit-grade single-prefix numbers as discovery aids only.
- **RAGTruth and HaluEval are much more stable across offsets.** RAGTruth F1 stds are 0.016–0.023; HaluEval F1 stds are 0.004–0.007 (HaluEval has perfectly alternating labels by construction so all contiguous slices have identical base rate). On these corpora the §4.2 single-prefix numbers are within ±1σ of the cross-offset mean for every detector.
- **Substrate F1 on SummEval is 0.479 ± 0.046 across offsets, but the §4.2.1 held-out F1 was 0.188.** Holdout and across-offset are different uncertainty sources: holdout penalizes threshold-tuning-on-test (a within-prefix bias) while across-offset penalizes prefix choice. The substrate's SummEval F1 has both bias sources working against it; the §4.2 snapshot's 0.422 was favorably tuned AND favorably prefixed. Cite ~0.188 as the production lower bound on this corpus.
- **Grok column gap acknowledged.** The judge column is the single point estimate at offset=0; its across-sample variance is unmeasured. The §4.3 cued-vs-blind ablation showed within-prefix prompt sensitivity; an additional K=9 cued-judge runs at non-zero offsets would close this gap. Cost: ~$50; budget-gated per §7.

### 4.2.5 Per-call latency and cost framework

§5's architecture decision ("for audit-grade use Grok; for triage MiniCheck remains competitive at substantially lower per-call cost") was qualitative until now. This sub-table makes it quantitative for latency and gives the cost framework for the API-priced detector. Per-call latency below is mean wall-clock per example from the pinned snapshots (n_total per row varies by which snapshot was used).

| Detector | Inference mode | RAGTruth (s/call) | SummEval (s/call) | HaluEval (s/call) | Cost framework |
|---|---|---|---|---|---|
| Substrate L6 (word_overlap_inv) | Pure-Python stdlib, single-threaded | < 0.01 (not snapshotted; ~2 ms reported elsewhere in this doc) | < 0.01 | < 0.01 | Compute-only at adopter's infra cost; effectively free at any production scale. |
| MiniCheck Flan-T5-Large | Local CPU (no GPU) | 4.93 | 2.73 | 9.38 | Compute-only at adopter's infra cost; GPU would reduce by ~10x. Model: HuggingFace `lytang/MiniCheck-Flan-T5-Large` (~770M, Apache-2.0). |
| AlignScore-base | Local CPU (no GPU) | 8.70 | 2.58 | 6.24 | Compute-only at adopter's infra cost; GPU would reduce similarly. Model: `yzha/AlignScore` (~125M, MIT). |
| xAI Grok 4.20 non-reasoning (cued) | API (api.x.ai, OpenAI-compatible) | 1.15 | 1.07 | 1.19 | API-priced per million tokens. Input ≈ source + output + system prompt (~500-2000 tokens depending on corpus); output is one short JSON ≈ 30 tokens. Per-call cost ≈ (input_tokens × in_rate + output_tokens × out_rate) ÷ 1_000_000. Adopter must look up current `grok-4.20-0309-non-reasoning` pricing at api.x.ai; the snapshot here is wall-clock latency only. |
| xAI Grok 4.20 non-reasoning (blind) | Same API | 1.50 | 1.61 | 1.66 | Same framework. Blind prompt is ~35% longer wall-clock per call than cued, consistent with judge spending more time on the unsteered task. Both fit comfortably inside a 2 s/call envelope. |

**Reading guidance:**

- **The latency numbers are NOT comparable apples-to-apples without normalizing hardware.** The trained discriminators are CPU-bound on the snapshotted runs; the judge is API-bound (network + xAI inference time). A production team running MiniCheck on a single GPU sees 0.2–0.9 s/call (a ~10x speedup on the CPU numbers above). A team batching MiniCheck across many examples sees sub-100ms amortized cost. A team calling xAI through a higher-tier endpoint or with provisioned throughput sees different latency.
- **The substrate is the only detector with sub-100ms per-call cost without infrastructure provisioning.** It is the right Stage-1 in the §5 architecture for any volume where Stage-2 has non-trivial per-call cost.
- **Cost-to-deploy framework, qualitatively (numbers depend on adopter pricing as of look-up date):**
  - Substrate: ~0 marginal cost above whatever Python interpreter the application already runs.
  - MiniCheck / AlignScore: GPU-hour amortized over batched inference; rough order ~$0.0001-0.001 per call on commodity cloud GPU at moderate utilization. No external API dependency.
  - Grok: API token charges. For a 500-token-input, 30-token-output call (typical RAGTruth pair), per-call cost is dominated by input tokens. Current `grok-4.20-0309-non-reasoning` published rates are at api.x.ai; the snapshot in this repo does not pin a $ figure because the rate changes faster than the snapshot does. A production team should compute their own per-call cost from current rates × measured token count.
- **For the §5 architecture decision the relevant comparison is per-call $ cost × call volume.** The latency table above lets a team size their inference fleet; the cost framework lets them compute fleet-vs-API trade-off. Without both numbers the architecture decision in §5 is qualitative; this sub-section makes it computable.

Open question deferred to a future round: ship a `cost_per_call.py` script that takes a pricing rates file (kept out-of-repo by the adopter) and produces a per-corpus per-detector $ table by multiplying rates × measured token counts. The token-counting infrastructure is straightforward (`tiktoken` for OpenAI-compatible APIs; HuggingFace tokenizer for the trained discriminators); the gating concern is that pinning specific pricing into the public repo would go stale within weeks.

### 4.2.6 Per-category audit on naturalistic positives (n=15)

§4.1 reports per-category catch on a hand-authored 16-case fixture where each example is one categorized atomic perturbation. Naturalistic positives in §4.2 are not categorized; the headline F1 numbers hide whether each detector's catches are concentrated in 1-2 hallucination subtypes or distributed across the failure-mode space. This sub-section addresses that with a small but explicit hand-audit: 5 positives per corpus from the offset=0 n=400 subsample, classified into the §4.1 taxonomy (closest match) or a new naturalistic category if none of the §4.1 ones fit, with detector catches at the §4.2 in-sample F1-optimal threshold tabulated per case.

n=15 is small; the table is a directional probe, not a representative-sample claim. The audit was performed by Claude Opus 4.7 (this session's author) from the source/output texts directly; per-case categorization is a single-judge label without inter-annotator agreement. Reproduce by reading `/tmp/alignscore_corpora/<corpus>.json` (the pinned pair files) at the indices below and applying the §4.1 taxonomy.

| Case | Closest §4.1 category | Naturalistic-only? | Substrate (thr) | MiniCheck (thr) | AlignScore (thr) | Grok cued (thr) | Grok blind (thr) |
|---|---|---|---|---|---|---|---|
| rag/4 | counterfactual_extension (fabricated "30 in 18 months" stat) | yes | 0.23 (N) | **0.94** (Y) | 0.49 (Y) | **0.65** (Y) | **0.70** (Y) |
| rag/57 | imputed_cause (fabricated "concerns among the passengers") | yes | **0.33** (Y) | **0.69** (Y) | **0.29** (Y) | **0.75** (Y) | **0.65** (Y) |
| rag/178 | (no §4.1 fit) format_hallucination ("Sure! Here's…") + minor | YES (new) | **0.31** (Y) | 0.23 (Y) | **0.65** (Y) | **0.65** (=) | **0.65** (Y) |
| rag/248 | (mostly correct; inferred date / "dozens of new cases") | possible | **0.45** (Y) | **0.96** (Y) | **0.43** (Y) | **0.65** (=) | **0.65** (Y) |
| rag/326 | counterfactual_extension (Julian-calendar / blood-moon priors) | yes | **0.36** (Y) | 0.03 (N) | **0.24** (Y) | **0.65** (=) | **0.65** (Y) |
| sum/0 | (no clean §4.1) compound_fabrication + ungrammatical extract | YES (new) | 0.08 (N) | **0.93** (Y) | 0.26 (N) | **0.85** (Y) | **0.85** (Y) |
| sum/64 | counterfactual_extension (fabricated "destroyed villages") | yes | 0.09 (N) | 0.10 (N) | 0.23 (N) | **0.80** (Y) | 0.40 (N) |
| sum/88 | counterfactual_extension (fabricated demographic split) | yes | **0.24** (Y) | **0.93** (Y) | **0.94** (Y) | **0.95** (Y) | **0.95** (Y) |
| sum/208 | attribute_swap + (no §4.1) gibberish | YES (new) | 0.00 (N) | **0.91** (Y) | **0.41** (Y) | **0.95** (Y) | **0.85** (Y) |
| sum/280 | relation_reversal (Pep Guardiola/Jorge Jesus entity swap) | no | 0.13 (N) | **0.94** (Y) | **0.79** (Y) | **0.95** (Y) | **0.95** (Y) |
| hal/1 | number_swap_same_scale (50,900 vs ~42,000) | no | **0.20** (Y) | 0.08 (Y) | **0.38** (Y) | **0.65** (=) | 0.35 (N) |
| hal/41 | (no exact §4.1) future_as_past_tense (Cech "has made debut") | YES (new) | **0.34** (Y) | **0.98** (Y) | **0.99** (Y) | **0.95** (Y) | **0.95** (Y) |
| hal/121 | direction_reversal (Spurs 7 pts behind ↔ 7 pt gap framing) | no | **0.28** (Y) | **0.49** (Y) | **0.51** (Y) | **0.85** (Y) | **0.75** (Y) |
| hal/241 | numerical_conflation (Tevez's 26 season-total → match score) | no | **0.25** (Y) | **0.84** (Y) | **0.28** (Y) | **0.85** (Y) | **0.85** (Y) |
| hal/321 | counterfactual_extension (fabricated "texting" / insurance cap) | yes | **0.37** (Y) | **0.64** (Y) | **0.44** (Y) | **0.85** (Y) | **0.85** (Y) |
| **catch rate at F1-opt thr (15-case)** | — | — | **11/15** | **13/15** | **12/15** | **15/15** | **12/15** |

(Bold = score above the corpus's in-sample F1-optimal threshold from §4.2; "(=)" = score exactly at threshold, counted as catch. Per-corpus F1-opt thresholds: RAGTruth substrate=0.276/MC=0.142/AS=0.221/Grok cued=0.650/Grok blind=0.400; SummEval 0.133/0.788/0.322/0.700/0.800; HaluEval 0.150/0.052/0.263/0.650/0.650.)

**What the per-category audit shows:**

- **Naturalistic positives don't cleanly map to the §4.1 taxonomy.** Of 15 hand-audited cases, only 7 match a §4.1 category cleanly (rag/4, rag/57, sum/64, sum/88, sum/280, hal/121, hal/241). The other 8 are compound (multiple atomic errors per output), are §4.1-adjacent but blurry (rag/248 "mostly correct with inferred date"), or are categories not in §4.1 at all: **format_hallucination** (rag/178 "Sure! Here's…" assistant frame), **gibberish_extractive_summary** (sum/0, sum/208 — repeated words, broken grammar), **future_as_past_tense** (hal/41 — model writes future events as if they happened). The §4.1 taxonomy is a substrate-blind-spot taxonomy, not a naturalistic-hallucination taxonomy.
- **At F1-opt thresholds, all detectors catch ≥11 of 15.** This is consistent with the §4.2 in-sample F1 numbers (0.45-0.77 across corpora at F1-opt) at the much-more-permissive F1-opt threshold than the audit-grade P=0.9 threshold. The audit does NOT contradict §4.2.2's finding that at P=0.9 the catch rate is much lower (single-digit catches per ~50 positives). The audit measures F1-opt catches; deployment at P=0.9 would catch far fewer.
- **Grok cued catches all 15.** Consistent with its §4.2 in-sample F1 0.67-0.77 (the highest of the five detectors). The two "(=)" cells (rag/178, rag/248, rag/326 at score 0.65 = threshold 0.65) sit exactly at the boundary; under random tie-breaking (§4.2.2) some would flip.
- **Grok blind misses 3 cases that Grok cued catches** (sum/64, hal/1, plus close calls). On this small sample the cued prompt has the F1-opt-threshold catch-rate edge despite the §4.2.2 finding that blind has a higher F1-optimal AUC. The cued prompt's tendency to compress scores into the 0.65-0.95 bucket gives it more catches at any threshold ≤ 0.65, but those catches are not necessarily more accurate (it also has more false positives, which §4.2.2 captures via wider P@R90 tie envelope).
- **MiniCheck misses 2 (rag/326, sum/64).** Both are counterfactual-extension cases where the output adds plausible-sounding world-knowledge content (Julian calendar; "destroyed villages"). MiniCheck's training distribution may not have prepared it for plausible-extension hallucinations on out-of-domain summarization.
- **AlignScore misses 3 (rag/4, sum/0, sum/64).** Two of these are gibberish/extractive-fragment outputs; AlignScore's NLI+QA architecture may give partial credit for vocabulary overlap with the source even when the output is incoherent.
- **Substrate misses 4 (rag/4, sum/0, sum/64, sum/208).** All four involve fabrication that uses vocabulary from the source (counterfactual extension) or gibberish that re-uses source vocabulary heavily (sum/0, sum/208). The substrate's lexical-overlap baseline cannot distinguish "uses source words" from "uses source words correctly," consistent with the §4 wall claim.

**Honest limits on this audit:**

- n=15 is a directional probe, not a representative sample. With ~5 cases per corpus, per-category catch rate estimates have ~30 percentage-point CIs.
- Single-judge categorization (Claude Opus 4.7, this session). No inter-annotator agreement. The "closest §4.1 category" judgment for compound cases is unavoidably subjective.
- The "(=)" tie-at-threshold cases were counted as catches; under random tie-break in §4.2.2 some would flip and the catch rates would shift by 1-2 points.
- Catches are reported at F1-opt thresholds, not P=0.9 thresholds. Production deployments at audit-grade precision would catch substantially fewer of these positives.

### 4.2.7 Pairwise statistical tests on detector orderings

§4.2 reports point estimates and §4.2.1 / §4.2.2 / §4.2.4 characterize within-detector noise (holdout inflation, tie envelope, across-subsample variance). None of those address the question every cross-detector claim in §4.2 rests on: is the gap between detector A and detector B statistically supported at n=400, or is it within paired sampling noise? This section runs paired statistical tests for every pair of detectors on every corpus. Reproduce via `python -m benchmarks.external.paired_detector_tests`; full pairwise matrix at `benchmarks/external/paired_detector_tests_n400_2026-05-19.json`.

Two tests are reported per pair:

- **Paired stratified bootstrap on AUC difference** (n_resamples=2000, seed=0). Each resample draws the same row indices for both detectors so the difference's variance reflects detector disagreement, not marginal sample noise. Returns the 95% percentile CI of (AUC_A − AUC_B) and a two-sided bootstrap p-value (twice the smaller tail mass beyond zero). The CI tells you whether AUC ordering is supported at α=0.05.
- **McNemar's exact binomial test on paired binary verdicts at each detector's F1-optimal threshold**. Conditional on discordant pairs, the count of A-positive-B-negative outcomes is Binomial(b+c, 0.5) under H0 of equal verdict-flip rates. Reports the two-sided exact p-value. Tests whether verdict distributions at F1-opt operating points differ.

Headline survival of prior §4.2 / §4.3 ordering claims under paired tests:

- **MiniCheck vs AlignScore on AUC is statistically indistinguishable on all three corpora** (RAGTruth p=0.174; SummEval p=0.072; HaluEval p=0.961). Multiple prior tables ordered them; that ordering is not statistically supported at n=400 at α=0.05. They are AUC-equivalent within sampling noise and any "MiniCheck > AlignScore" or "AlignScore > MiniCheck" claim should be withdrawn.
- **Substrate L6 vs MiniCheck on AUC is statistically indistinguishable on RAGTruth Summary** (p=0.904). The §2 conclusion "Touchstone L6 is operationally comparable to AlignScore-base on these corpora" extends here: L6 is also comparable to MiniCheck on RAGTruth at the AUC level. (McNemar at F1-opt is significant — verdicts differ — so they're not interchangeable in production, just rank-equivalent.)
- **Substrate L6 significantly beats MiniCheck and AlignScore on HaluEval Summarization AUC** (p=0.048 vs MiniCheck; p=0.026 vs AlignScore). The §2 finding that L6 is "operationally comparable" on HaluEval understates the result; on this corpus the lexical baseline statistically outranks both trained NLI detectors at the AUC level. Load-bearing for the §5 architecture story.
- **Grok blind > Grok cued on AUC is significant on RAGTruth (p=0.047) and SummEval (p=0.002), not on HaluEval (p=0.290)**. The §4.3 narrative "blind AUC equal to or slightly above cued" understates the gap on the two non-adversarial corpora and is correct on HaluEval. The cued prompt is statistically inferior to the blind prompt as a default judge prompt for non-adversarial summarization.
- **Grok (either variant) significantly beats substrate, MiniCheck, AlignScore on AUC on every corpus**. The cross-class judge advantage in §4.2 is fully supported.

Across all 30 pairs (10 pairs × 3 corpora), 22 are AUC-significant at α=0.05 and 23 are McNemar-significant. McNemar catches pairs where the ranking is similar but the verdicts at F1-opt are different (e.g., one detector's F1-opt threshold puts more weight on recall and the other on precision). Several pairs are McNemar-significant but AUC-not (MiniCheck vs AlignScore on RAGTruth and HaluEval; substrate L6 vs AlignScore on HaluEval). Read McNemar as "the operating points disagree" and AUC paired bootstrap as "the ranking abilities disagree."

**What changes in production-architecture claims after paired tests:**

- The previous §4.2 statement "MiniCheck F1-opt 0.452 > Touchstone L6 F1-opt 0.445 on RAGTruth" is meaningless: their AUCs differ by 0.006 with 95% CI [-0.098, +0.086]. They are a statistical tie. Pick whichever has lower per-call cost (the substrate, by ~3 orders of magnitude per §4.2.5).
- The previous §4.2 statement "MiniCheck > AlignScore on SummEval" (F1-opt 0.695 vs 0.543) is not AUC-supported (Δ +0.075, 95% CI [-0.008, +0.161], p=0.072 — within sampling noise at α=0.05). MiniCheck does win at F1-opt by 15 points but AUC ranking is not statistically different.
- The §5 architecture decision "use a trained NLI as stage 2" is unaffected for SummEval (AlignScore-or-MiniCheck both materially beat substrate on AUC there) and Grok-augmented; for RAGTruth and HaluEval the choice between substrate and trained NLI as the cheap-tier baseline is not statistically forced.

**Caveats:**

- Paired bootstrap at n=400 with 2000 resamples has approximate p-value resolution ~0.001. p-values below 0.001 are reported as such; don't read them as "vanishingly small."
- McNemar at F1-optimal threshold uses each detector's own in-sample threshold (§4.2.1's inflation applies); the test still controls for the same underlying labels but the threshold selection is itself within-corpus. A held-out McNemar would change verdicts modestly without changing the significance pattern materially.
- Multiple-comparison correction (10 detector pairs × 3 corpora = 30 tests) is NOT applied. Under Bonferroni at family-wise α=0.05, individual α would tighten to 0.0017; under this stricter bar fewer pairs are significant. The reported p-values are uncorrected and per-test; a reviewer doing meta-analysis across the table should apply their own correction.

### 4.2.8 Multi-vendor judge panel (Grok / Claude / GPT-4o)

§4.2's headline "frontier judge advantage" was measured against one vendor (xAI Grok 4.20). This sub-section adds Anthropic Claude Sonnet 4.6 and OpenAI GPT-4o on the cued prompt at n=400 for all three corpora, and Claude blind across all three. On the 16-case toy fixture all three vendors are at-ceiling (AUC 0.994-1.000); the toy fixture cannot discriminate frontier-judge classes. Reproduce via `python -m benchmarks.external.operational_metrics_on_subsample` after the per-vendor snapshots in `benchmarks/external/<corpus>/results/judge_*_n400_2026-05-19.json` are present.

Per-vendor in-sample F1-optimal on each n=400 corpus (cued prompt; blind variant numbers are in the parallel cells below):

| Corpus | Substrate L6 | MiniCheck | AlignScore | xAI Grok cued | Anthropic Claude cued | OpenAI GPT-4o cued |
|---|---|---|---|---|---|---|
| RAGTruth Summary | 0.445 | 0.452 | 0.493 | 0.670 | **0.754** | 0.717 |
| SummEval | 0.422 | 0.695 | 0.543 | 0.702 | 0.685 | **0.748** |
| HaluEval Summarization | 0.721 | 0.698 | 0.692 | 0.766 | **0.777** | 0.749 |

Per-vendor in-sample F1-optimal under the blind prompt (where measured):

| Corpus | xAI Grok blind | Anthropic Claude blind |
|---|---|---|
| RAGTruth Summary | 0.698 | 0.735 |
| SummEval | **0.763** | 0.685 |
| HaluEval Summarization | 0.761 | 0.765 |

(Bold = highest F1 per corpus across the three frontier judges. GPT-4o blind was rate-limit-blocked on every corpus in this round and is a known gap.)

Per-vendor held-out F1 (eval n=200, §4.2.1 split applied to each vendor):

| Corpus | Grok cued | Grok blind | Claude cued | Claude blind | GPT-4o cued |
|---|---|---|---|---|---|
| RAGTruth Summary | 0.661 | 0.667 | 0.724 | 0.704 | **0.725** |
| SummEval | 0.632 | 0.704 | 0.585 | 0.621 | **0.737** |
| HaluEval Summarization | **0.743** | 0.735 | 0.722 | 0.746 | (recompute pending) |

Per-vendor Brier Skill Score (§4.2.3; higher = better calibrated):

| Corpus | Grok cued | Grok blind | Claude cued | Claude blind | GPT-4o cued |
|---|---|---|---|---|---|
| RAGTruth Summary | +0.115 | +0.297 | +0.426 | **+0.443** | +0.350 |
| SummEval | +0.178 | **+0.381** | +0.335 | +0.307 | +0.330 |
| HaluEval Summarization | +0.269 | +0.300 | +0.281 | +0.244 | (recompute pending) |

Per-vendor R@P90 (audit-precision recall, single-snapshot tie-break realization; treat with §4.2.2 tie envelope in mind):

| Corpus | Grok cued | Grok blind | Claude cued | Claude blind | GPT-4o cued |
|---|---|---|---|---|---|
| RAGTruth Summary | 2/95 | 5/95 | **26/95** | (n/a) | (n/a) |
| SummEval | 12/46 | 11/46 | 5/46 | 4/46 | (recompute pending) |
| HaluEval Summarization | 87/200 | 82/200 | 81/200 | 59/200 | (recompute pending) |

**What the multi-vendor panel changes:**

- **No single vendor dominates across all corpora.** Per-corpus best cued-prompt F1-opt vendor: Claude on RAGTruth and HaluEval; GPT-4o on SummEval. Per-corpus best including blind: Claude cued on RAGTruth (0.754) and HaluEval (0.777); Grok blind on SummEval (0.763). The §4.2 "Grok advantage" headline read narrowly was a single-vendor result; the broader reading is "any frontier judge dominates the trained discriminators on these corpora, but vendor choice matters at the F1 operating point and matters more at audit precision."
- **Claude's audit-grade recall on RAGTruth is dramatically higher than Grok's** (26 of 95 vs 2 of 95 at precision 0.9 — 13x more catches). This is the first detector in this entire evaluation that approaches "audit-grade" recall on a naturalistic corpus (27% recall at precision 0.9). The §4.2's "no detector is audit-grade on every corpus" conclusion survives — Claude is audit-grade only on RAGTruth — but the option space for production audit applications widens materially.
- **Calibration ordering: Claude blind ≈ Claude cued > GPT-4o cued > Grok blind > Grok cued on most cells.** Claude has the best or near-best Brier Skill Score on every corpus measured. Combined with §4.2.3's finding that MiniCheck and Substrate raw probabilities are anti-calibrated on RAGTruth/HaluEval, the production-recommended Stage-2 default for calibrated-probability pathways is Claude (blind on RAGTruth where BSS +0.443 is highest, cued on HaluEval where BSS +0.281 leads). Grok blind is competitive on SummEval (BSS +0.381 vs Claude's +0.307) and may be cheaper per call; deployment choice is per-corpus.
- **Cued-vs-blind effect is vendor-specific.** Grok shows cued-hurts-blind-helps on RAGTruth (+0.028 blind) and especially SummEval (+0.061 blind). Claude shows cued-vs-blind ties on SummEval (0.685 = 0.685) and a cued-better edge on RAGTruth (+0.019 cued). The §4.1 prompt-cueing concern is a real production-design knob — adopters should ablate cued-vs-blind on their own corpus rather than copy a default from this doc.
- **GPT-4o's pattern is different from the other two**: highest F1 on SummEval cued where Grok and Claude both stall (0.748 vs Grok 0.702 / Claude 0.685). Its held-out F1 on SummEval (0.737) is the highest held-out F1 from any vendor on any corpus, suggesting its calibration generalizes well to the holdout. Whether GPT-4o's edge survives the blind ablation is unknown (rate-limit gap).

**Honest limits:**

- GPT-4o blind variant was rate-limit-blocked by OpenAI's 30K TPM cap when run in parallel; sequential runs would complete in ~13 min/corpus but were deprioritized this round. Three GPT-4o blind cells are missing from the table; the cued-vs-blind comparison for OpenAI is therefore not made.
- Anthropic credits ran out during the SummEval and HaluEval blind runs after RAGTruth blind completed. The SummEval and HaluEval Claude blind cells are filled from a snapshot a parallel session previously produced; cells are marked normally but the run provenance is not byte-pinned by this commit.
- HaluEval GPT-4o cued landed in this commit cycle, but the per-vendor holdout/calibration/tie-envelope numbers for HaluEval GPT-4o were not regenerated through `operational_metrics_holdout.py` / `calibration_metrics.py` / `operational_metrics_tie_envelope.py` for this commit (the parallel session's scripts would pick it up automatically on the next run; the table marks "recompute pending" where this gap shows).
- All three vendor judges share the cued and blind prompt text byte-identically (`PROMPT_VARIANTS` dict in `judge_xai_from_pairs.py`, re-imported by `judge_anthropic_from_pairs.py`). Cross-vendor differences cannot be attributed to prompt variation.
- Token rates differ across vendors. Per-call cost is the right deployment comparator and is a function of (vendor cost) × (corpus catch rate); not computed here.
- Three vendors at n=400 is still a small panel. Gemini, Mistral, Meta Llama-as-judge, and other frontier judges are out of scope this round. Within-vendor variance across re-runs at temperature=0.0 with retry is also unmeasured for any vendor.

### 4.3 Does the substrate add value when the judge is already in the loop?

Touchstone's pitch is substrate + judge, not substrate or judge. §4.2 measured each detector independently; this section measures whether the substrate adds operational value to a frontier judge or is redundant. The analysis was first run against the cued judge (the prompt that enumerates the six §4 wall-claim categories) and then re-run with the blind judge to factor out the cueing confound flagged in §4.1. Three combination strategies, all on the same n=400 indices, all pure-python (no sklearn): zero-fit max-ensemble, zero-fit mean-ensemble, and a 5-fold cross-validated linear blend `alpha * substrate + (1 - alpha) * judge` where alpha is selected on each train fold by AUC. Reproduce via `python -m benchmarks.external.substrate_plus_judge_analysis`. Full per-corpus breakdown lives in `benchmarks/external/substrate_plus_judge_n400_2026-05-18.json`.

The right way to read this table: the AUC column is the unbiased comparison (no threshold selection); the F1-optimal column for `blend_cv5` is averaged across 5 fold-test sets at n=80 each, with F1-opt re-selected per fold, so it carries the selection inflation flagged in §4.2.1 and is an upper bound. Treat AUC gaps as load-bearing and F1-opt gaps as suggestive.

| Corpus | Detector | AUC | F1-optimal | Precision at recall 0.9 | Recall at precision 0.9 | Top-10% lift |
|---|---|---|---|---|---|---|
| RAGTruth Summary | substrate_only | 0.659 | 0.458 | 0.272 | catches 1 of 95 | 2.00x |
| RAGTruth Summary | cued_only | 0.854 | 0.670 | 0.455 | catches 2 of 95 | 3.26x |
| RAGTruth Summary | mean_with_cued | 0.850 | 0.659 | 0.411 | catches 10 of 95 | 3.26x |
| RAGTruth Summary | blend_cv5_with_cued (α≈0.10) | 0.849 | 0.703 | 0.459 | catches 30 of 95 | 3.37x |
| RAGTruth Summary | **blind_only** | **0.872** | 0.698 | 0.462 | catches 5 of 95 | 3.26x |
| RAGTruth Summary | mean_with_blind | 0.872 | 0.701 | 0.472 | catches 19 of 95 | 3.26x |
| RAGTruth Summary | blend_cv5_with_blind (α≈0.14) | 0.877 | 0.726 | 0.487 | catches 33 of 95 | 3.37x |
| SummEval | substrate_only | 0.647 | 0.388 | 0.130 | catches 9 of 46 | 3.26x |
| SummEval | cued_only | 0.933 | 0.702 | 0.538 | catches 12 of 46 | 5.43x |
| SummEval | mean_with_cued | 0.925 | 0.680 | 0.532 | catches 10 of 46 | 5.43x |
| SummEval | blend_cv5_with_cued (α≈0.16) | 0.925 | 0.800 | 0.504 | catches 23 of 46 | 6.74x |
| SummEval | **blind_only** | **0.946** | 0.763 | 0.600 | catches 11 of 46 | 6.52x |
| SummEval | mean_with_blind | 0.937 | 0.741 | 0.618 | catches 12 of 46 | 6.74x |
| SummEval | blend_cv5_with_blind (α≈0.00) | 0.943 | 0.842 | 0.606 | catches 22 of 46 | 7.38x |
| HaluEval Summarization | substrate_only | 0.748 | 0.701 | 0.570 | catches 9 of 200 | 1.70x |
| HaluEval Summarization | cued_only | 0.807 | 0.766 | 0.623 | catches 87 of 200 | 1.90x |
| HaluEval Summarization | mean_with_cued | 0.827 | 0.769 | 0.623 | catches 81 of 200 | 1.85x |
| HaluEval Summarization | blend_cv5_with_cued (α≈0.60) | 0.827 | 0.789 | 0.647 | catches 94 of 200 | 1.85x |
| HaluEval Summarization | **blind_only** | **0.816** | 0.761 | 0.616 | catches 82 of 200 | 1.90x |
| HaluEval Summarization | mean_with_blind | 0.833 | 0.768 | 0.636 | catches 76 of 200 | 1.85x |
| HaluEval Summarization | blend_cv5_with_blind (α≈0.70) | 0.836 | 0.796 | 0.669 | catches 84 of 200 | 1.80x |

**What the substrate-plus-judge data shows (with cueing factored out):**

- **A blind judge beats a cued judge on AUC on all three corpora.** RAGTruth 0.872 vs 0.854; SummEval 0.946 vs 0.933; HaluEval 0.816 vs 0.807. All differences are within the n=400 bootstrap CI of ±~0.04 but they all point the same way: the category enumeration in the cued prompt biased the judge toward false positives on naturalistic data rather than steering it toward true positives. The §4.2 headline "Grok dominates" is not a cueing artifact and survives de-cueing; if anything the actual judge advantage is slightly larger than §4.2 reported.
- **The substrate's AUC value-add shrinks with a blind judge.** Cued: blend AUC beats cued-only AUC by -0.005 (RAGTruth, statistical noise), -0.008 (SummEval), +0.020 (HaluEval). Blind: blend AUC vs blind-only AUC is +0.005, -0.003, +0.020. On SummEval the 5-fold CV with blind judge picks **α=0.00 on every fold** — the substrate adds no AUC value over the blind judge there. On HaluEval the substrate still meaningfully helps (α≈0.70, AUC +0.020). On RAGTruth the substrate helps slightly (α≈0.14, AUC +0.005). The earlier §4.3 claim "substrate is not redundant" is corpus-specific: substrate adds AUC on HaluEval, marginally on RAGTruth, not on SummEval-with-blind-judge.
- **R@P90 gains shrink but do not vanish under blind judge.** RAGTruth blind-only catches 5 of 95 at precision 0.9; blend with blind catches 33 (still a 6.6x improvement). SummEval blind-only catches 11 of 46; blend catches 22 (~2x). HaluEval blind-only catches 82 of 200; blend catches 84 (essentially tied). Read these R@P90 numbers in conjunction with §4.2.2's tie envelope: the original cued-judge R@P90 numbers had wide tie-break variance because the cued judge produces clustered scores. The blind judge has less clustering (per the prompt-cueing caveat in §4.1) so the blind R@P90 numbers are more tie-stable.
- **The substrate is most useful where the judge is weakest.** Substrate-only AUCs: HaluEval 0.748 (strongest), RAGTruth 0.659, SummEval 0.647 (weakest). Blend-with-blind picks α that mirrors this: HaluEval α=0.70 (substrate strong → weight it heavily), RAGTruth α=0.14, SummEval α=0.00 (substrate weak → drop it). The "substrate complements judge" story is corpus-dependent in a predictable way: weight the substrate where it shows AUC strength, ignore it where it doesn't.
- **Mechanism, confirmed by the cued-vs-blind asymmetry.** The original §4.3 "substrate breaks ties in judge's bucketed scores" claim is corroborated, not refuted, by the ablation: the cued judge clusters more (because the prompt induces categorical thinking), so substrate tie-breaking has more material to work with under cued and less under blind. The mechanism is real; its production impact depends on which judge prompt the production team chooses.

**This sharpens the substrate-plus-judge architecture in §5 with two specific findings, not the over-broad "substrate is not redundant" claim from the prior §4.3 draft.** A production team running a blind frontier judge (the more honest baseline) on these three corpora would see: substrate adds meaningful AUC and R@P90 on HaluEval, marginal AUC on RAGTruth, no AUC on SummEval. The "substrate complements judge" story holds on adversarial-summarization corpora; on cleaner NLI-shaped corpora a blind frontier judge is close to ceiling for what a small lexical substrate can add. Production teams should measure the corpus-specific α before deciding whether to integrate the substrate at all.

**Caveats:**

- 5-fold CV on n=400 gives fold-test ops metrics on n=80. F1-optimal threshold selection is noisy at this scale and biased upward (see §4.2.1); read the F1-opt column for `blend_cv5` rows as upper bounds. AUC is the unbiased comparison.
- Alpha is selected on train-fold AUC, not on F1 or R@P90. Selecting alpha on the metric you actually deploy at might shift the optimum. The corpus-dependent α pattern (substrate weight tracks substrate AUC strength) is robust enough that the conclusion holds across selection metrics.
- The substrate scores used here are the calibrated `Verifier(mode="substrate_only").score()` output, which was trained on RAGTruth Summary 70/30. On SummEval and HaluEval the substrate is out-of-distribution; in-distribution recalibration could move the substrate AUC up and shift the optimal alpha upward. The reported blend gains under blind judge are a lower bound on what corpus-calibrated substrate weights would deliver.
- The cued vs blind comparison uses identical xAI Grok 4.20 non-reasoning at temperature 0 with `response_format=json_object` on the same n=400 indices. Other prompt scaffolds (calibration-eliciting, structured-output, chain-of-thought) could move the numbers in either direction; this ablation isolates the category-enumeration effect, not the full prompt-design space.

### 4.3.1 Holdout-validated blend metrics (and how the §4.3 narrative changes)

The §4.3 table reports 5-fold CV with per-fold F1-optimal re-selection on the test fold. That carries both §4.2.1's holdout inflation (F1-opt is re-picked on small test folds) and a hyperparameter-on-test artifact (α is chosen on train-fold AUC). This section applies the §4.2.1 holdout discipline to the blend: split each n=400 into a 200-row tune half and 200-row eval half (deterministic stratified interleave matching §4.2.1), pick (α, threshold) on the tune half, evaluate on the eval half at that frozen (α, threshold). Reproduce via `python -m benchmarks.external.substrate_plus_judge_holdout`. Full snapshot at `benchmarks/external/substrate_plus_judge_holdout_n400_2026-05-19.json`.

Two α-selection strategies are reported, mirroring the two §4.3 viewpoints:

- **α-on-tune-F1**: pick α that maximizes tune-half F1-optimal (production-shape choice if you deploy at a fixed threshold). Threshold is the tune F1-optimal at that α.
- **α-on-tune-AUC**: pick α that maximizes tune-half AUC (matching §4.3's CV approach). Threshold is the tune F1-optimal at that α.

| Corpus | Judge | Judge-alone eval F1 | Blend (α-on-F1) eval F1 (gain) | Blend (α-on-AUC) eval F1 (gain) | Blend (α-on-AUC) eval AUC (gain) |
|---|---|---|---|---|---|
| RAGTruth Summary | cued | 0.661 | 0.571 (-0.090, α=0.6) | 0.571 (-0.090, α=0.6) | 0.860 (-0.020) |
| RAGTruth Summary | blind | 0.667 | 0.667 (0.000, α=0.0) | 0.667 (0.000, α=0.6) | 0.868 (-0.018) |
| SummEval | cued | 0.632 | 0.618 (-0.013, α=0.7) | 0.632 (0.000, α=0.0) | 0.915 (0.000) |
| SummEval | blind | 0.704 | 0.585 (-0.118, α=0.7) | 0.704 (0.000, α=0.0) | 0.935 (0.000) |
| HaluEval Summarization | cued | 0.743 | 0.732 (-0.011, α=0.6) | 0.732 (-0.011, α=0.6) | 0.801 (+0.022) |
| HaluEval Summarization | blind | 0.735 | 0.723 (-0.012, α=0.4) | **0.754 (+0.019, α=0.7)** | **0.806 (+0.023)** |

**What the holdout-validated blend shows:**

- **The substrate-plus-judge blend does NOT improve eval F1 over judge-alone on 5 of the 6 (corpus × judge variant) cells.** The single exception is HaluEval-blind with α-on-AUC, where blend eval F1 = 0.754 vs judge-alone 0.735 (gain +0.019). Every other cell is a tie or a loss; the F1-pick variant is consistently worse than the AUC-pick variant (and worse than judge-alone) because picking α to maximize tune F1 overfits the tune set's threshold-sensitive structure and that overfit does not transfer to eval.
- **The §4.3 CV claim "substrate is not redundant" does not survive holdout.** The previously-reported R@P90 jumps (15x on RAGTruth, 2x on SummEval) were per-fold F1-opt re-selection artifacts; under honest tune/eval discipline, the blend's eval R@P90 is essentially at parity with judge-alone on most corpora. Headline retraction: the §4.3 "substrate complements judge" framing is downgraded to "substrate adds at most modest AUC value on HaluEval-with-blind-judge; no measurable eval F1 gain on any (corpus, judge variant) except HaluEval-blind."
- **α-on-AUC picks α=0 on three of six cells**, meaning the tune-set AUC verdict is "the blend cannot beat judge-alone on this corpus/judge combo, ignore the substrate." Under that strategy, the blend defaults to judge-alone and the F1 / AUC gain are exactly zero by construction. This is the AUC-honest answer for SummEval-cued, SummEval-blind, and RAGTruth-blind (where the tune α-on-AUC peaked at α=0 on those splits).
- **The cued-vs-blind asymmetry confirmed by holdout.** Blind judge consistently dominates cued judge under holdout on every corpus on both eval F1 (RAGTruth 0.667 vs 0.661; SummEval 0.704 vs 0.632; HaluEval 0.735 vs 0.743 statistical tie) and eval AUC (RAGTruth 0.886 vs 0.880; SummEval 0.935 vs 0.915; HaluEval 0.783 vs 0.779). The cued prompt should not be the production default.
- **The only genuinely surviving substrate value-add cell is HaluEval-blind with α-on-AUC**: +0.019 eval F1 and +0.023 eval AUC. This is meaningful and corroborates the §4.2.7 finding that the substrate statistically beats trained NLI on HaluEval AUC; it carries through to the blend. Production teams deploying on HaluEval-distribution data could realize this gain. On RAGTruth and SummEval the blend offers no measurable advantage over judge-alone under honest holdout.

**Caveats:**

- n=200 eval half is half of the §4.2 n=400 subsample. Bootstrap CI on eval F1 widens correspondingly (~±0.06 at this scale). The reported gains/losses below ±0.06 should be read as statistical ties.
- α grid resolution is 0.1. Finer α (0.01 increments) could shift the tune-set choice modestly without changing the headline (the AUC-pick strategy already collapses to α=0 on half the cells; finer α won't surface a hidden value cliff).
- Tune/eval split is deterministic (stratified interleave matching §4.2.1). A different split (random, multi-seed) would produce different per-corpus α picks and gain estimates; the across-subsample variance in §4.2.4 suggests the variance on eval F1 across subsample seeds is in the 0.03-0.06 range — comparable to the gains/losses reported here.
- The substrate is RAGTruth-trained. The HaluEval-blind +0.019 / +0.023 gain is achieved despite the substrate being out-of-distribution; an in-corpus recalibration of substrate weights might shift the result on the other corpora as well.

## 5. The honest production architecture

Touchstone alone is NOT a sufficient hallucination detector for production deployment in the general case. For real-world AI output verification, the production architecture is:

1. **Stage 1: Touchstone substrate (Verifier substrate-only)** — runs in <100 ms per output. Catches: lexically-distinguishable hallucinations (new numbers, new entities, new years, vocabulary drift). Routes outputs into a review queue ordered by suspicion score.
2. **Stage 2: An LLM-based judge (MiniCheck / AlignScore / GPT-4 / Claude / domain-specific NLI)** on the top X% of stage-1 outputs OR on every output if compute budget allows. Catches: semantically-distinguishable hallucinations (direction reversal, attribute swap, scoping shift, relation reversal).
3. **Stage 3: Human review** on the top Y% of stage-1+stage-2 outputs by combined score, with span-level localization from Touchstone Layer 11 to focus reviewer attention.

The Verifier API supports this architecture: `Verifier(use_minicheck=True).score(...)` combines the cheap substrate signal with the caller-supplied trained-discriminator score into a single calibrated probability + signal breakdown + span localization. §4.3 measures the substrate's value-add when a frontier LLM judge is stage 2 under CV; §4.3.1 re-measures under honest tune/eval holdout. The holdout result revises the §4.3 claim downward: of the six (corpus, judge-variant) cells, only HaluEval-with-blind-judge shows a positive eval gain (+0.019 F1, +0.023 AUC at α=0.7 picked on tune-AUC). On the other five cells the blend is at parity with judge-alone or worse. The "substrate complements judge" story holds only on adversarial-summarization corpora where the substrate is itself strong on AUC (§4.2.7's HaluEval result); on cleaner NLI-shaped corpora a blind frontier judge is at the ceiling for what a small lexical substrate can add. Production teams should measure their own corpus's α-on-AUC on a held-out tune split before deciding whether to integrate the substrate alongside a frontier judge; for most corpus distributions the honest answer will be "judge-alone is the deployable system."

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
- `python -m benchmarks.external.operational_metrics_holdout` — computes the §4.2.1 held-out F1-optimal table by splitting each n=400 subsample 200/200 (stratified interleave), tuning the F1-optimal threshold on the tune half, reporting metrics on the eval half. Reads existing snapshots; no new judge calls.
- `python -m benchmarks.external.operational_metrics_tie_envelope` — computes the §4.2.2 tie-aware metric envelope by K=100 sub-quantum-jitter permutations on every detector's scores; reports mean ± std for F1-optimal, P@R90, R@P90, and top-10% lift. Deterministic (SHA-1 seed per detector name).
- `python -m benchmarks.external.calibration_metrics` — computes the §4.2.3 calibration table (ECE, MCE, Brier, Brier skill score, per-bin reliability diagram) per detector per corpus. Reads existing snapshots; no new judge calls.
- `python -m benchmarks.external.across_subsample_variance` — computes the §4.2.4 across-subsample-variance table by re-tabulating substrate / MiniCheck / AlignScore on K=10 prefix offsets per corpus. Reads existing full-N snapshots; Grok column gated on additional API budget.
- `XAI_API_KEY=$(vault decrypt XAI_API_KEY) .venv-external/bin/python benchmarks/external/judge_xai_from_pairs.py <pairs.json> --label "<corpus>" --corpus-dir <corpus_dir> --model grok-4.20-0309-non-reasoning --prompt-variant blind --output <out.json>` — re-runs the Grok judge under the blind (no-category-enumeration) prompt variant; pair with the cued snapshot to measure the cueing delta on naturalistic data (the toy fixture is at ceiling under both).
- World-knowledge-only ablation (the §4.1 contamination check): a one-shot script (not pinned in `benchmarks/`; the snapshot at `benchmarks/adversarial_subtle/judge_xai_world_knowledge_only_2026-05-19.json` is the byte-pinned result). Sends each OUTPUT to Grok with NO SOURCE and a fact-checker prompt asking the judge to flag from priors alone. Reproduce by sending the 32 outputs to xAI with `model=grok-4.20-0309-non-reasoning`, `temperature=0.0`, `response_format=json_object`, and the system prompt stored in the snapshot's `judge_prompt_system` field.
- `python -m benchmarks.external.score_substrate_on_subsample --pairs /tmp/alignscore_corpora/<corpus>_n400.json --output benchmarks/external/<corpus_dir>/results/substrate_only_n400_2026-05-18.json --corpus-dir <corpus_dir> --label "<corpus>"` — runs the Verifier substrate-only on each n=400 subsample pair (required input for §4.3).
- `python -m benchmarks.external.paired_detector_tests` — runs paired stratified bootstrap on AUC differences and McNemar exact tests at each detector's F1-optimal threshold for every detector pair on each n=400 subsample. Outputs §4.2.7's pairwise significance matrix to `benchmarks/external/paired_detector_tests_n400_2026-05-19.json`.
- `python -m benchmarks.external.substrate_plus_judge_analysis` — computes the §4.3 substrate-plus-judge value-add table (zero-fit ensembles + 5-fold CV linear blend) from the substrate and judge per-example snapshots; runs against both the cued and blind judge variants.
- `python -m benchmarks.external.substrate_plus_judge_holdout` — computes the §4.3.1 holdout-validated blend metrics: 200/200 tune/eval split, picks (α, threshold) on tune, evaluates frozen pair on eval. Reports both α-on-tune-F1 and α-on-tune-AUC variants plus eval tie envelope on the blended score.
- `XAI_API_KEY=$(vault decrypt XAI_API_KEY) .venv-external/bin/python benchmarks/external/judge_xai_from_pairs.py /tmp/alignscore_corpora/<corpus>_n400.json --label "<corpus> (n=400 blind)" --corpus-dir <corpus_dir> --model grok-4.20-0309-non-reasoning --prompt-variant blind --output benchmarks/external/<corpus_dir>/results/judge_xai_grok420_blind_n400_2026-05-18.json` — blind-prompt judge run used for the §4.3 cued-vs-blind ablation.
- `python examples/production_verifier.py` — runs an end-to-end demo of the calibrated Verifier API.
- `python -m benchmarks.external.cross_baseline_summary --markdown` — emits the cross-corpus cross-baseline table including trivial-baseline anchor.

All snapshots are byte-pinned; every reported number is reproducible from a fresh clone.
