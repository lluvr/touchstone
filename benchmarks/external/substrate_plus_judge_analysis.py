"""Substrate-plus-judge value-add analysis on the n=400 subsamples.

Answers the production-architecture question §4.2 cannot: when a
frontier judge (Grok 4.20) is already in the loop, does the Touchstone
substrate add measurable value, or is it redundant?

Three combination strategies tested, all pure-python (no sklearn):

1. ``max(substrate, grok)`` — zero-fit ensemble. Flags if EITHER
   detector is concerned. No training-test split needed.
2. ``mean(substrate, grok)`` — zero-fit averaging. Smooths
   single-detector noise.
3. Linear blend ``alpha * substrate + (1 - alpha) * grok`` with alpha
   selected via 5-fold cross-validation (alpha grid 0.0, 0.1, ..., 1.0).
   For each fold, pick the alpha that maximises train-fold AUC; apply
   to test fold; average per-fold test-set ops metrics.

For each corpus, the script reports operational metrics for:
substrate_only, grok_only, max, mean, blend_cv. The output JSON has
the full breakdown; the stdout summary has F1-optimal and P@R90 for
quick comparison.

Run::

    python -m benchmarks.external.substrate_plus_judge_analysis
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from benchmarks.external._bootstrap import auc_roc
from benchmarks.external.operational_metrics import _ops_metrics

BASE = Path("benchmarks/external")

CORPORA = [
    ("ragtruth_summary", "RAGTruth Summary"),
    ("summeval", "SummEval"),
    ("halueval_summarization", "HaluEval Summarization"),
]

ALPHA_GRID = [round(0.1 * i, 1) for i in range(11)]  # 0.0, 0.1, ..., 1.0


def _kfold_indices(n: int, k: int, labels: list[int]) -> list[tuple[list[int], list[int]]]:
    """Stratified k-fold split: split positives and negatives separately,
    interleave so each fold preserves base rate. Deterministic from
    label order (no shuffle). Returns list of (train_idx, test_idx).
    """
    pos = [i for i, lab in enumerate(labels) if lab == 1]
    neg = [i for i, lab in enumerate(labels) if lab == 0]
    folds: list[list[int]] = [[] for _ in range(k)]
    for j, i in enumerate(pos):
        folds[j % k].append(i)
    for j, i in enumerate(neg):
        folds[j % k].append(i)
    splits: list[tuple[list[int], list[int]]] = []
    for f in range(k):
        test = folds[f]
        train = [i for j in range(k) if j != f for i in folds[j]]
        splits.append((train, test))
    return splits


def _blend(subs: list[float], judge: list[float], alpha: float) -> list[float]:
    return [alpha * s + (1.0 - alpha) * j for s, j in zip(subs, judge, strict=True)]


def _select(values: list[float], indices: list[int]) -> list[float]:
    return [values[i] for i in indices]


def _select_int(values: list[int], indices: list[int]) -> list[int]:
    return [values[i] for i in indices]


def _mean_ops(ops_per_fold: list[dict[str, Any]]) -> dict[str, Any]:
    """Average a few headline operational metrics across folds."""
    keys_top = ["f1_optimal", "precision_at_recall_0.9", "recall_at_precision_0.9"]
    out: dict[str, Any] = {"n_folds_aggregated": len(ops_per_fold)}
    for k in keys_top:
        vals_f1 = [o[k] for o in ops_per_fold if o.get(k) is not None]
        if not vals_f1:
            out[k] = None
            continue
        avg = {}
        sample = vals_f1[0]
        for field in sample:
            if isinstance(sample[field], (int, float)):
                avg[field] = round(
                    sum(v[field] for v in vals_f1) / len(vals_f1),
                    4,
                )
            else:
                avg[field] = sample[field]
        out[k] = avg
    # lift at top-10 averaged
    top10 = [o["lift_at_top_k"].get("top_10_percent") for o in ops_per_fold]
    top10 = [t for t in top10 if t]
    if top10:
        avg = {
            "lift_vs_random": round(sum(t["lift_vs_random"] for t in top10) / len(top10), 3),
            "precision": round(sum(t["precision"] for t in top10) / len(top10), 4),
            "recall": round(sum(t["recall"] for t in top10) / len(top10), 4),
        }
        out["lift_at_top_10_percent"] = avg
    return out


def analyse_corpus(corpus_dir: str, label: str) -> dict[str, Any]:
    base = BASE / corpus_dir / "results"
    sub_doc = json.loads((base / "substrate_only_n400_2026-05-18.json").read_text())
    judge_doc = json.loads((base / "judge_xai_grok420_n400_2026-05-18.json").read_text())
    substrate = sub_doc["per_example_prob_hallucinated"]
    judge = judge_doc["per_example_prob_hallucinated"]
    labels = sub_doc["per_example_label_hallucinated"]
    if not (len(substrate) == len(judge) == len(labels)):
        raise SystemExit(
            f"{corpus_dir}: array lengths differ: substrate={len(substrate)}, "
            f"judge={len(judge)}, labels={len(labels)}"
        )

    # Full-corpus zero-fit ensembles and individual detectors.
    full_results: OrderedDict[str, Any] = OrderedDict()
    full_results["substrate_only"] = {
        "auc": round(auc_roc(substrate, labels), 4),
        "ops": _ops_metrics(substrate, labels),
    }
    full_results["grok_only"] = {
        "auc": round(auc_roc(judge, labels), 4),
        "ops": _ops_metrics(judge, labels),
    }
    max_scores = [max(s, j) for s, j in zip(substrate, judge, strict=True)]
    mean_scores = _blend(substrate, judge, alpha=0.5)
    full_results["ensemble_max"] = {
        "auc": round(auc_roc(max_scores, labels), 4),
        "ops": _ops_metrics(max_scores, labels),
    }
    full_results["ensemble_mean"] = {
        "auc": round(auc_roc(mean_scores, labels), 4),
        "ops": _ops_metrics(mean_scores, labels),
    }

    # 5-fold CV linear blend.
    splits = _kfold_indices(len(labels), 5, labels)
    fold_alphas: list[float] = []
    fold_ops: list[dict[str, Any]] = []
    fold_aucs: list[float] = []
    for train_idx, test_idx in splits:
        train_sub = _select(substrate, train_idx)
        train_jud = _select(judge, train_idx)
        train_lab = _select_int(labels, train_idx)
        best_alpha, best_auc = 0.5, -1.0
        for alpha in ALPHA_GRID:
            blend = _blend(train_sub, train_jud, alpha)
            a = auc_roc(blend, train_lab)
            if a > best_auc:
                best_alpha, best_auc = alpha, a
        test_sub = _select(substrate, test_idx)
        test_jud = _select(judge, test_idx)
        test_lab = _select_int(labels, test_idx)
        test_blend = _blend(test_sub, test_jud, best_alpha)
        fold_alphas.append(best_alpha)
        fold_aucs.append(round(auc_roc(test_blend, test_lab), 4))
        fold_ops.append(_ops_metrics(test_blend, test_lab))
    full_results["blend_cv5"] = {
        "fold_alphas": fold_alphas,
        "mean_alpha": round(sum(fold_alphas) / len(fold_alphas), 3),
        "fold_test_aucs": fold_aucs,
        "mean_test_auc": round(sum(fold_aucs) / len(fold_aucs), 4),
        "averaged_ops": _mean_ops(fold_ops),
    }

    return {
        "label": label,
        "n": len(labels),
        "base_rate": round(sum(labels) / len(labels), 4),
        "results": full_results,
    }


def _print_row(name: str, auc: float | None, ops: dict[str, Any] | None) -> None:
    f1 = ops["f1_optimal"]["f1"] if ops and "f1_optimal" in ops else None
    p_r90 = ops.get("precision_at_recall_0.9") if ops else None
    r_p90 = ops.get("recall_at_precision_0.9") if ops else None
    top10 = ops["lift_at_top_k"].get("top_10_percent") if ops and "lift_at_top_k" in ops else None
    p_r90_v = p_r90["precision"] if p_r90 else None
    r_p90_v = r_p90["recall"] if r_p90 else None
    lift = top10["lift_vs_random"] if top10 else None
    print(
        f"  {name:18s}  AUC {auc:.3f}  F1opt {f1:.3f}  "
        f"P@R90 {p_r90_v if p_r90_v is None else f'{p_r90_v:.3f}':<6}  "
        f"R@P90 {r_p90_v if r_p90_v is None else f'{r_p90_v:.3f}':<6}  "
        f"lift10 {lift if lift is None else f'{lift:.2f}x':<6}"
    )


def main() -> None:
    out: OrderedDict[str, Any] = OrderedDict()
    for corpus_dir, label in CORPORA:
        print(f"\n=== {label} (n=400 subsample) ===")
        result = analyse_corpus(corpus_dir, label)
        out[corpus_dir] = result
        r = result["results"]
        _print_row("substrate_only", r["substrate_only"]["auc"], r["substrate_only"]["ops"])
        _print_row("grok_only", r["grok_only"]["auc"], r["grok_only"]["ops"])
        _print_row("ensemble_max", r["ensemble_max"]["auc"], r["ensemble_max"]["ops"])
        _print_row("ensemble_mean", r["ensemble_mean"]["auc"], r["ensemble_mean"]["ops"])
        blend = r["blend_cv5"]
        avg = blend["averaged_ops"]
        print(
            f"  {'blend_cv5':18s}  AUC {blend['mean_test_auc']:.3f}  "
            f"F1opt {avg['f1_optimal']['f1']:.3f}  "
            f"P@R90 {avg['precision_at_recall_0.9']['precision'] if avg.get('precision_at_recall_0.9') else 'n/a':<6}  "
            f"R@P90 {avg['recall_at_precision_0.9']['recall'] if avg.get('recall_at_precision_0.9') else 'n/a':<6}  "
            f"lift10 {avg['lift_at_top_10_percent']['lift_vs_random'] if avg.get('lift_at_top_10_percent') else 'n/a'}x  "
            f"(mean alpha {blend['mean_alpha']})"
        )

    out_path = Path("benchmarks/external/substrate_plus_judge_n400_2026-05-18.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
