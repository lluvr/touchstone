"""Join the substrate-only Verifier + MiniCheck + AlignScore + Grok judge
results on the 16-case subtle stress test into one cross-detector table.

The substrate-only Verifier results live in
``results_2026-05-17.json`` (one row per case, holding
``faithful_prob`` and ``halluc_prob``). The three external detectors
each wrote a 32-row per-pair snapshot. This script:

1. Loads the substrate-only per-case results.
2. Loads ``pairs.json`` to recover (case_idx, side) ordering.
3. Loads each external detector snapshot and pulls per-pair scores in
   the same row order.
4. For each detector, computes per-case
   ``halluc_score - faithful_score`` and counts how many of the 16
   cases are correctly separated (delta > 0).
5. Emits a per-category breakdown so the structural-blindness
   categories (direction reversal, attribute swap, scoping shift,
   relation reversal, time-frame shift, imputed cause, quarter shift,
   numerical conflation) are visible per detector.
6. Writes a combined JSON snapshot and prints a markdown table.

Run::

    python -m benchmarks.adversarial_subtle.join_detectors
"""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path("benchmarks/adversarial_subtle")
SUBSTRATE_PATH = BASE / "results_2026-05-17.json"
PAIRS_PATH = BASE / "pairs.json"
MINICHECK_PATH = BASE / "minicheck_2026-05-18.json"
ALIGNSCORE_PATH = BASE / "alignscore_2026-05-18.json"
JUDGE_PATH = BASE / "judge_xai_2026-05-18.json"
OUT_PATH = BASE / "cross_detector_2026-05-18.json"

# Detector specs: (label, snapshot path, score key in snapshot,
# direction). direction="hallucinated" means higher = more
# hallucinated; "supported" means higher = more supported (we flip
# to 1 - score for the comparison).
DETECTORS: list[tuple[str, Path, str, str]] = [
    ("MiniCheck Flan-T5-Large", MINICHECK_PATH, "per_example_raw_prob_supported", "supported"),
    ("AlignScore-base", ALIGNSCORE_PATH, "per_example_raw_score_supported", "supported"),
    ("xAI Grok 4.20 non-reasoning", JUDGE_PATH, "per_example_prob_hallucinated", "hallucinated"),
]


def _to_halluc_score(values: list[float], direction: str) -> list[float]:
    if direction == "hallucinated":
        return [float(v) for v in values]
    if direction == "supported":
        return [1.0 - float(v) for v in values]
    raise ValueError(f"unknown direction {direction!r}")


def main() -> None:
    substrate = json.loads(SUBSTRATE_PATH.read_text())
    pairs = json.loads(PAIRS_PATH.read_text())
    if len(pairs) != 2 * substrate["n_cases"]:
        raise SystemExit(
            f"pairs.json has {len(pairs)} rows but substrate has {substrate['n_cases']} cases "
            f"(expected {2 * substrate['n_cases']} pair rows)."
        )

    # Index pair rows by (case_idx, side) so we know which row to pull
    # the score from when the detector emits per-row scores in input
    # order.
    case_indices_by_row: list[tuple[int, str]] = [(p["case_idx"], p["side"]) for p in pairs]

    per_case: list[dict] = []
    for substrate_case in substrate["per_case"]:
        per_case.append(
            {
                "category": substrate_case["category"],
                "scores": {
                    "Touchstone substrate (L1-L11)": {
                        "faithful": substrate_case["faithful_prob"],
                        "hallucinated": substrate_case["halluc_prob"],
                        "delta": substrate_case["delta"],
                        "separated": substrate_case["correctly_separated"],
                    },
                },
            }
        )

    detector_summary: list[dict] = []
    for label, path, key, direction in DETECTORS:
        if not path.exists():
            raise SystemExit(f"missing detector snapshot: {path}")
        snap = json.loads(path.read_text())
        raw = snap[key]
        if len(raw) != len(pairs):
            raise SystemExit(
                f"{label}: snapshot has {len(raw)} per-example scores "
                f"but pairs.json has {len(pairs)} rows"
            )
        halluc_scores = _to_halluc_score(raw, direction)

        case_buckets: dict[int, dict[str, float]] = {}
        for row_idx, (case_idx, side) in enumerate(case_indices_by_row):
            case_buckets.setdefault(case_idx, {})[side] = halluc_scores[row_idx]

        n_separated = 0
        for case_idx, sides in case_buckets.items():
            delta = sides["hallucinated"] - sides["faithful"]
            sep = delta > 0
            if sep:
                n_separated += 1
            per_case[case_idx]["scores"][label] = {
                "faithful": round(sides["faithful"], 6),
                "hallucinated": round(sides["hallucinated"], 6),
                "delta": round(delta, 6),
                "separated": sep,
            }
        detector_summary.append(
            {
                "detector": label,
                "n_correctly_separated": n_separated,
                "n_cases": substrate["n_cases"],
                "separation_rate": round(n_separated / substrate["n_cases"], 4),
            }
        )

    detector_summary.insert(
        0,
        {
            "detector": "Touchstone substrate (L1-L11)",
            "n_correctly_separated": substrate["n_correctly_separated"],
            "n_cases": substrate["n_cases"],
            "separation_rate": substrate["separation_rate"],
        },
    )

    # Per-category breakdown: which detectors caught each case.
    by_category: list[dict] = []
    for case in per_case:
        row = {"category": case["category"]}
        for det in case["scores"]:
            row[det] = case["scores"][det]["separated"]
        by_category.append(row)

    out = {
        "test": "Cross-detector comparison on hand-crafted 16-case subtle stress test",
        "n_cases": substrate["n_cases"],
        "detectors": detector_summary,
        "per_category_caught": by_category,
        "per_case": per_case,
        "honest_caveat": (
            "16 hand-authored cases, single author. A separation rate "
            "significantly above 50% (chance) is a positive signal; "
            "below 50% indicates the detector flips on subtle errors. "
            "This is a sanity check, not a benchmark."
        ),
    }
    OUT_PATH.write_text(json.dumps(out, indent=2))

    # Headline table.
    print()
    print("=== Cross-detector separation on 16 subtle cases ===")
    print(f"{'Detector':40s} {'Separated':>12s} {'Rate':>8s}")
    print("-" * 64)
    for d in detector_summary:
        print(
            f"{d['detector']:40s} {d['n_correctly_separated']:>3d} of {d['n_cases']:>2d}     "
            f"{d['separation_rate'] * 100:>5.0f}%"
        )

    print()
    print("=== Per-category catch matrix (Y=separated, .=missed) ===")
    headers = ["category"] + [d["detector"] for d in detector_summary]
    abbr = {h: h[:10] for h in headers}
    print(" | ".join(f"{abbr[h]:<10s}" for h in headers))
    print("-" * (12 * len(headers)))
    for row in by_category:
        cells = [row["category"][:24]]
        for d in detector_summary:
            v = row.get(d["detector"])
            cells.append("Y" if v is True else "." if v is False else "?")
        print(f"{cells[0]:<24s} " + "  ".join(f"{c:<10s}" for c in cells[1:]))

    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
