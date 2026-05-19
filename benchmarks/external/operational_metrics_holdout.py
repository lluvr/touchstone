"""Held-out F1-optimal threshold selection on n=400 subsamples.

Sister to ``operational_metrics_on_subsample.py``. That script picks the
F1-optimal threshold on the same 400 rows it then reports F1 on; the
reported F1 is therefore the in-sample optimum and biased upward. This
script splits each n=400 subsample into a 200-row tune half and a
200-row eval half, stratified by label (each half preserves the
subsample's base rate to the nearest example), picks the F1-optimal
threshold on the tune half, then reports F1 / precision / recall on the
eval half at that threshold. The headline F1 the doc cites alongside
the in-sample number is the eval-half F1; the gap between in-sample
and held-out is the inflation introduced by tuning-on-test.

Tune/eval split is a deterministic stratified interleave (positive
examples in encounter order go to tune/eval/tune/eval/...; negative
examples likewise). No randomness; reproducible from the same
subsample indices.

Run::

    python -m benchmarks.external.operational_metrics_holdout
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from benchmarks.external.operational_metrics_on_subsample import (
    CORPORA,
    _load_detector_scores_on_subsample,
)


def _stratified_interleave_split(
    scores: list[float], labels: list[int]
) -> tuple[tuple[list[float], list[int]], tuple[list[float], list[int]]]:
    """Deterministic stratified split: alternate positives (and negatives)
    between tune and eval in encounter order. Both halves preserve the
    base rate to the nearest example."""
    tune_s: list[float] = []
    tune_l: list[int] = []
    eval_s: list[float] = []
    eval_l: list[int] = []
    pos_seen = 0
    neg_seen = 0
    for s, lab in zip(scores, labels, strict=True):
        if lab == 1:
            if pos_seen % 2 == 0:
                tune_s.append(s)
                tune_l.append(lab)
            else:
                eval_s.append(s)
                eval_l.append(lab)
            pos_seen += 1
        else:
            if neg_seen % 2 == 0:
                tune_s.append(s)
                tune_l.append(lab)
            else:
                eval_s.append(s)
                eval_l.append(lab)
            neg_seen += 1
    return (tune_s, tune_l), (eval_s, eval_l)


def _f1_optimal_threshold(scores: list[float], labels: list[int]) -> tuple[float, float]:
    """Sweep thresholds and return (best_threshold, best_f1) on the given pair."""
    n_pos = sum(labels)
    if n_pos == 0:
        return 0.5, 0.0
    paired = sorted(zip(scores, labels, strict=True), key=lambda p: -p[0])
    tp = 0
    fp = 0
    best_f1 = 0.0
    best_thr = paired[0][0]
    for k, (s, lab) in enumerate(paired, start=1):
        if lab == 1:
            tp += 1
        else:
            fp += 1
        precision = tp / k
        recall = tp / n_pos
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        if f1 > best_f1:
            best_f1 = f1
            best_thr = s
    return best_thr, best_f1


def _eval_at_threshold(scores: list[float], labels: list[int], threshold: float) -> dict[str, Any]:
    """Apply a fixed threshold and report precision/recall/F1 at it."""
    n_pos = sum(labels)
    n = len(labels)
    tp = sum(1 for s, lab in zip(scores, labels, strict=True) if s >= threshold and lab == 1)
    fp = sum(1 for s, lab in zip(scores, labels, strict=True) if s >= threshold and lab == 0)
    fn = n_pos - tp
    n_flagged = tp + fp
    precision = tp / n_flagged if n_flagged else 0.0
    recall = tp / n_pos if n_pos else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "threshold": round(threshold, 4),
        "n_flagged": n_flagged,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "n_eval": n,
        "n_eval_positive": n_pos,
    }


def main() -> None:
    out: OrderedDict[str, Any] = OrderedDict()
    print()
    for corpus_dir, label, judge_snap_rel in CORPORA:
        print(f"=== {label} (n=400, holdout-validated) ===")
        all_labels, all_detectors = _load_detector_scores_on_subsample(corpus_dir, judge_snap_rel)
        per_detector: OrderedDict[str, Any] = OrderedDict()
        for name, scores in all_detectors.items():
            (tune_s, tune_l), (eval_s, eval_l) = _stratified_interleave_split(scores, all_labels)
            tune_thr, tune_f1 = _f1_optimal_threshold(tune_s, tune_l)
            eval_at_tune = _eval_at_threshold(eval_s, eval_l, tune_thr)
            # Also compute eval's OWN F1-optimal so the in-sample/holdout
            # inflation is auditable per-row.
            _, eval_in_sample_f1 = _f1_optimal_threshold(eval_s, eval_l)
            inflation = round(eval_in_sample_f1 - eval_at_tune["f1"], 4)
            per_detector[name] = {
                "tune_n": len(tune_l),
                "tune_n_positive": sum(tune_l),
                "tune_f1_optimal_threshold": round(tune_thr, 4),
                "tune_f1_optimal": round(tune_f1, 4),
                "eval_at_tune_threshold": eval_at_tune,
                "eval_in_sample_f1_optimal": round(eval_in_sample_f1, 4),
                "in_sample_vs_holdout_F1_inflation_on_eval": inflation,
            }
            ev = eval_at_tune
            print(
                f"  {name:42s}  tune_thr={tune_thr:.3f}  "
                f"tune_F1={tune_f1:.3f}  eval_F1={ev['f1']:.3f}  "
                f"(P={ev['precision']:.3f}, R={ev['recall']:.3f}, "
                f"inflation_vs_in_sample_eval={inflation:+.3f})"
            )
        out[corpus_dir] = {
            "label": label,
            "n_subsample": len(all_labels),
            "n_positive": sum(all_labels),
            "split": "deterministic stratified interleave (pos→tune,eval,tune,eval; neg likewise)",
            "tune_n": len(all_labels) // 2 + sum(all_labels) % 2,
            "eval_n": len(all_labels) // 2,
            "per_detector": per_detector,
        }
        print()
    out_path = Path("benchmarks/external/operational_metrics_n400_holdout_2026-05-18.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
