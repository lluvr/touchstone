"""Operational metrics for production deployment analysis.

AUC is a research metric. Production teams care about operational
metrics at specific decision thresholds:

- **Precision at recall 0.9**: "we want to catch 90% of hallucinations;
  what fraction of flagged outputs are false alarms?"
- **Recall at precision 0.9**: "we only flag when we're 90% sure; how
  many real hallucinations do we miss?"
- **F1-optimal threshold + its precision/recall**: the most-balanced
  operating point and what it costs.
- **Precision/recall/F1 at threshold 0.5** (the Verifier's default
  ``should_flag()`` threshold): the out-of-box deployment behaviour.
- **Reviewer-burden estimate**: at recall 0.9, how many false alarms
  would a reviewer process per real hallucination caught?

This script reads the existing per-example scores from the snapshot
files and computes operational metrics for every (system, corpus)
combination. It does NOT re-run any model.

Usage::

    python -m benchmarks.external.operational_metrics
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

BASE = Path("benchmarks/external")


def _ops_metrics(scores: list[float], labels: list[int]) -> dict[str, Any]:
    """Compute operational metrics for a binary classifier.

    ``scores[i]`` is the model's score for example ``i`` (higher means
    more likely positive, where positive = hallucinated). ``labels[i]``
    is 1 for hallucinated, 0 for supported. Returns a dict with the
    metrics described in the module docstring.
    """
    n = len(scores)
    if n == 0 or n != len(labels):
        return {"error": "empty or mismatched inputs"}

    n_pos = sum(labels)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return {"error": "single-class corpus"}

    # Sort examples by descending score; sweep threshold from "flag all" to "flag nothing".
    paired = sorted(zip(scores, labels, strict=True), key=lambda p: -p[0])
    sorted_scores = [s for s, _ in paired]
    sorted_labels = [lab for _, lab in paired]

    # Sweep threshold: at each k examples flagged (the top k by score),
    # compute precision/recall/F1.
    tp = 0
    fp = 0
    curves: list[tuple[float, int, int, float, float, float]] = []
    for k, lab in enumerate(sorted_labels, start=1):
        if lab == 1:
            tp += 1
        else:
            fp += 1
        recall = tp / n_pos
        precision = tp / k
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        # The threshold corresponding to "flag top k" is the kth-highest score.
        threshold = sorted_scores[k - 1]
        curves.append((threshold, tp, fp, precision, recall, f1))

    # Precision at recall ≥ 0.9 (find smallest k with recall >= 0.9 and report its precision).
    precision_at_r90 = None
    for thr, tp_, fp_, prec, rec, _ in curves:
        if rec >= 0.9:
            precision_at_r90 = {
                "threshold": round(thr, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "n_flagged": tp_ + fp_,
                "tp": tp_,
                "fp": fp_,
                "false_positive_rate": round(fp_ / n_neg, 4),
                "false_alarms_per_caught": round(fp_ / max(tp_, 1), 2),
            }
            break

    # Recall at precision ≥ 0.9 (find largest k with precision >= 0.9 and report its recall).
    recall_at_p90 = None
    for thr, tp_, fp_, prec, rec, _ in reversed(curves):
        if prec >= 0.9:
            recall_at_p90 = {
                "threshold": round(thr, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "n_flagged": tp_ + fp_,
                "tp": tp_,
                "fp": fp_,
            }
            break

    # F1 optimum.
    f1_opt_idx, (thr, tp_, fp_, prec, rec, f1) = max(enumerate(curves), key=lambda x: x[1][5])
    f1_optimal = {
        "threshold": round(thr, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "n_flagged": tp_ + fp_,
    }

    # Lift at top-K% (triage / review-queue prioritization use case).
    # If a team can review only K% of outputs, how much better is Touchstone
    # ranking than random review? lift = (precision at top-K%) / base_rate.
    lift_at_top: dict[str, dict[str, Any]] = {}
    base_rate = n_pos / n
    for pct in (5, 10, 20, 30):
        k = max(1, int(round(n * pct / 100.0)))
        if k > len(curves):
            continue
        thr, tp_, fp_, prec, rec, _f1 = curves[k - 1]
        lift = prec / base_rate if base_rate > 0 else 0.0
        lift_at_top[f"top_{pct}_percent"] = {
            "k": k,
            "threshold": round(thr, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "lift_vs_random": round(lift, 2),
            "tp": tp_,
            "fp": fp_,
        }

    # Metrics at threshold 0.5 (Verifier should_flag default).
    tp05 = sum(1 for s, lab in zip(scores, labels, strict=True) if s >= 0.5 and lab == 1)
    fp05 = sum(1 for s, lab in zip(scores, labels, strict=True) if s >= 0.5 and lab == 0)
    fn05 = sum(1 for s, lab in zip(scores, labels, strict=True) if s < 0.5 and lab == 1)
    n_flagged_05 = tp05 + fp05
    prec05 = tp05 / max(n_flagged_05, 1)
    rec05 = tp05 / n_pos
    f1_05 = 2 * prec05 * rec05 / (prec05 + rec05) if (prec05 + rec05) > 0 else 0.0
    at_threshold_05 = {
        "threshold": 0.5,
        "n_flagged": n_flagged_05,
        "tp": tp05,
        "fp": fp05,
        "fn": fn05,
        "precision": round(prec05, 4),
        "recall": round(rec05, 4),
        "f1": round(f1_05, 4),
        "false_positive_rate": round(fp05 / n_neg, 4),
    }

    return {
        "n_total": n,
        "n_positive": n_pos,
        "n_negative": n_neg,
        "base_rate": round(n_pos / n, 4),
        "at_threshold_0.5": at_threshold_05,
        "precision_at_recall_0.9": precision_at_r90,
        "recall_at_precision_0.9": recall_at_p90,
        "f1_optimal": f1_optimal,
        "lift_at_top_k": lift_at_top,
    }


def _load_corpus_scores(corpus_dir: str) -> dict[str, tuple[list[float], list[int]]]:
    """For each system on this corpus, return (scores, labels) tuples.

    ``scores`` are oriented so higher means more likely hallucinated.
    """
    out: dict[str, tuple[list[float], list[int]]] = {}

    base = BASE / corpus_dir / "results"

    # MiniCheck (with per-example probs, with CIs).
    mc_path = base / "minicheck_with_cis_2026-05-16.json"
    if mc_path.exists():
        d = json.loads(mc_path.read_text())
        # Raw prob is P(supported); invert for "hallucinated" positive.
        probs = d["per_example_raw_prob_supported"]
        labels = d["per_example_label_hallucinated"]
        out["minicheck_flan_t5_large"] = ([1.0 - p for p in probs], labels)

    # AlignScore.
    as_path = base / "alignscore_baseline_2026-05-15.json"
    if as_path.exists():
        d = json.loads(as_path.read_text())
        probs = d["per_example_raw_score_supported"]
        labels = d["per_example_label"]
        out["alignscore_base"] = ([1.0 - p for p in probs], labels)

    # Trivial baselines.
    tb_path = base / "trivial_lexical_baselines_2026-05-17.json"
    if tb_path.exists():
        d = json.loads(tb_path.read_text())
        labels = d["per_example_label_hallucinated"]
        for name, scores in d["per_example_scores"].items():
            out[f"trivial_{name}"] = (list(scores), labels)

    return out


CORPORA = [
    ("ragtruth_summary", "RAGTruth Summary"),
    ("summeval", "SummEval"),
    ("halueval_summarization", "HaluEval summarization"),
]


def main() -> None:
    summary: OrderedDict[str, OrderedDict[str, Any]] = OrderedDict()
    for corpus_dir, label in CORPORA:
        print(f"\n=== {label} ===")
        per_system = _load_corpus_scores(corpus_dir)
        per_system_metrics: OrderedDict[str, Any] = OrderedDict()
        for system, (scores, labels) in per_system.items():
            metrics = _ops_metrics(scores, labels)
            per_system_metrics[system] = metrics
            if "error" in metrics:
                print(f"  {system}: {metrics['error']}")
                continue
            f1opt = metrics["f1_optimal"]
            p_r90 = metrics["precision_at_recall_0.9"]
            r_p90 = metrics["recall_at_precision_0.9"]
            print(
                f"  {system:32s}  base_rate {metrics['base_rate']:.2f}  "
                f"F1-opt {f1opt['f1']:.3f} (p={f1opt['precision']:.2f}, r={f1opt['recall']:.2f}, thr={f1opt['threshold']:.3f})"
            )
            if p_r90:
                print(
                    f"    @recall 0.9: precision {p_r90['precision']:.3f}  "
                    f"({p_r90['false_alarms_per_caught']:.1f} false alarms per caught hallucination; "
                    f"FPR {p_r90['false_positive_rate']:.3f})"
                )
            else:
                print("    @recall 0.9: not achievable")
            if r_p90:
                print(
                    f"    @precision 0.9: recall {r_p90['recall']:.3f}  (catches {r_p90['tp']} of {metrics['n_positive']})"
                )
            else:
                print("    @precision 0.9: not achievable")
            top10 = metrics["lift_at_top_k"].get("top_10_percent")
            if top10:
                print(
                    f"    triage (top 10%): precision {top10['precision']:.3f}  "
                    f"recall {top10['recall']:.3f}  lift {top10['lift_vs_random']:.2f}x  "
                    f"(catches {top10['tp']} of {metrics['n_positive']})"
                )
        summary[corpus_dir] = per_system_metrics

    out_path = Path("benchmarks/external/operational_metrics_2026-05-17.json")
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
