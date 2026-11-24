"""Library demo for the Touchstone Verifier.

The probability orders a review queue. It is not a hallucination
detector, and the result has no confidence interval.

1. **Substrate-only** (no extras, sub-100 ms per pair): the default.
   Verifier AUC on the n=400 subsamples is 0.647 (SummEval), 0.748
   (HaluEval), 0.659 (RAGTruth Summary; 0.677 on the 271 held-out
   rows). The 0.67-0.76 range is raw Layer 6.
2. **Substrate + MiniCheck**: the caller passes MiniCheck's
   supported-probability. MiniCheck alone averages AUC 0.76. This
   combined mode has no published evaluation.
3. **Substrate + MiniCheck + AlignScore**: both probabilities. This
   combined mode has no published evaluation. AlignScore alone
   averages AUC 0.75.
4. **Substrate + a caller-supplied judge**: linear blend,
   ``judge_alpha`` default 0.3 (a substrate-light default, below the
   §4.3.1 tune mean of about 0.375). The 0.78-0.94 range is the
   judge's own AUC. On the holdout the blend was at parity with the
   judge or worse on 5 of 6 Grok cells.

See ``docs/production_readiness.md``.

Run::

    python examples/production_verifier.py
"""

from __future__ import annotations

from clarethium_touchstone import Verifier

SOURCE = (
    "Apple reported Q1 fiscal 2026 revenue of $143 billion. The company's "
    "iPhone segment grew 8% year-over-year. Tim Cook commented on AI "
    "investments during the earnings call. Operating margins reached 32%."
)

FAITHFUL_SUMMARY = (
    "Apple reported Q1 fiscal 2026 revenue of $143 billion, with iPhone "
    "segment growth of 8% and 32% operating margins. CEO Tim Cook "
    "commented on AI investments during the earnings call."
)

HALLUCINATED_SUMMARY = (
    "Apple reported Q1 fiscal 2026 revenue of $185 billion, the company's "
    "highest ever. McKinsey forecasts industry-wide growth of 47% next "
    "quarter. The Federal Reserve will raise rates 75 basis points in "
    "response. Tesla announced a competing AR product for late 2027."
)


def main() -> None:
    verifier = Verifier()

    print("=" * 70)
    print("TOUCHSTONE VERIFIER — production demo")
    print("=" * 70)
    print()
    print("Source:")
    print(f"  {SOURCE}")
    print()

    # The first two demos use substrate-only. The third shows the new
    # substrate_plus_judge mode (mocked judge probability so the demo runs
    # without an API call; in production the caller invokes Grok/Claude/
    # GPT-4o and passes the returned P(hallucinated)).
    demos: list[tuple[str, str, dict[str, float | None]]] = [
        ("Faithful summary, substrate-only", FAITHFUL_SUMMARY, {}),
        ("Hallucinated summary, substrate-only", HALLUCINATED_SUMMARY, {}),
        (
            "Hallucinated summary, substrate + judge (judge_hallucinated_prob=0.92, judge_alpha=0.3)",
            HALLUCINATED_SUMMARY,
            {"judge_hallucinated_prob": 0.92, "judge_alpha": 0.3},
        ),
    ]
    for label, summary, judge_kwargs in demos:
        print("-" * 70)
        print(f"[{label}]")
        print(f"  {summary}")
        print()
        result = verifier.score(summary, source=SOURCE, **judge_kwargs)
        # Two thresholds shown for honesty: 0.5 is the library default but
        # operationally under-flags on the v1.0 corpora (the F1-optimal
        # threshold is 0.07-0.27 there). Adopters MUST tune on their own
        # held-out data; see docs/production_readiness.md §2.
        verdict_default = "FLAG" if result.should_flag(threshold=0.5) else "PASS"
        verdict_tuned = "FLAG" if result.should_flag(threshold=0.2) else "PASS"
        print(f"  prob_hallucinated = {result.prob_hallucinated:.3f}")
        print(f"    at threshold 0.5 (library default):       {verdict_default}")
        print(f"    at threshold 0.2 (F1-optimal-ish on v1.0): {verdict_tuned}")
        print(f"  mode = {result.mode}")
        print()
        print("  Signal breakdown (each row contributes to the logit):")
        for name, contrib in result.signal_breakdown.items():
            print(f"    {name:25s}  {contrib:+.4f}")
        print()
        if result.top_unsupported:
            print("  Top unsupported sentences:")
            for span in result.top_unsupported:
                primary = span.layer11_primary
                markers = f"  [markers: {', '.join(span.p_markers)}]" if span.p_markers else ""
                score = (
                    f"  [grounding={span.grounding_score:.2f}]"
                    if span.grounding_score is not None
                    else ""
                )
                print(f"    {primary}{markers}{score}")
                print(f"       {span.sentence!r}")
        else:
            print("  (no unsupported spans flagged)")
        print()

    print("-" * 70)
    print()
    print("Production deployment guidance (READ docs/production_readiness.md):")
    print()
    print("  • Touchstone substrate-only is STRUCTURALLY BLIND to hallucinations")
    print("    that preserve vocabulary and only change semantic relationships")
    print("    (direction reversal, attribute swap, scoping shift, relation reversal,")
    print("    time-frame shift, imputed cause). On a 16-case stress test, the")
    print("    substrate-only Verifier separated hallucinated from faithful at 50%")
    print("    (chance). It is NOT a standalone production hallucination detector.")
    print()
    print("  • What it IS useful for in production:")
    print("    - Ordering a review queue. Top-10% lift over random review on")
    print("      English news summarization is about 1.7x-3.3x for the Verifier")
    print("      and 1.6x-4.2x for raw Layer 6, depending on corpus.")
    print("    - Drift detection on stable production streams.")
    print("  • What the holdout does not support: blending this score onto a")
    print("    judge. Parity or worse on 5 of 6 Grok cells (production_readiness")
    print("    §4.3.1). Judge-alone is the check. A caller-supplied detector")
    print("    score changes the probability only.")
    print()
    print("  • The default should_flag(threshold=0.5) UNDER-FLAGS for any")
    print("    production deployment. The Verifier's F1-optimal thresholds on")
    print("    the n=400 subsamples are 0.15-0.22. The 0.07-0.27 range is for")
    print("    raw detector scores, not this probability. Tune on held-out data.")
    print()
    print("  • Recalibrate via Verifier.with_calibration() if your input")
    print("    distribution differs from English news summarization.")
    print()


if __name__ == "__main__":
    main()
