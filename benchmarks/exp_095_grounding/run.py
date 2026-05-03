"""EXP-095 grounding decomposition benchmark runner.

Runs ``grounding_decomposition`` from Touchstone against each
ground-truth-classified output, compares predicted G/F/P proportions
to the manual baseline, and emits an aggregate report.

Usage
-----
From the touchstone repository root::

    python -m benchmarks.exp_095_grounding.run

Or with pytest from the test suite::

    pytest tests/test_benchmarks.py

Output
------
JSON to stdout with per-output predicted vs ground-truth proportions
and aggregate agreement statistics (mean absolute error per category,
P-detection sign agreement, etc.). Optionally writes to a results
file when ``--output PATH`` is supplied.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from clarethium_touchstone.measure import grounding_decomposition

BENCHMARK_DIR = Path(__file__).parent
GROUND_TRUTH_PATH = BENCHMARK_DIR / "ground_truth.json"
SOURCES_DIR = BENCHMARK_DIR / "sources"
OUTPUTS_DIR = BENCHMARK_DIR / "outputs"


@dataclass
class PerOutputResult:
    """Result of running Layer 11 on one ground-truth-classified output."""

    output_id: int
    model: str
    topic: str
    predicted: dict[str, float]
    manual_full: dict[str, float] | None
    manual_p_estimate: list[float] | None
    detector_v031: dict[str, float]
    p_agreement_with_manual: str  # "exact" | "in_range" | "outside_range" | "no_baseline"


def run_single(
    output_path: Path,
    source_path: Path,
) -> dict[str, float]:
    """Run Layer 11 on one (output, source) pair, return G/F/P proportions."""
    text = output_path.read_text(encoding="utf-8")
    source = source_path.read_text(encoding="utf-8")
    result = grounding_decomposition(text, source)
    return dict(result["proportions"])


def classify_p_agreement(
    predicted_p: float,
    manual_full: dict[str, float] | None,
    manual_p_estimate: list[float] | None,
) -> str:
    """Compare predicted P% to manual baseline.

    Returns:
        "exact" — manual_full present and predicted within ±2pp
        "close" — manual_full present and predicted within ±5pp
        "off" — manual_full present and predicted outside ±5pp
        "in_range" — only manual_p_estimate available and predicted within range
        "outside_range" — only manual_p_estimate available and predicted outside range
        "no_baseline" — neither manual signal available (should not occur)
    """
    if manual_full is not None:
        manual_p = manual_full["P"]
        diff = abs(predicted_p - manual_p)
        if diff <= 0.02:
            return "exact"
        if diff <= 0.05:
            return "close"
        return "off"
    if manual_p_estimate is not None:
        low, high = manual_p_estimate
        # Allow ±2pp slack at boundaries to absorb manual-estimate uncertainty
        if low - 0.02 <= predicted_p <= high + 0.02:
            return "in_range"
        return "outside_range"
    return "no_baseline"


def run_all() -> list[PerOutputResult]:
    """Run the benchmark on every ground-truth entry."""
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text())
    results: list[PerOutputResult] = []

    for entry in ground_truth["outputs"]:
        output_path = OUTPUTS_DIR / entry["output_file"]
        source_path = SOURCES_DIR / entry["source_file"]
        if not output_path.exists():
            raise FileNotFoundError(f"missing output: {output_path}")
        if not source_path.exists():
            raise FileNotFoundError(f"missing source: {source_path}")

        predicted = run_single(output_path, source_path)
        manual_full = entry.get("manual_full")
        manual_p_estimate = entry.get("manual_p_estimate")

        results.append(
            PerOutputResult(
                output_id=entry["id"],
                model=entry["model"],
                topic=entry["topic"],
                predicted=predicted,
                manual_full=manual_full,
                manual_p_estimate=manual_p_estimate,
                detector_v031=entry["detector_v031"],
                p_agreement_with_manual=classify_p_agreement(
                    predicted["P"], manual_full, manual_p_estimate
                ),
            )
        )
    return results


def aggregate(results: list[PerOutputResult]) -> dict[str, object]:
    """Compute aggregate statistics across all per-output results."""
    n = len(results)
    if n == 0:
        return {"n": 0}

    # P-detection agreement breakdown
    agreement_counts = {
        "exact": 0,
        "close": 0,
        "off": 0,
        "in_range": 0,
        "outside_range": 0,
        "no_baseline": 0,
    }
    for r in results:
        agreement_counts[r.p_agreement_with_manual] += 1

    # Mean absolute error vs manual_full where available (G/F/P)
    full_results = [r for r in results if r.manual_full is not None]
    mae_by_category: dict[str, float | None] = {"G": None, "F": None, "P": None}
    if full_results:
        for cat in ("G", "F", "P"):
            errors = [
                abs(r.predicted[cat] - r.manual_full[cat])  # type: ignore[index]
                for r in full_results
            ]
            mae_by_category[cat] = round(sum(errors) / len(errors), 4)

    # MAE vs detector_v031 for backwards-compat reference (all entries)
    mae_vs_detector: dict[str, float] = {}
    for cat in ("G", "F", "P"):
        errors = [abs(r.predicted[cat] - r.detector_v031[cat]) for r in results]
        mae_vs_detector[cat] = round(sum(errors) / len(errors), 4)

    # P-direction agreement: did predicted detect any P when manual said >0%?
    p_direction_agreement = 0
    p_direction_n = 0
    for r in results:
        if r.manual_full is not None:
            manual_has_p = r.manual_full["P"] > 0
            predicted_has_p = r.predicted["P"] > 0
            if manual_has_p == predicted_has_p:
                p_direction_agreement += 1
            p_direction_n += 1
        elif r.manual_p_estimate is not None:
            manual_has_p = r.manual_p_estimate[1] > 0  # high estimate
            predicted_has_p = r.predicted["P"] > 0
            if manual_has_p == predicted_has_p:
                p_direction_agreement += 1
            p_direction_n += 1

    return {
        "n": n,
        "n_with_full_manual": len(full_results),
        "p_agreement_breakdown": agreement_counts,
        "p_direction_agreement_rate": (
            round(p_direction_agreement / p_direction_n, 3) if p_direction_n else None
        ),
        "mae_vs_manual_full": mae_by_category,
        "mae_vs_detector_v031": mae_vs_detector,
    }


def render_report(results: list[PerOutputResult], aggregate_stats: dict) -> str:
    """Emit a human-readable + machine-readable JSON report."""
    return json.dumps(
        {
            "experiment": "EXP-095 grounding decomposition",
            "library": "clarethium-touchstone",
            "n_outputs": len(results),
            "aggregate": aggregate_stats,
            "per_output": [
                {
                    "id": r.output_id,
                    "model": r.model,
                    "topic": r.topic,
                    "predicted": {k: round(v, 4) for k, v in r.predicted.items()},
                    "manual_full": r.manual_full,
                    "manual_p_estimate": r.manual_p_estimate,
                    "detector_v031": r.detector_v031,
                    "p_agreement": r.p_agreement_with_manual,
                }
                for r in results
            ],
        },
        indent=2,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="EXP-095 grounding decomposition benchmark.")
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
