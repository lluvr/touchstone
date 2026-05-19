"""Production usage demo for the Touchstone Verifier.

Shows the four operating modes:

1. **Substrate-only** (no extras, sub-100 ms per pair): the default.
   Suitable for drift detection and regression testing; not for
   sole-source audit decisions. Default-calibrated AUC ≈ 0.67-0.76
   on three external summarization corpora.
2. **Substrate + MiniCheck** (caller invokes MiniCheck themselves and
   passes the supported-probability): AUC ≈ 0.76 on RAGTruth Summary
   held-out test split. Adds the MiniCheck cost (~5 s/pair on CPU).
3. **Substrate + MiniCheck + AlignScore**: AUC ≈ 0.77. Adds the
   AlignScore cost (~5 s/pair on CPU) on top of MiniCheck.
4. **Substrate + LLM judge** (caller invokes any frontier judge —
   xAI Grok / Anthropic Claude / OpenAI GPT-4o per §4.2.8 — and
   passes the P(hallucinated) the judge returned). Linear blend
   with ``judge_alpha`` defaulting to ≈ 0.3 (cross-corpus mean of
   the §4.3.1 picked α). Highest AUC of the four modes when the
   judge is competently chosen; deployment cost is one judge call
   per pair (~1-2 s, $.001-.005 per call depending on vendor).

The Verifier is the production-shaped API: one ``score()`` call,
calibrated probability + CI bounds + per-sentence localization. See
``docs/methodology.md`` for the honest empirical envelope these
calibrations deliver on held-out corpora.

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
    print("    - Triage / review-queue prioritization (2-4x lift over random review")
    print("      on English news summarization).")
    print("    - Cheap first-pass filter ahead of an LLM-based judge.")
    print("    - Drift detection on stable production streams.")
    print("    - The lexical half of a two-stage architecture; combine with a")
    print("      trained semantic discriminator via minicheck_supported_prob and/or")
    print("      alignscore_supported_prob, OR a frontier LLM judge via")
    print("      judge_hallucinated_prob (mode auto-selects to substrate_plus_judge;")
    print("      linear blend with judge_alpha defaulting to 0.3 per §4.3.1).")
    print()
    print("  • The default should_flag(threshold=0.5) UNDER-FLAGS for any")
    print("    production deployment. F1-optimal thresholds on v1.0 corpora are")
    print("    0.07-0.27. Tune on your own held-out data.")
    print()
    print("  • Recalibrate via Verifier.with_calibration() if your input")
    print("    distribution differs from English news summarization.")
    print()


if __name__ == "__main__":
    main()
