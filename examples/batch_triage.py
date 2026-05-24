"""Batch-triage a corpus of (text, source) pairs and surface the top-K.

End-to-end pattern for using Touchstone as a review-queue prioritiser:

1. Load a list of ``(text, source, item_id)`` triples (CSV / JSONL / DB).
2. Score every pair with :class:`Verifier` (substrate-only mode; sub-100 ms
   per 5 KB document).
3. Sort by ``prob_hallucinated`` and surface the top-K for human review.
4. Inspect ``scope`` and ``scope_notes`` to separate "high-confidence flag"
   results from "low-signal needs human-review" results.

This is the production use case Touchstone is empirically validated for:
``docs/production_readiness.md`` §3 reports 2-4× lift over random review
on the three external summarization corpora. The pattern below scales
linearly with corpus size and runs single-CPU at ~500-1000 pairs/second
on 5-50 KB documents.

The corpus below is an inline 8-row toy set so the example is offline-safe;
adopters point ``load_corpus()`` at their real source.

Run from the repository root::

    pip install -e .
    python examples/batch_triage.py
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from clarethium_touchstone import Verifier, VerifierResult

# A real adopter would load this from a CSV / JSONL / DB. The eight rows
# below cover the four scope buckets (validated faithful, validated
# embellished, limited signal, insufficient input) so the triage output
# illustrates each case.
SOURCE_Q1 = (
    "Quarterly revenue grew 12% year over year to $143 million, with operating "
    "margins reaching 25%. Headcount declined 8% to 5,000 employees over 18 "
    "months. Customer acquisition cost dropped to $1,200 from a $1,750 baseline. "
    "Retention improved from 87% to 94.2% across the major customer segments."
)

CORPUS: list[tuple[str, str, str]] = [
    (
        "row_01_faithful",
        "Revenue rose 12% to $143 million and operating margins reached 25% "
        "this quarter. Headcount declined 8% to 5,000 employees over 18 "
        "months while customer acquisition cost dropped to $1,200 from $1,750. "
        "Retention improved from 87% to 94.2%.",
        SOURCE_Q1,
    ),
    (
        "row_02_embellished_external_citation",
        "Revenue rose 12% to $143 million while operating margins reached an "
        "industry-leading 25%, well above the SaaS-sector median of 18% per "
        "recent McKinsey analyses. Headcount declined 8% to 5,000 over 18 "
        "months, mirroring Salesforce's reduction. R&D grew from $28 million "
        "to $32 million, signaling product-surface expansion by FY2027.",
        SOURCE_Q1,
    ),
    (
        "row_03_clean_hallucination",
        "Industry-wide revenue grew 47% across all segments according to "
        "McKinsey. The Federal Reserve will raise rates 75 basis points next "
        "month. Tesla announced a 2027 product roadmap citing 18% margins.",
        SOURCE_Q1,
    ),
    (
        "row_04_short_faithful",
        "Revenue grew 12% to $143 million.",
        SOURCE_Q1,
    ),
    (
        "row_05_short_fabricated",
        "Revenue grew 47% to $999 million.",
        SOURCE_Q1,
    ),
    (
        "row_06_empty",
        "",
        SOURCE_Q1,
    ),
    (
        "row_07_whitespace",
        "   \n\t  ",
        SOURCE_Q1,
    ),
    (
        "row_08_paraphrase_preserves_numbers",
        "Quarterly results showed 12% revenue growth reaching $143 million. "
        "Operating margins held at 25%. Workforce shrank to 5,000 employees, "
        "an 8% reduction across 18 months. Customer acquisition costs dropped "
        "to $1,200 from $1,750. Retention rose from 87% to 94.2% across major "
        "customer segments.",
        SOURCE_Q1,
    ),
]


@dataclass(frozen=True)
class TriageRow:
    """One scored row in the triage output."""

    item_id: str
    text_preview: str
    prob_hallucinated: float
    scope: str
    scope_notes: list[str]
    top_unsupported_count: int
    result: VerifierResult


def score_corpus(rows: list[tuple[str, str, str]]) -> list[TriageRow]:
    """Score every ``(item_id, text, source)`` triple in ``rows``."""
    v = Verifier()  # substrate-only mode; no external dependencies
    out: list[TriageRow] = []
    for item_id, text, source in rows:
        result = v.score(text, source=source)
        preview = text[:60].replace("\n", " ").strip() or "(empty)"
        if len(text) > 60:
            preview = preview + "…"
        out.append(
            TriageRow(
                item_id=item_id,
                text_preview=preview,
                prob_hallucinated=result.prob_hallucinated,
                scope=result.scope,
                scope_notes=list(result.scope_notes),
                top_unsupported_count=len(result.top_unsupported),
                result=result,
            )
        )
    return out


def print_triage_table(scored: list[TriageRow], top_k: int = 5) -> None:
    """Pretty-print the triage table sorted by prob_hallucinated descending."""
    print()
    print("=" * 110)
    print("  Batch triage — sorted by prob_hallucinated (descending)")
    print("=" * 110)
    sorted_rows = sorted(scored, key=lambda r: r.prob_hallucinated, reverse=True)
    header = f"{'item_id':<40s} {'prob':>6s} {'scope':<19s} {'spans':>6s}  text"
    print(header)
    print("-" * 110)
    for row in sorted_rows:
        print(
            f"{row.item_id:<40s} {row.prob_hallucinated:>6.3f} "
            f"{row.scope:<19s} {row.top_unsupported_count:>6d}  {row.text_preview}"
        )

    print()
    print("Top", top_k, "rows for human review (default threshold=0.5, scope gated):")
    flagged = [r for r in sorted_rows if r.result.should_flag()]
    if not flagged:
        print("  (no rows cleared the default threshold gate)")
    for row in flagged[:top_k]:
        print(f"  • {row.item_id}: p={row.prob_hallucinated:.3f}")
        for span in row.result.top_unsupported:
            print(f"      [{span.layer11_primary}]  {span.sentence!r}  markers={span.p_markers}")

    print()
    print("Limited-signal / insufficient-input rows (manual review recommended):")
    low_signal = [r for r in sorted_rows if r.scope != "validated"]
    for row in low_signal:
        print(f"  • {row.item_id}: scope={row.scope}")
        for note in row.scope_notes:
            print(f"      - {note}")


def main() -> int:
    print("Touchstone batch-triage example")
    print(f"Corpus size: {len(CORPUS)} rows")
    start = time.perf_counter()
    scored = score_corpus(CORPUS)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    throughput = len(CORPUS) / max(elapsed_ms / 1000.0, 1e-6)
    print(f"Scored in {elapsed_ms:.1f} ms ({throughput:.0f} pairs/second)")

    print_triage_table(scored)

    print()
    print("Notes for production:")
    print(" • Default threshold 0.5 under-flags on every published external corpus.")
    print("   Tune on your own held-out data; F1-optimal threshold on RAGTruth")
    print("   Summary is ≈ 0.26, on SummEval ≈ 0.09, on HaluEval ≈ 0.13.")
    print(" • Scope=='validated' rows are calibrated; act on prob_hallucinated.")
    print(" • Scope=='limited_signal' rows route to manual review, not auto-flag.")
    print(" • Scope=='insufficient_input' rows are typically empty/whitespace or")
    print("   below the char floor; the substrate cannot score them meaningfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
