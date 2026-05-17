"""Production usage demo for the Touchstone Verifier.

Shows three operating modes:

1. **Substrate-only** (no extras, sub-100 ms per pair): the default.
   Suitable for drift detection and regression testing; not for
   sole-source audit decisions. Default-calibrated AUC ≈ 0.67-0.76
   on three external summarization corpora.
2. **Substrate + MiniCheck** (caller invokes MiniCheck themselves and
   passes the supported-probability): AUC ≈ 0.76 on RAGTruth Summary
   held-out test split. Adds the MiniCheck cost (~5 s/pair on CPU).
3. **Substrate + MiniCheck + AlignScore**: AUC ≈ 0.77. Adds the
   AlignScore cost (~5 s/pair on CPU) on top of MiniCheck.

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

    for label, summary in [
        ("Faithful summary", FAITHFUL_SUMMARY),
        ("Hallucinated summary", HALLUCINATED_SUMMARY),
    ]:
        print("-" * 70)
        print(f"[{label}]")
        print(f"  {summary}")
        print()
        result = verifier.score(summary, source=SOURCE)
        verdict = "FLAG" if result.should_flag(threshold=0.5) else "PASS"
        print(f"  prob_hallucinated = {result.prob_hallucinated:.3f}  ({verdict} at threshold 0.5)")
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
    print("Production deployment guidance:")
    print()
    print("  • Substrate-only mode (this demo) is research-tier signal strength.")
    print("    Default-calibrated AUC ≈ 0.67-0.76 on three external English-news-")
    print("    summarization corpora. Use for: drift detection, regression testing,")
    print("    cheap first-pass filter ahead of an LLM-based judge.")
    print("  • For production hallucination detection: combine with a trained")
    print("    discriminator (MiniCheck, AlignScore, or similar) by invoking the")
    print("    discriminator yourself and passing its supported-probability to")
    print("    score(). Substrate + MiniCheck adds ~0.08 AUC; +AlignScore another")
    print("    ~0.01-0.02. Latency budget: substrate ~50ms, MiniCheck ~5s, both")
    print("    ~10s per pair on CPU.")
    print("  • Recalibrate on your own held-out data if your input distribution")
    print("    differs from English news summarization. Use Verifier.with_calibration().")
    print()


if __name__ == "__main__":
    main()
