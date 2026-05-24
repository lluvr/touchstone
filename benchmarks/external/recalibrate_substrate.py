"""Per-corpus substrate recalibration with honest holdout.

The Verifier's substrate-only calibration (``DEFAULT_CALIBRATION_2026_05_17``)
is fit on RAGTruth Summary 70/30. On SummEval and HaluEval it is
out-of-distribution; §4.2 / §4.3 / §4.3.1 all use the default calibration
on every corpus. This script characterizes the out-of-distribution
penalty by:

1. Loading per-pair substrate feature vectors from
   ``substrate_features_n400_2026-05-19.json`` for each corpus.
2. Splitting each corpus's n=400 into a stratified 200/200 tune/eval
   split (same interleave discipline as §4.2.1).
3. Fitting a logistic regression on the tune half (pure-python gradient
   descent on logistic loss with L2 regularization). Reports the fitted
   intercept and per-feature coefficients.
4. Evaluating two probability streams on the eval half:
   - the per-corpus-refit predictions
   - the default-calibration predictions (already in
     ``substrate_only_n400_2026-05-18.json``), sub-selected to the eval
     indices
5. Reporting AUC, F1-optimal (at thresholds picked on tune), and
   ops metrics for both streams on the eval half.

The gap between in-corpus and default-calibration eval AUC is the
out-of-distribution penalty that the §4.2 substrate row is paying on
SummEval and HaluEval.

Run::

    python -m benchmarks.external.recalibrate_substrate
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from pathlib import Path
from typing import Any

from benchmarks.external._bootstrap import auc_roc
from benchmarks.external.operational_metrics import _ops_metrics
from benchmarks.external.operational_metrics_holdout import (
    _eval_at_threshold,
    _f1_optimal_threshold,
)

CORPORA = [
    ("ragtruth_summary", "RAGTruth Summary"),
    ("summeval", "SummEval"),
    ("halueval_summarization", "HaluEval Summarization"),
]


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ex = math.exp(z)
    return ex / (1.0 + ex)


def fit_logistic(
    x_rows: list[dict[str, float]],
    y: list[int],
    feature_names: list[str],
    *,
    n_iter: int = 500,
    lr: float = 1.0,
    l2: float = 0.01,
) -> dict[str, Any]:
    """Pure-python batch gradient descent on logistic loss.

    Returns ``{"intercept": float, "coef": {name: float}}`` matching the
    shape of ``DEFAULT_CALIBRATION_2026_05_17[mode]``. L2 regularization
    is applied to the coefficients (not the intercept).
    """
    n = len(x_rows)
    if n == 0:
        return {"intercept": 0.0, "coef": dict.fromkeys(feature_names, 0.0)}
    intercept = 0.0
    coef = dict.fromkeys(feature_names, 0.0)
    for _ in range(n_iter):
        g_intercept = 0.0
        g_coef = dict.fromkeys(feature_names, 0.0)
        for x, label in zip(x_rows, y, strict=True):
            z = intercept + sum(coef[f] * x[f] for f in feature_names)
            p = _sigmoid(z)
            err = p - label
            g_intercept += err
            for f in feature_names:
                g_coef[f] += err * x[f]
        intercept -= lr * g_intercept / n
        for f in feature_names:
            coef[f] -= lr * (g_coef[f] / n + l2 * coef[f])
    return {"intercept": intercept, "coef": coef}


def predict_logistic(x_rows: list[dict[str, float]], coefs: dict[str, Any]) -> list[float]:
    intercept = coefs["intercept"]
    coef = coefs["coef"]
    out: list[float] = []
    for x in x_rows:
        z = intercept + sum(coef[f] * x[f] for f in coef)
        out.append(_sigmoid(z))
    return out


def _stratified_interleave_indices(labels: list[int]) -> tuple[list[int], list[int]]:
    tune_idx: list[int] = []
    eval_idx: list[int] = []
    pos_seen = 0
    neg_seen = 0
    for i, lab in enumerate(labels):
        if lab == 1:
            if pos_seen % 2 == 0:
                tune_idx.append(i)
            else:
                eval_idx.append(i)
            pos_seen += 1
        else:
            if neg_seen % 2 == 0:
                tune_idx.append(i)
            else:
                eval_idx.append(i)
            neg_seen += 1
    return tune_idx, eval_idx


def analyse_corpus(corpus_dir: str, label: str) -> dict[str, Any]:
    base = Path("benchmarks/external") / corpus_dir / "results"
    feat_doc = json.loads((base / "substrate_features_n400_2026-05-19.json").read_text())
    default_doc = json.loads((base / "substrate_only_n400_2026-05-18.json").read_text())
    feature_names: list[str] = feat_doc["feature_names"]
    features: list[dict[str, float]] = feat_doc["per_example_features"]
    labels: list[int] = feat_doc["per_example_label_hallucinated"]
    default_probs: list[float] = default_doc["per_example_prob_hallucinated"]
    if labels != default_doc["per_example_label_hallucinated"]:
        raise SystemExit(
            f"{corpus_dir}: label mismatch between features and default-prob snapshots"
        )

    tune_idx, eval_idx = _stratified_interleave_indices(labels)
    tune_x = [features[i] for i in tune_idx]
    tune_y = [labels[i] for i in tune_idx]
    eval_x = [features[i] for i in eval_idx]
    eval_y = [labels[i] for i in eval_idx]
    default_eval = [default_probs[i] for i in eval_idx]

    # Default calibration: in-corpus eval AUC + F1 at default-thr-on-tune.
    default_tune_probs = [default_probs[i] for i in tune_idx]
    default_tune_thr, _ = _f1_optimal_threshold(default_tune_probs, tune_y)
    default_eval_at_tune = _eval_at_threshold(default_eval, eval_y, default_tune_thr)
    default_eval_auc = round(auc_roc(default_eval, eval_y), 4)
    default_eval_ops = _ops_metrics(default_eval, eval_y)

    # In-corpus refit calibration.
    fitted = fit_logistic(tune_x, tune_y, feature_names)
    refit_eval = predict_logistic(eval_x, fitted)
    refit_tune = predict_logistic(tune_x, fitted)
    refit_tune_thr, refit_tune_f1 = _f1_optimal_threshold(refit_tune, tune_y)
    refit_eval_at_tune = _eval_at_threshold(refit_eval, eval_y, refit_tune_thr)
    refit_eval_auc = round(auc_roc(refit_eval, eval_y), 4)
    refit_eval_ops = _ops_metrics(refit_eval, eval_y)

    return {
        "label": label,
        "n_subsample": len(labels),
        "n_positive": sum(labels),
        "tune_n": len(tune_y),
        "eval_n": len(eval_y),
        "feature_names": feature_names,
        "fitted_calibration": {
            "intercept": round(fitted["intercept"], 6),
            "coef": {f: round(fitted["coef"][f], 6) for f in feature_names},
        },
        "default_calibration_on_eval": {
            "tune_threshold": round(default_tune_thr, 4),
            "eval_at_tune_threshold": default_eval_at_tune,
            "eval_auc": default_eval_auc,
            "eval_precision_at_recall_0.9": default_eval_ops.get("precision_at_recall_0.9"),
            "eval_recall_at_precision_0.9": default_eval_ops.get("recall_at_precision_0.9"),
        },
        "refit_calibration_on_eval": {
            "tune_f1_optimal_threshold": round(refit_tune_thr, 4),
            "tune_f1_optimal": round(refit_tune_f1, 4),
            "eval_at_tune_threshold": refit_eval_at_tune,
            "eval_auc": refit_eval_auc,
            "eval_precision_at_recall_0.9": refit_eval_ops.get("precision_at_recall_0.9"),
            "eval_recall_at_precision_0.9": refit_eval_ops.get("recall_at_precision_0.9"),
        },
        "refit_gain_eval_auc": round(refit_eval_auc - default_eval_auc, 4),
        "refit_gain_eval_f1": round(refit_eval_at_tune["f1"] - default_eval_at_tune["f1"], 4),
    }


def main() -> None:
    out: OrderedDict[str, Any] = OrderedDict()
    print()
    for corpus_dir, label in CORPORA:
        r = analyse_corpus(corpus_dir, label)
        out[corpus_dir] = r
        print(f"=== {label} (n=400, recalibrated on n=200 tune, eval on n=200) ===")
        dc = r["default_calibration_on_eval"]
        rc = r["refit_calibration_on_eval"]
        print(
            f"  default RAGTruth-trained:  eval AUC={dc['eval_auc']:.3f}  "
            f"eval F1@tune_thr={dc['eval_at_tune_threshold']['f1']:.3f}"
        )
        print(
            f"  in-corpus refit:           eval AUC={rc['eval_auc']:.3f}  "
            f"eval F1@tune_thr={rc['eval_at_tune_threshold']['f1']:.3f}"
        )
        print(
            f"  refit gain:                AUC {r['refit_gain_eval_auc']:+.4f}  "
            f"F1 {r['refit_gain_eval_f1']:+.4f}"
        )
        print()

    out_path = Path("benchmarks/external/substrate_recalibration_n400_2026-05-19.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
