"""Hand-crafted adversarial stress test.

The existing external corpora contain mostly obvious hallucinations
(fabricated entities, citations, numeric drift across orders of
magnitude). Real LLM hallucinations in production are often SUBTLE:
number swaps within the same scale, year/quarter shifts, attribute
swaps, conjunction shifts. These are operationally what matters and
are what evade lexical-overlap-based detection most readily.

This script ships 16 hand-crafted (source, faithful, hallucinated)
triples covering the subtle-hallucination categories that real LLM
deployments produce. Each case is small enough to inspect by hand;
the runner reports per-case Verifier scores and a confusion summary
showing how many subtle hallucinations were caught vs missed at the
F1-optimal threshold and the default threshold.

This is NOT a benchmark with bootstrap CIs. It is a sanity check:
does the Verifier handle the kinds of mistakes real LLMs make, or
does it only catch the obvious ones?

Run::

    python -m benchmarks.adversarial_subtle.run
"""

from __future__ import annotations

import json
from pathlib import Path

from clarethium_touchstone import Verifier

# Each case is (category, source, faithful_summary, hallucinated_summary).
# The faithful summary is faithful to source; the hallucinated summary
# contains the subtle error described in the category label. A
# well-behaving verifier should score the hallucinated summary higher
# than the faithful one consistently across all cases.
CASES: list[tuple[str, str, str, str]] = [
    # Category 1: number swap within same scale
    (
        "number_swap_same_scale",
        "Apple reported Q1 fiscal 2026 revenue of $143 billion. Operating margins reached 32%.",
        "Apple reported Q1 fiscal 2026 revenue of $143 billion with operating margins of 32%.",
        "Apple reported Q1 fiscal 2026 revenue of $134 billion with operating margins of 32%.",
    ),
    # Category 2: percentage shift within plausible range
    (
        "percentage_shift_plausible_range",
        "Revenue grew 12% year-over-year to $143 million in Q1.",
        "Revenue grew 12% year-over-year to $143 million in Q1.",
        "Revenue grew 21% year-over-year to $143 million in Q1.",
    ),
    # Category 3: quarter / time-window shift
    (
        "quarter_shift",
        "Apple reported Q1 fiscal 2026 revenue of $143 billion.",
        "Apple reported Q1 fiscal 2026 revenue of $143 billion.",
        "Apple reported Q3 fiscal 2026 revenue of $143 billion.",
    ),
    # Category 4: role / title swap
    (
        "role_title_swap",
        "Apple CEO Tim Cook commented on AI investments during the earnings call.",
        "Apple CEO Tim Cook commented on AI investments during the earnings call.",
        "Apple CFO Tim Cook commented on AI investments during the earnings call.",
    ),
    # Category 5: direction reversal (grew vs declined)
    (
        "direction_reversal",
        "Costs declined 8% in Q1 while headcount grew by 1200 employees.",
        "Costs declined 8% in Q1 while headcount grew by 1200 employees.",
        "Costs grew 8% in Q1 while headcount declined by 1200 employees.",
    ),
    # Category 6: imputed cause (revenue grew DUE TO X vs revenue grew AND X happened)
    (
        "imputed_cause",
        "Revenue grew 12% in Q1. AI investments increased by $5 billion.",
        "Revenue grew 12% in Q1; separately, AI investments increased by $5 billion.",
        "Revenue grew 12% in Q1 due to a $5 billion increase in AI investments.",
    ),
    # Category 7: magnitude shift (million vs billion)
    (
        "magnitude_shift",
        "Revenue grew to $143 million in Q1 fiscal 2026.",
        "Revenue grew to $143 million in Q1 fiscal 2026.",
        "Revenue grew to $143 billion in Q1 fiscal 2026.",
    ),
    # Category 8: false precision (specific number where source is vague)
    (
        "false_precision",
        "Revenue grew significantly in Q1, with strong margins across all segments.",
        "Revenue grew significantly in Q1, with strong margins across all segments.",
        "Revenue grew 47% in Q1, with margins of 33% across all segments.",
    ),
    # Category 9: time-frame shift (this quarter vs last quarter)
    (
        "time_frame_shift",
        "Apple's Q1 fiscal 2026 revenue was $143 billion, up from $120 billion in Q4 fiscal 2025.",
        "Apple's Q1 fiscal 2026 revenue was $143 billion, up from $120 billion in Q4 fiscal 2025.",
        "Apple's Q4 fiscal 2025 revenue was $143 billion, up from $120 billion in Q1 fiscal 2026.",
    ),
    # Category 10: attribute swap (similar attribute, different value)
    (
        "attribute_swap",
        "The iPhone segment grew 8% while Mac segment declined 4%.",
        "iPhone grew 8% in the quarter; Mac declined 4%.",
        "The iPhone segment declined 8% while Mac segment grew 4%.",
    ),
    # Category 11: fabricated affiliation (plausible)
    (
        "fabricated_affiliation",
        "Apple held an investor day on November 15, 2025, with Tim Cook presenting.",
        "Apple's investor day was on November 15, 2025, hosted by Tim Cook.",
        "Apple's investor day was on November 15, 2025, co-hosted by Tim Cook and former CEO Steve Jobs.",
    ),
    # Category 12: scoping shift (segment vs total)
    (
        "scoping_shift",
        "iPhone revenue grew 8% to $65 billion. Total Apple revenue was $143 billion.",
        "iPhone revenue was $65 billion (up 8%); total Apple revenue was $143 billion.",
        "Total Apple revenue grew 8% to $65 billion.",
    ),
    # Category 13: counterfactual extension (predicting beyond source)
    (
        "counterfactual_extension",
        "Apple reported Q1 fiscal 2026 revenue of $143 billion.",
        "Apple reported Q1 fiscal 2026 revenue of $143 billion.",
        "Apple reported Q1 fiscal 2026 revenue of $143 billion and projects Q2 revenue of $155 billion.",
    ),
    # Category 14: numerical conflation (similar numbers from different fields)
    (
        "numerical_conflation",
        "Revenue grew 12% to $143 billion. iPhone segment was 8% of growth.",
        "Revenue grew 12% to $143 billion; iPhone contributed 8% of the growth.",
        "Revenue grew 8% to $143 billion; iPhone contributed 12% of the growth.",
    ),
    # Category 15: subtle entity swap (similar names)
    (
        "subtle_entity_swap",
        "Apple's CFO Luca Maestri discussed Q1 results.",
        "Luca Maestri, Apple's CFO, discussed Q1 results.",
        "Apple's CFO Luca Maestro discussed Q1 results.",
    ),
    # Category 16: relation reversal (X owns Y vs Y owns X)
    (
        "relation_reversal",
        "Apple acquired AI startup Foundation Labs for $400 million.",
        "Apple acquired AI startup Foundation Labs for $400 million in Q1.",
        "AI startup Foundation Labs acquired Apple for $400 million.",
    ),
]


