"""Pairwise statistical tests for §4.2 / §4.3 detector-ordering claims.

For every (detector A, detector B) pair on every n=400 subsample, run:

- Paired stratified bootstrap on AUC(A) - AUC(B). Reports point
  difference, 95% CI, two-sided p-value. The CI / p-value tells you
  whether the AUC ordering is statistically supported at n=400 or is
  within paired sampling noise.

- McNemar's exact binomial test on paired binary verdicts at each
  detector's F1-optimal threshold. Reports b, c (discordant counts) and
  the two-sided exact p-value. Tells you whether one detector's verdict
  distribution differs from the other at their respective operating
  points.

- Paired bootstrap on F1-optimal-at-fixed-threshold(A) - F1-optimal(B)
  is not meaningful: the threshold is selected from each detector's
  own data. Instead this script bootstraps the AUC and reports the
  F1-optimal McNemar separately.

The output snapshot has, for each corpus, a per-pair-of-detectors
dictionary with both tests. The stdout summary prints just the
significant pairs (p < 0.05 by either test) with their effect sizes.

Run::

    python -m benchmarks.external.paired_detector_tests
"""

from __future__ import annotations

import json
from collections import OrderedDict
from itertools import combinations
from pathlib import Path
from typing import Any

from benchmarks.external._paired_tests import mcnemar_exact, paired_bootstrap_auc_diff
from benchmarks.external.operational_metrics import _ops_metrics
from benchmarks.external.operational_metrics_on_subsample import (
    CORPORA,
    _load_detector_scores_on_subsample,
)


def _verdicts_at_f1opt(scores: list[float], labels: list[int]) -> tuple[list[int], float]:
    """Return (binary verdicts at F1-optimal threshold, threshold)."""
    m = _ops_metrics(scores, labels)
    if "error" in m:
        return [0] * len(scores), 0.5
    thr = m["f1_optimal"]["threshold"]
    verdicts = [1 if s >= thr else 0 for s in scores]
    return verdicts, thr


def main() -> None:
    out: OrderedDict[str, Any] = OrderedDict()
    summary_lines: list[str] = []
    for corpus_dir, label, judge_snap_rel in CORPORA:
        print(f"\n=== {label} (n=400) ===")
        labels, detectors = _load_detector_scores_on_subsample(corpus_dir, judge_snap_rel)
        names = list(detectors.keys())
        # Precompute F1opt verdicts and thresholds.
        verdicts_by_name: dict[str, list[int]] = {}
        thr_by_name: dict[str, float] = {}
        for name, scores in detectors.items():
            v, t = _verdicts_at_f1opt(scores, labels)
            verdicts_by_name[name] = v
            thr_by_name[name] = t

        per_pair: OrderedDict[str, Any] = OrderedDict()
        for a, b in combinations(names, 2):
            auc_test = paired_bootstrap_auc_diff(
                detectors[a], detectors[b], labels, n_resamples=2000, seed=0
            )
            mcn_test = mcnemar_exact(verdicts_by_name[a], verdicts_by_name[b], labels)
            pair_key = f"{a}  vs  {b}"
            per_pair[pair_key] = {
                "paired_bootstrap_auc_diff": auc_test,
                "mcnemar_at_f1_optimal": {
                    "threshold_a": round(thr_by_name[a], 4),
                    "threshold_b": round(thr_by_name[b], 4),
                    **mcn_test,
                },
            }
            sig_marker = ""
            if auc_test["significant_at_0.05"]:
                sig_marker += "[AUC]"
            if mcn_test["p_two_sided"] < 0.05:
                sig_marker += "[McN]"
            if sig_marker:
                line = (
                    f"  {sig_marker:10s}  {a:38s}  vs  {b:38s}  "
                    f"ΔAUC={auc_test['diff_point']:+.3f} "
                    f"[{auc_test['diff_ci_low']:+.3f}, {auc_test['diff_ci_high']:+.3f}]  "
                    f"p_AUC={auc_test['p_two_sided']:.3f}  "
                    f"p_McN={mcn_test['p_two_sided']:.3f}"
                )
                summary_lines.append(line)
                print(line)

        out[corpus_dir] = {
            "label": label,
            "n_subsample": len(labels),
            "n_positive": sum(labels),
            "detectors": names,
            "f1_optimal_thresholds": {n: round(thr_by_name[n], 4) for n in names},
            "per_pair": per_pair,
        }
        print(
            f"  ({sum(1 for line in summary_lines if label in line or label in 'X')} pairs printed)"
        )

    out_path = Path("benchmarks/external/paired_detector_tests_n400_2026-05-19.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {out_path}")
    print(f"\nTotal significant pairs (across all corpora): {len(summary_lines)}")


if __name__ == "__main__":
    main()
