"""Tie-aware envelope on the n=400 cross-detector metrics.

``operational_metrics_on_subsample.py`` uses Python's stable sort on
``-score``: within a tied group (e.g., 274 of 400 SummEval Grok probs
at exactly 0.0; 110 of 400 RAGTruth Grok probs at 0.35) the
order is the input order. That makes the precision-at-recall and
F1-optimal numbers depend on which examples in the source pair file
happen to come first within a tied group, which is an artifact rather
than a property of the detector.

This sibling script breaks ties uniformly at random by adding a
sub-quantum jitter (1e-6, well below the visible 0.05+ gap between
distinct probability values in every corpus checked) to every score
and re-running ``_ops_metrics``. Repeat K=100 times with independent
RNG seeds; report mean and std for F1-optimal, P@R90, R@P90, and
top-10% lift across the K permutations. If std is large relative to
the cross-detector gap, the headline ordering is a tie-break artifact;
if std is small, the headline is robust.

The mean across permutations is the unbiased estimator of expected
metric under random tie-breaking. The std is the operating-point
uncertainty contributed by ties; report it alongside any cross-detector
comparison whose gap is on the same order of magnitude.

Run::

    python -m benchmarks.external.operational_metrics_tie_envelope
"""

from __future__ import annotations

import json
import math
import random
from collections import OrderedDict
from pathlib import Path
from typing import Any

from benchmarks.external.operational_metrics import _ops_metrics
from benchmarks.external.operational_metrics_on_subsample import (
    CORPORA,
    _load_detector_scores_on_subsample,
)

N_PERMS = 100
JITTER_EPS = 1e-6  # < 0.05 (the smallest visible gap between probability values)


def _mean_std(xs: list[float]) -> tuple[float, float]:
    if not xs:
        return float("nan"), float("nan")
    mu = sum(xs) / len(xs)
    var = sum((x - mu) ** 2 for x in xs) / max(1, len(xs) - 1)
    return mu, math.sqrt(var)


def _tie_envelope(
    scores: list[float], labels: list[int], n_perms: int = N_PERMS, seed: int = 0
) -> dict[str, Any]:
    """K permutations of sub-quantum jitter on scores; aggregate metrics."""
    rng = random.Random(seed)
    f1opt_vals: list[float] = []
    f1opt_thr_vals: list[float] = []
    pr90_vals: list[float] = []
    rp90_vals: list[float] = []
    top10_lift_vals: list[float] = []
    for _ in range(n_perms):
        jittered = [s + rng.uniform(0.0, JITTER_EPS) for s in scores]
        m = _ops_metrics(jittered, labels)
        if "error" in m:
            return m
        f1opt_vals.append(m["f1_optimal"]["f1"])
        f1opt_thr_vals.append(m["f1_optimal"]["threshold"])
        pr90 = m.get("precision_at_recall_0.9")
        if pr90:
            pr90_vals.append(pr90["precision"])
        rp90 = m.get("recall_at_precision_0.9")
        if rp90:
            rp90_vals.append(rp90["recall"])
        top10 = m["lift_at_top_k"].get("top_10_percent")
        if top10:
            top10_lift_vals.append(top10["lift_vs_random"])
    f1_mu, f1_sd = _mean_std(f1opt_vals)
    thr_mu, thr_sd = _mean_std(f1opt_thr_vals)
    pr90_mu, pr90_sd = _mean_std(pr90_vals) if pr90_vals else (float("nan"), float("nan"))
    rp90_mu, rp90_sd = _mean_std(rp90_vals) if rp90_vals else (float("nan"), float("nan"))
    top10_mu, top10_sd = (
        _mean_std(top10_lift_vals) if top10_lift_vals else (float("nan"), float("nan"))
    )
    return {
        "n_permutations": n_perms,
        "jitter_epsilon": JITTER_EPS,
        "f1_optimal_mean": round(f1_mu, 4),
        "f1_optimal_std": round(f1_sd, 4),
        "f1_optimal_threshold_mean": round(thr_mu, 4),
        "f1_optimal_threshold_std": round(thr_sd, 4),
        "precision_at_recall_0.9_mean": round(pr90_mu, 4),
        "precision_at_recall_0.9_std": round(pr90_sd, 4),
        "recall_at_precision_0.9_mean": round(rp90_mu, 4),
        "recall_at_precision_0.9_std": round(rp90_sd, 4),
        "top_10_percent_lift_mean": round(top10_mu, 4),
        "top_10_percent_lift_std": round(top10_sd, 4),
    }


def _stable_seed(name: str) -> int:
    """Deterministic across Python interpreter restarts (Python's built-in
    ``hash()`` is randomized via PYTHONHASHSEED). Snapshot reproducibility
    requires a stable seed; SHA-1 over the detector name gives one with
    no extra deps."""
    import hashlib

    return int(hashlib.sha1(name.encode("utf-8")).hexdigest()[:8], 16)


def main() -> None:
    out: OrderedDict[str, Any] = OrderedDict()
    print()
    for corpus_dir, label, judge_snap_rel in CORPORA:
        print(f"=== {label} (n=400, K={N_PERMS} tie-permutations) ===")
        labels, detectors = _load_detector_scores_on_subsample(corpus_dir, judge_snap_rel)
        per_detector: OrderedDict[str, Any] = OrderedDict()
        for name, scores in detectors.items():
            env = _tie_envelope(scores, labels, n_perms=N_PERMS, seed=_stable_seed(name))
            per_detector[name] = env
            print(
                f"  {name:42s}  "
                f"F1={env['f1_optimal_mean']:.3f}±{env['f1_optimal_std']:.3f}  "
                f"thr={env['f1_optimal_threshold_mean']:.3f}±{env['f1_optimal_threshold_std']:.3f}  "
                f"P@R90={env['precision_at_recall_0.9_mean']:.3f}±{env['precision_at_recall_0.9_std']:.3f}  "
                f"R@P90={env['recall_at_precision_0.9_mean']:.3f}±{env['recall_at_precision_0.9_std']:.3f}  "
                f"top10_lift={env['top_10_percent_lift_mean']:.2f}x±{env['top_10_percent_lift_std']:.2f}"
            )
        out[corpus_dir] = {
            "label": label,
            "n_subsample": len(labels),
            "n_positive": sum(labels),
            "n_permutations": N_PERMS,
            "per_detector": per_detector,
        }
        print()
    out_path = Path("benchmarks/external/operational_metrics_n400_tie_envelope_2026-05-18.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
