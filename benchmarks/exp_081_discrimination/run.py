"""EXP-081 adversarial discrimination benchmark runner.

Runs ``measure()`` against 12 paired faithful/embellished outputs and
compares predicted Layer 4 (source_matching) and Layer 10
(quality_profile) values to the published EXP-081 adversarial-validity
metrics. Reproduces the published d=-5.43 effect size for the
faithful-vs-embellished gap.

Usage
-----
From the touchstone repository root::

    python -m benchmarks.exp_081_discrimination.run

Or with pytest::

    pytest tests/test_benchmarks.py -k exp_081

Output
------
JSON to stdout with per-document predicted metrics, expected values,
and aggregate discrimination statistics (mean gap by condition,
Cohen's d).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from clarethium_touchstone import measure

BENCHMARK_DIR = Path(__file__).parent
GROUND_TRUTH_PATH = BENCHMARK_DIR / "ground_truth.json"
SOURCES_DIR = BENCHMARK_DIR / "sources"
OUTPUTS_DIR = BENCHMARK_DIR / "outputs"


@dataclass
class PerDocResult:
    """Result of running measure() on one EXP-081 doc."""

    doc_id: int
    condition: str
    topic: str
    version: int
    predicted_unsourced_rate: float
    predicted_total_numbers: int
    predicted_substance_index: float
    predicted_presentation_index: float
    predicted_gap: float
    expected: dict[str, object]


def run_single(output_path: Path, source_path: Path) -> dict[str, float | int]:
    """Run measure() on one (output, source) pair and return the
    metrics this benchmark cares about.
    """
    text = output_path.read_text(encoding="utf-8")
    source = source_path.read_text(encoding="utf-8")
    result = measure(text, source=source)

    sm = result["source_matching"]
    qp = result["quality_profile"]
    assert sm is not None
    assert qp is not None
    return {
        "unsourced_rate": sm["unsourced_rate"],
        "total_numbers": sm["n_total"],
        "substance_index": qp["substance_index"],
        "presentation_index": qp["presentation_index"],
        "gap": qp["gap"],
    }


def run_all() -> list[PerDocResult]:
    """Run the benchmark on every ground-truth entry."""
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text())
    results: list[PerDocResult] = []

    for entry in ground_truth["outputs"]:
        output_path = OUTPUTS_DIR / entry["output_file"]
        source_path = SOURCES_DIR / entry["source_file"]
        if not output_path.exists():
            raise FileNotFoundError(f"missing output: {output_path}")
        if not source_path.exists():
            raise FileNotFoundError(f"missing source: {source_path}")

        predicted = run_single(output_path, source_path)
        results.append(
            PerDocResult(
                doc_id=entry["id"],
                condition=entry["condition"],
                topic=entry["topic"],
                version=entry["version"],
                predicted_unsourced_rate=float(predicted["unsourced_rate"]),
                predicted_total_numbers=int(predicted["total_numbers"]),
                predicted_substance_index=float(predicted["substance_index"]),
                predicted_presentation_index=float(predicted["presentation_index"]),
                predicted_gap=float(predicted["gap"]),
                expected=entry["expected"],
            )
        )
    return results


def cohens_d(group_a: list[float], group_b: list[float]) -> float:
    """Cohen's d effect size with pooled standard deviation."""
    if not group_a or not group_b:
        return 0.0
    mean_a = sum(group_a) / len(group_a)
    mean_b = sum(group_b) / len(group_b)
    n_a, n_b = len(group_a), len(group_b)
    var_a = sum((x - mean_a) ** 2 for x in group_a) / max(n_a - 1, 1)
    var_b = sum((x - mean_b) ** 2 for x in group_b) / max(n_b - 1, 1)
    pooled_sd = math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / max(n_a + n_b - 2, 1))
    if pooled_sd == 0:
        return 0.0
    return (mean_a - mean_b) / pooled_sd


def aggregate(results: list[PerDocResult]) -> dict[str, object]:
    """Compute aggregate discrimination statistics."""
    faithful_gaps = [r.predicted_gap for r in results if r.condition == "faithful"]
    embellished_gaps = [r.predicted_gap for r in results if r.condition == "embellished"]

    # MAE per metric vs published values
    mae_unsourced = (
        sum(abs(r.predicted_unsourced_rate - float(r.expected["unsourced_rate"])) for r in results)
        / len(results)
        if results
        else 0.0
    )
    mae_gap = (
        sum(abs(r.predicted_gap - float(r.expected["gap"])) for r in results) / len(results)
        if results
        else 0.0
    )
    mae_substance = (
        sum(
            abs(r.predicted_substance_index - float(r.expected["substance_index"])) for r in results
        )
        / len(results)
        if results
        else 0.0
    )
    mae_presentation = (
        sum(
            abs(r.predicted_presentation_index - float(r.expected["presentation_index"]))
            for r in results
        )
        / len(results)
        if results
        else 0.0
    )

    # Direction agreement on gap sign vs expected
    direction_agreement = sum(
        1 for r in results if (r.predicted_gap > 0) == (float(r.expected["gap"]) > 0)
    )

    return {
        "n": len(results),
        "n_faithful": len(faithful_gaps),
        "n_embellished": len(embellished_gaps),
        "mean_gap_faithful": (
            round(sum(faithful_gaps) / len(faithful_gaps), 4) if faithful_gaps else None
        ),
        "mean_gap_embellished": (
            round(sum(embellished_gaps) / len(embellished_gaps), 4) if embellished_gaps else None
        ),
        "cohens_d_faithful_vs_embellished": round(cohens_d(faithful_gaps, embellished_gaps), 3),
        "gap_direction_agreement_with_published": (
            round(direction_agreement / len(results), 3) if results else None
        ),
        "mae_vs_published": {
            "unsourced_rate": round(mae_unsourced, 4),
            "gap": round(mae_gap, 4),
            "substance_index": round(mae_substance, 4),
            "presentation_index": round(mae_presentation, 4),
        },
    }


def render_report(results: list[PerDocResult], aggregate_stats: dict) -> str:
    """Emit a JSON report with per-doc and aggregate findings."""
    return json.dumps(
        {
            "experiment": "EXP-081 adversarial discrimination",
            "library": "clarethium-touchstone",
            "n_outputs": len(results),
            "aggregate": aggregate_stats,
            "per_output": [
                {
                    "id": r.doc_id,
                    "condition": r.condition,
                    "topic": r.topic,
                    "version": r.version,
                    "predicted": {
                        "unsourced_rate": round(r.predicted_unsourced_rate, 4),
                        "total_numbers": r.predicted_total_numbers,
                        "substance_index": round(r.predicted_substance_index, 4),
                        "presentation_index": round(r.predicted_presentation_index, 4),
                        "gap": round(r.predicted_gap, 4),
                    },
                    "expected": {
                        "unsourced_rate": r.expected["unsourced_rate"],
                        "total_numbers": r.expected["total_numbers"],
                        "substance_index": r.expected["substance_index"],
                        "presentation_index": r.expected["presentation_index"],
                        "gap": r.expected["gap"],
                    },
                }
                for r in results
            ],
        },
        indent=2,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="EXP-081 adversarial discrimination benchmark.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the JSON report. Defaults to stdout only.",
    )
    args = parser.parse_args()

    results = run_all()
    aggregate_stats = aggregate(results)
    report = render_report(results, aggregate_stats)

    print(report)
    if args.output is not None:
        args.output.write_text(report + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
