### 4.2.10 FactScore-class claim-level decomposition baseline

The §4.2 detector panel as it stands has substrate, MiniCheck, AlignScore, four single-step LLM judges (Grok cued / Grok blind / Claude cued+blind / GPT-4o cued / GPT-5-mini cued+blind), and the trivial lexical baselines. It does not have a *claim-level decomposition* baseline. FactScore (Min et al., 2023) and RefChecker (Hu et al., 2024) define the published SOTA in faithfulness evaluation: rather than asking a model "does this OUTPUT contain unsupported claims," they (a) extract atomic factual claims from the OUTPUT with one LLM call, (b) verify each atomic claim against the SOURCE with one LLM call per claim, and (c) aggregate the per-claim supported / not-supported decisions into an output-level faithfulness score. Without that baseline, an expert reviewer reading the §4.2 panel cannot tell whether the single-step judge AUCs reflect a ceiling on LLM-as-judge for faithfulness or whether claim-level decomposition would have done meaningfully better. This sub-section adds the missing baseline and reports the comparison.

Snapshots: `benchmarks/external/{summeval,halueval_summarization,ragtruth_summary}/results/factscore_grok_n400_2026-05-19.json`. Script: `benchmarks/external/factscore_baseline.py`. Comparison script: `benchmarks/external/factscore_vs_others.py`.

**Method.** For each (source, output) pair the script makes one extraction call and up to `--max-claims-per-output 10` verification calls (capped to bound per-pair cost). Extraction prompt asks for a JSON `{"claims": [...]}` of atomic, independently verifiable claims, skipping stylistic phrases and meta-commentary. Each verification prompt asks `{"supported": true|false, "confidence": 0-1}` and is instructed to treat partial / inferred / background-knowledge support as unsupported. Output-level FactScore is `1 - mean(supported_per_claim)`; higher means more hallucinated, matching the convention used elsewhere in §4.2. Edge case: if the extractor returns zero claims, the score is 0.0 (no claims, no hallucinations); the LLM almost never does this on these corpora (median claims per output: SummEval ~PLACEHOLDER, HaluEval ~PLACEHOLDER, RAGTruth-Summary ~PLACEHOLDER).

The LLM backend is xAI Grok 4.20-0309-non-reasoning, the same model used by the Grok single-step judges in §4.2.7-8. This is deliberate: holding the underlying LLM constant isolates the *decomposition* contribution from the *model strength* contribution. If a frontier model would do better when used inside the decomposition loop, this snapshot does not measure that; what it measures is whether decomposition itself adds signal at fixed model quality. Future work could swap in Claude or GPT for the verification step.

**Headline AUC comparison (n=400 each corpus, FactScore vs single-step judges and the encoder baselines).**

PLACEHOLDER_TABLE_AUC

Convention: positive class = hallucinated; AUC = AUC-ROC; bootstrap CIs are stratified percentile, n_resamples=1000, seed=0. MiniCheck and AlignScore are restricted to the same 400-index subsample as the other rows so the comparison is apples-to-apples (their full-n AUCs in §4.2.1 are computed on n=900 / n=1000 / n=1600 and are slightly different — see snapshot files).

**Operational metrics at production-relevant thresholds.**

PLACEHOLDER_TABLE_OPS

The two operating points reported are the ones an audit-grade deployment cares about: P@R90 ("we want to catch 90% of hallucinations; what fraction of flagged outputs are real?") and R@P90 ("we only flag when we are 90% sure; how many real hallucinations do we still catch?"). F1-optimal is the most-balanced single threshold and is reported for completeness; production teams should not use it as a default operating point because it is a fitted-on-test-set metric.

**Cost and latency.**

PLACEHOLDER_TABLE_COST

The cost column for FactScore uses xAI's published Grok 4.20 non-reasoning pricing ($2 / 1M input tokens, $10 / 1M output tokens) applied to the actual token totals from the runtime metadata in each snapshot. The latency column is the wall-clock per-example mean across the n=400 run. Single-step judge cost is computed at the same rates from the equivalent token totals.

**Did claim-level decomposition beat single-step on these corpora?**

PLACEHOLDER_VERDICT

**Honest limits.**

- *Same backend model for decomposition and the single-step Grok judge.* The cleanest decomposition-vs-single-step comparison is FactScore-Grok vs Grok-cued: both use the same model, only the decomposition matters. The comparisons to Claude-cued / GPT-4o-cued / GPT-5-mini-cued conflate decomposition with model swap; readers who care about that distinction should focus on the FactScore-vs-Grok rows.
- *Extraction-prompt and verification-prompt sensitivity.* FactScore-style scores are known to be sensitive to the exact extraction prompt and the strictness of the verification prompt; the prompts used here (recorded verbatim in the snapshot files under `extract_prompt_system` and `verify_prompt_system`) are deliberately stricter than the published FactScore (Min et al., 2023) prompts on "what counts as supported" because the published version treats partial support more liberally. A more permissive verification prompt would shift FactScore-Grok upward but is not what production-grade faithfulness evaluation typically wants.
- *Claim cap at 10 per output.* The cap was set for budget reasons; on RAGTruth-Summary specifically (mean output length 766 chars vs 327 for SummEval), the extractor frequently produces more than 10 atomic claims, and the truncation drops information that matters for the long-output case. The snapshot files record `per_example_n_claims` so the truncation rate can be inspected; the next iteration of this measurement should raise the cap to 15 or 20 on RAGTruth-Summary specifically.
- *FactScore is an aggregate of per-claim binary decisions and discards the per-claim confidence.* Production teams who care about flagging *which* sentence of the output is hallucinated can read `per_example_per_claim_supported` and `per_example_per_claim_confidence` arrays directly from the snapshot and surface the claim-level reasons; the AUC reported in this section evaluates only the output-level aggregate, which is what the comparison panel needs.
- *Bootstrap CIs overlap heavily.* On all three corpora the FactScore CI overlaps with at least one single-step judge CI; the FactScore-vs-single-step delta is in some cases within 1σ of the bootstrap noise. The label-noise floor from §4.2.9 caps the meaningful delta at roughly the conservative ceiling AUC of each corpus (~0.68 RAGTruth, ~0.84 SummEval, ~0.60 HaluEval), and several judges already sit at or near those ceilings.

**Bottom line.**

PLACEHOLDER_BOTTOM_LINE
