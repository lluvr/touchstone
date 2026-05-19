"""Holdout-validated substrate-plus-judge blend metrics.

§4.3's headline numbers come from 5-fold CV with per-fold F1-opt
re-selection on the test fold. That is biased upward in the same way
§4.2's in-sample F1-opt is biased (§4.2.1's holdout fix). This sibling
script applies the §4.2.1 + §4.2.2 disciplines to the substrate +
judge blend:

1. Deterministic stratified-interleave split of each n=400 subsample
   into a 200-row tune half and a 200-row eval half (same as
   ``operational_metrics_holdout.py``).
2. On the tune half: sweep alpha over {0.0, 0.1, ..., 1.0}; at each
   alpha sweep thresholds; record the (alpha, threshold) pair that
   maximises tune F1. This is the tune-set's recommendation for the
   production blend.
3. On the eval half: apply the chosen (alpha, threshold) and report
   eval F1, precision, recall, plus eval AUC, P@R90, R@P90, top-10%
   lift on the blended score.
4. Tie envelope: K=100 sub-quantum-jitter permutations of the eval-half
   blended scores; report mean ± std of F1, P@R90, R@P90 on the eval
   set. The blended score is partially continuous (substrate is
   continuous, judge is clustered); the envelope tells you how much
   the clustering propagates through the blend.
5. In-sample-vs-holdout inflation: also compute the eval set's own
   F1-optimal at the chosen alpha (re-selecting the threshold on the
   eval set itself) so the inflation is auditable per row.

Run::

    python -m benchmarks.external.substrate_plus_judge_holdout
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from benchmarks.external._bootstrap import auc_roc
from benchmarks.external.operational_metrics import _ops_metrics
from benchmarks.external.operational_metrics_holdout import (
    _eval_at_threshold,
    _f1_optimal_threshold,
)
from benchmarks.external.operational_metrics_tie_envelope import _tie_envelope
from benchmarks.external.substrate_plus_judge_analysis import (
    ALPHA_GRID,
    _blend,
)

CORPORA = [
    ("ragtruth_summary", "RAGTruth Summary"),
    ("summeval", "SummEval"),
    ("halueval_summarization", "HaluEval Summarization"),
]


def _stratified_split_aligned(
    substrate: list[float], judge: list[float], labels: list[int]
) -> tuple[tuple[list[float], list[float], list[int]], tuple[list[float], list[float], list[int]]]:
    """Same stratified interleave as operational_metrics_holdout, but
    applied jointly to (substrate, judge, labels) so every row's
    substrate score, judge score, and label travel together to the
    same half."""
    tune_s: list[float] = []
    tune_j: list[float] = []
    tune_l: list[int] = []
    eval_s: list[float] = []
    eval_j: list[float] = []
    eval_l: list[int] = []
    pos_seen = 0
    neg_seen = 0
    for s, j, lab in zip(substrate, judge, labels, strict=True):
        if lab == 1:
            if pos_seen % 2 == 0:
                tune_s.append(s)
                tune_j.append(j)
                tune_l.append(lab)
            else:
                eval_s.append(s)
                eval_j.append(j)
                eval_l.append(lab)
            pos_seen += 1
        else:
            if neg_seen % 2 == 0:
                tune_s.append(s)
                tune_j.append(j)
                tune_l.append(lab)
            else:
                eval_s.append(s)
                eval_j.append(j)
                eval_l.append(lab)
            neg_seen += 1
    return (tune_s, tune_j, tune_l), (eval_s, eval_j, eval_l)


def _pick_best_alpha_on_tune_f1(
    tune_sub: list[float], tune_jud: list[float], tune_lab: list[int]
) -> tuple[float, float, float]:
    """At each alpha in the grid, sweep thresholds on the tune blend
    and record tune F1-optimal. Return (best_alpha, best_tune_threshold,
    best_tune_f1)."""
    best_alpha = 0.5
    best_thr = 0.5
    best_f1 = -1.0
    for alpha in ALPHA_GRID:
        blend = _blend(tune_sub, tune_jud, alpha)
        thr, f1 = _f1_optimal_threshold(blend, tune_lab)
        if f1 > best_f1:
            best_f1 = f1
            best_alpha = alpha
            best_thr = thr
    return best_alpha, best_thr, best_f1


def _pick_best_alpha_on_tune_auc(
    tune_sub: list[float], tune_jud: list[float], tune_lab: list[int]
) -> tuple[float, float, float]:
    """At each alpha in the grid, compute tune-set AUC of the blend.
    Return (best_alpha, threshold_from_F1opt_at_that_alpha, best_tune_auc).
    Mirrors the §4.3 CV approach (alpha on AUC) but on a single
    deterministic tune/eval split."""
    best_alpha = 0.5
    best_auc = -1.0
    for alpha in ALPHA_GRID:
        blend = _blend(tune_sub, tune_jud, alpha)
        a = auc_roc(blend, tune_lab)
        if a > best_auc:
            best_auc = a
            best_alpha = alpha
    blend_at_best = _blend(tune_sub, tune_jud, best_alpha)
    thr, _ = _f1_optimal_threshold(blend_at_best, tune_lab)
    return best_alpha, thr, best_auc


def analyse_corpus(corpus_dir: str, label: str) -> dict[str, Any]:
    base = Path("benchmarks/external") / corpus_dir / "results"
    sub_doc = json.loads((base / "substrate_only_n400_2026-05-18.json").read_text())
    substrate = sub_doc["per_example_prob_hallucinated"]
    labels = sub_doc["per_example_label_hallucinated"]
    judge_cued = json.loads((base / "judge_xai_grok420_n400_2026-05-18.json").read_text())[
        "per_example_prob_hallucinated"
    ]
    judge_blind = json.loads((base / "judge_xai_grok420_blind_n400_2026-05-18.json").read_text())[
        "per_example_prob_hallucinated"
    ]

    # Baseline: judge-only holdout (apply §4.2.1 to the judge by itself
    # so we can compare blend gain on the eval half).
    out: OrderedDict[str, Any] = OrderedDict()
    out["n_subsample"] = len(labels)
    out["n_positive"] = sum(labels)
    out["base_rate"] = round(sum(labels) / len(labels), 4)
    out["tune_n"] = (len(labels) // 2) + (sum(labels) % 2)
    out["eval_n"] = len(labels) // 2
    out["variants"] = OrderedDict()

    for judge_label, judge in (("cued", judge_cued), ("blind", judge_blind)):
        (tune_s, tune_j, tune_l), (eval_s, eval_j, eval_l) = _stratified_split_aligned(
            substrate, judge, labels
        )

        # Judge-alone baseline on the same split.
        judge_tune_thr, judge_tune_f1 = _f1_optimal_threshold(tune_j, tune_l)
        judge_eval_at_tune = _eval_at_threshold(eval_j, eval_l, judge_tune_thr)
        judge_eval_auc = round(auc_roc(eval_j, eval_l), 4)
        judge_eval_ops = _ops_metrics(eval_j, eval_l)
        _, judge_eval_in_sample_f1 = _f1_optimal_threshold(eval_j, eval_l)

        # Blend variant 1: pick (alpha, threshold) on tune by F1, evaluate on eval.
        best_alpha, best_tune_thr, best_tune_f1 = _pick_best_alpha_on_tune_f1(
            tune_s, tune_j, tune_l
        )
        eval_blend = _blend(eval_s, eval_j, best_alpha)
        blend_eval_at_tune = _eval_at_threshold(eval_blend, eval_l, best_tune_thr)
        blend_eval_auc = round(auc_roc(eval_blend, eval_l), 4)
        blend_eval_ops = _ops_metrics(eval_blend, eval_l)
        _, blend_eval_in_sample_f1 = _f1_optimal_threshold(eval_blend, eval_l)
        blend_eval_envelope = _tie_envelope(eval_blend, eval_l, n_perms=100, seed=0)

        # Blend variant 2: pick alpha on tune AUC (matching §4.3 CV approach),
        # threshold at that alpha's tune F1-optimal, evaluate on eval.
        auc_alpha, auc_thr, auc_tune_auc = _pick_best_alpha_on_tune_auc(tune_s, tune_j, tune_l)
        eval_blend_auc_pick = _blend(eval_s, eval_j, auc_alpha)
        blend_auc_pick_eval_at_thr = _eval_at_threshold(eval_blend_auc_pick, eval_l, auc_thr)
        blend_auc_pick_eval_auc = round(auc_roc(eval_blend_auc_pick, eval_l), 4)

        # Also compute mean-ensemble (alpha=0.5) on eval as a zero-fit baseline.
        mean_eval = _blend(eval_s, eval_j, 0.5)
        mean_eval_at_tune_thr = _eval_at_threshold(
            mean_eval,
            eval_l,
            # Threshold for mean ensemble: pick its own F1opt on tune.
            _f1_optimal_threshold(_blend(tune_s, tune_j, 0.5), tune_l)[0],
        )

        out["variants"][judge_label] = {
            "judge_only": {
                "tune_f1_optimal_threshold": round(judge_tune_thr, 4),
                "tune_f1_optimal": round(judge_tune_f1, 4),
                "eval_at_tune_threshold": judge_eval_at_tune,
                "eval_in_sample_f1_optimal": round(judge_eval_in_sample_f1, 4),
                "in_sample_vs_holdout_f1_inflation_on_eval": round(
                    judge_eval_in_sample_f1 - judge_eval_at_tune["f1"], 4
                ),
                "eval_auc": judge_eval_auc,
                "eval_precision_at_recall_0.9": judge_eval_ops.get("precision_at_recall_0.9"),
                "eval_recall_at_precision_0.9": judge_eval_ops.get("recall_at_precision_0.9"),
                "eval_top_10_percent_lift": judge_eval_ops["lift_at_top_k"].get("top_10_percent"),
            },
            "blend_alpha_on_tune_f1": {
                "tune_best_alpha": best_alpha,
                "tune_best_threshold_at_alpha": round(best_tune_thr, 4),
                "tune_best_f1": round(best_tune_f1, 4),
                "eval_at_tune_threshold": blend_eval_at_tune,
                "eval_in_sample_f1_optimal_at_alpha": round(blend_eval_in_sample_f1, 4),
                "in_sample_vs_holdout_f1_inflation_on_eval": round(
                    blend_eval_in_sample_f1 - blend_eval_at_tune["f1"], 4
                ),
                "eval_auc": blend_eval_auc,
                "eval_precision_at_recall_0.9": blend_eval_ops.get("precision_at_recall_0.9"),
                "eval_recall_at_precision_0.9": blend_eval_ops.get("recall_at_precision_0.9"),
                "eval_top_10_percent_lift": blend_eval_ops["lift_at_top_k"].get("top_10_percent"),
                "eval_tie_envelope": blend_eval_envelope,
                "gain_vs_judge_alone_eval_f1": round(
                    blend_eval_at_tune["f1"] - judge_eval_at_tune["f1"], 4
                ),
                "gain_vs_judge_alone_eval_auc": round(blend_eval_auc - judge_eval_auc, 4),
            },
            "blend_alpha_on_tune_auc": {
                "tune_best_alpha": auc_alpha,
                "tune_threshold_at_alpha_via_f1opt": round(auc_thr, 4),
                "tune_best_auc": round(auc_tune_auc, 4),
                "eval_at_tune_threshold": blend_auc_pick_eval_at_thr,
                "eval_auc": blend_auc_pick_eval_auc,
                "gain_vs_judge_alone_eval_f1": round(
                    blend_auc_pick_eval_at_thr["f1"] - judge_eval_at_tune["f1"], 4
                ),
                "gain_vs_judge_alone_eval_auc": round(blend_auc_pick_eval_auc - judge_eval_auc, 4),
            },
            "mean_ensemble_baseline": {
                "tune_threshold": round(
                    _f1_optimal_threshold(_blend(tune_s, tune_j, 0.5), tune_l)[0], 4
                ),
                "eval_at_tune_threshold": mean_eval_at_tune_thr,
                "gain_vs_judge_alone_eval_f1": round(
                    mean_eval_at_tune_thr["f1"] - judge_eval_at_tune["f1"], 4
                ),
            },
        }

    return {"label": label, **out}


def main() -> None:
    out: OrderedDict[str, Any] = OrderedDict()
    print()
    for corpus_dir, label in CORPORA:
        print(f"=== {label} (n=400, blend with holdout + tie envelope) ===")
        r = analyse_corpus(corpus_dir, label)
        out[corpus_dir] = r
        for judge_label, variant in r["variants"].items():
            jo = variant["judge_only"]
            bl_f1 = variant["blend_alpha_on_tune_f1"]
            bl_auc = variant["blend_alpha_on_tune_auc"]
            print(
                f"  {judge_label:6s} judge_alone eval F1={jo['eval_at_tune_threshold']['f1']:.3f}  AUC={jo['eval_auc']:.3f}"
            )
            print(
                f"          α-on-F1   α={bl_f1['tune_best_alpha']:.2f}  "
                f"eval F1={bl_f1['eval_at_tune_threshold']['f1']:.3f}  "
                f"AUC={bl_f1['eval_auc']:.3f}  "
                f"gain F1 {bl_f1['gain_vs_judge_alone_eval_f1']:+.3f}  "
                f"gain AUC {bl_f1['gain_vs_judge_alone_eval_auc']:+.3f}"
            )
            print(
                f"          α-on-AUC  α={bl_auc['tune_best_alpha']:.2f}  "
                f"eval F1={bl_auc['eval_at_tune_threshold']['f1']:.3f}  "
                f"AUC={bl_auc['eval_auc']:.3f}  "
                f"gain F1 {bl_auc['gain_vs_judge_alone_eval_f1']:+.3f}  "
                f"gain AUC {bl_auc['gain_vs_judge_alone_eval_auc']:+.3f}"
            )
        print()

    out_path = Path("benchmarks/external/substrate_plus_judge_holdout_n400_2026-05-19.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