def main() -> None:
    verifier = Verifier()

    results: list[dict] = []
    deltas: list[float] = []
    print(f"{'category':32s} {'faithful':>10s} {'halluc':>10s} {'delta':>10s} {'h>f?':>5s}")
    print("-" * 75)
    n_separated = 0
    for category, source, faithful, hallucinated in CASES:
        faithful_res = verifier.score(faithful, source=source)
        halluc_res = verifier.score(hallucinated, source=source)
        delta = halluc_res.prob_hallucinated - faithful_res.prob_hallucinated
        deltas.append(delta)
        separated = delta > 0
        if separated:
            n_separated += 1
        print(
            f"{category:32s} {faithful_res.prob_hallucinated:>10.3f} "
            f"{halluc_res.prob_hallucinated:>10.3f} {delta:>+10.3f} "
            f"{'YES' if separated else 'NO':>5s}"
        )
        results.append(
            {
                "category": category,
                "source": source,
                "faithful": faithful,
                "hallucinated": hallucinated,
                "faithful_prob": faithful_res.prob_hallucinated,
                "halluc_prob": halluc_res.prob_hallucinated,
                "delta": round(delta, 6),
                "correctly_separated": separated,
                "faithful_top_unsupported": [
                    {
                        "sentence": s.sentence,
                        "primary": s.layer11_primary,
                        "p_markers": s.p_markers,
                    }
                    for s in faithful_res.top_unsupported
                ],
                "halluc_top_unsupported": [
                    {
                        "sentence": s.sentence,
                        "primary": s.layer11_primary,
                        "p_markers": s.p_markers,
                    }
                    for s in halluc_res.top_unsupported
                ],
            }
        )

    print()
    print(
        f"Correctly separated (halluc > faithful): {n_separated} of {len(CASES)} ({n_separated / len(CASES) * 100:.0f}%)"
    )
    print(f"Mean delta (halluc - faithful): {sum(deltas) / len(deltas):+.4f}")
    n_at_threshold_05 = sum(
        1 for r in results if r["halluc_prob"] >= 0.5 and r["faithful_prob"] < 0.5
    )
    n_flagged_both = sum(
        1 for r in results if r["halluc_prob"] >= 0.5 and r["faithful_prob"] >= 0.5
    )
    n_flagged_neither = sum(
        1 for r in results if r["halluc_prob"] < 0.5 and r["faithful_prob"] < 0.5
    )
    print(
        f"At threshold 0.5: cleanly separated {n_at_threshold_05}; "
        f"flagged both {n_flagged_both}; flagged neither {n_flagged_neither}"
    )

    out = {
        "test": "Hand-crafted adversarial subtle-hallucination stress test",
        "n_cases": len(CASES),
        "n_correctly_separated": n_separated,
        "separation_rate": round(n_separated / len(CASES), 4),
        "mean_delta": round(sum(deltas) / len(deltas), 6),
        "verifier_mode": "substrate_only (default)",
        "honest_caveat": (
            "This is a hand-crafted sanity check, not a benchmark. The "
            "16 categories are intended to cover subtle hallucination "
            "types that real LLMs produce; the source/faithful/hallucinated "
            "triples are authored by this project. A separation rate "
            "significantly above 50% (chance) is a positive signal; "
            "below 50% would indicate the Verifier flips on subtle errors."
        ),
        "per_case": results,
    }
    out_path = Path("benchmarks/adversarial_subtle/results_2026-05-17.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
