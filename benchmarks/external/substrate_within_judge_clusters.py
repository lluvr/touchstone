"""Measure the substrate's tie-breaking mechanism within judge score clusters.

§4.3 and §4.3.1 describe the substrate-plus-judge mechanism qualitatively:
"the substrate breaks ties within the judge's clustered scores."
That claim is plausible but unmeasured. If it is real, then *within* a
Grok-score cluster (e.g., all pairs the judge assigns 0.85), the
substrate's discriminative AUC over hallucinated-vs-faithful should be
> 0.5. If the substrate has no within-cluster signal, the mechanism
description is just plausible-sounding and the §4.3.1 HaluEval-blind
positive blend gain has a different explanation.

Method per corpus:
1. Load Grok blind per-example probabilities (the §4.2.8 judge column)
   and the substrate per-example probabilities (from
   substrate_only_n400 snapshots).
2. Identify the natural Grok-score clusters by histogramming with
   bin width 0.05 (Grok scores are observed to cluster at multiples
   of 0.05 on this prompt).
3. For each cluster with at least 20 pairs and at least 2 positives
   AND 2 negatives (so AUC is computable), compute substrate AUC on
   the within-cluster pairs.
4. Report: per-cluster (Grok-mid, n, n_pos, substrate AUC, label
   prevalence, substrate score range).

If substrate AUC > 0.55 within clusters where Grok was ambiguous
(e.g., 0.4-0.6), that's evidence of the tie-breaking mechanism. If
substrate AUC hovers around 0.5 within clusters, the mechanism is
unsupported by data and the §4.3.1 HaluEval gain has a different
explanation.

Run::

    python -m benchmarks.external.substrate_within_judge_clusters
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

from benchmarks.external._bootstrap import auc_roc

BASE = Path("benchmarks/external")
CORPORA = [
    ("ragtruth_summary", "RAGTruth Summary"),
    ("summeval", "SummEval"),
    ("halueval_summarization", "HaluEval Summarization"),
]
BIN_WIDTH = 0.05
MIN_CLUSTER_N = 20
MIN_CLASS = 2


def main() -> None:
    out: OrderedDict[str, object] = OrderedDict()
    for corpus_dir, label in CORPORA:
        base = BASE / corpus_dir / "results"
        sub = json.loads((base / "substrate_only_n400_2026-05-18.json").read_text())
        judge = json.loads((base / "judge_xai_grok420_blind_n400_2026-05-18.json").read_text())
        sub_p = sub["per_example_prob_hallucinated"]
        jud_p = judge["per_example_prob_hallucinated"]
        labels = sub["per_example_label_hallucinated"]
        if not (len(sub_p) == len(jud_p) == len(labels)):
            raise SystemExit(f"{corpus_dir}: length mismatch")

        # Bin pairs by Grok-blind probability with bin width 0.05.
        bins: dict[float, list[int]] = {}
        for i, jp in enumerate(jud_p):
            mid = round(jp / BIN_WIDTH) * BIN_WIDTH
            bins.setdefault(mid, []).append(i)

        cluster_rows = []
        for mid in sorted(bins):
            indices = bins[mid]
            if len(indices) < MIN_CLUSTER_N:
                continue
            cluster_labels = [labels[i] for i in indices]
            cluster_sub = [sub_p[i] for i in indices]
            n_pos = sum(cluster_labels)
            n_neg = len(cluster_labels) - n_pos
            if n_pos < MIN_CLASS or n_neg < MIN_CLASS:
                cluster_rows.append(
                    {
                        "judge_bin_mid": round(mid, 3),
                        "n_pairs": len(indices),
                        "n_positive": n_pos,
                        "n_negative": n_neg,
                        "substrate_auc": None,
                        "note": "skipped: <2 per class",
                        "substrate_score_range": [
                            round(min(cluster_sub), 4),
                            round(max(cluster_sub), 4),
                        ],
                    }
                )
                continue
            auc = auc_roc(cluster_sub, cluster_labels)
            cluster_rows.append(
                {
                    "judge_bin_mid": round(mid, 3),
                    "n_pairs": len(indices),
                    "n_positive": n_pos,
                    "n_negative": n_neg,
                    "label_prevalence": round(n_pos / len(indices), 4),
                    "substrate_auc": round(auc, 4),
                    "substrate_score_range": [
                        round(min(cluster_sub), 4),
                        round(max(cluster_sub), 4),
                    ],
                }
            )

        # Headline summary: weighted mean substrate AUC across clusters
        # where AUC was computable; weighted by cluster size.
        valid = [r for r in cluster_rows if r.get("substrate_auc") is not None]
        if valid:
            total_n = sum(r["n_pairs"] for r in valid)
            weighted_auc = sum(r["substrate_auc"] * r["n_pairs"] for r in valid) / total_n
            n_clusters_above_055 = sum(1 for r in valid if r["substrate_auc"] > 0.55)
            n_clusters_above_06 = sum(1 for r in valid if r["substrate_auc"] > 0.60)
        else:
            weighted_auc = None
            n_clusters_above_055 = 0
            n_clusters_above_06 = 0

        out[corpus_dir] = {
            "label": label,
            "n_total_pairs": len(labels),
            "judge": "xAI Grok 4.20 blind",
            "bin_width": BIN_WIDTH,
            "min_cluster_n": MIN_CLUSTER_N,
            "min_class": MIN_CLASS,
            "n_clusters_total": len(cluster_rows),
            "n_clusters_with_computable_auc": len(valid),
            "n_clusters_substrate_auc_above_0.55": n_clusters_above_055,
            "n_clusters_substrate_auc_above_0.60": n_clusters_above_06,
            "weighted_mean_within_cluster_substrate_auc": (
                round(weighted_auc, 4) if weighted_auc is not None else None
            ),
            "per_cluster": cluster_rows,
        }

        print(f"\n=== {label} ({len(labels)} pairs; judge=Grok blind; bin={BIN_WIDTH}) ===")
        print(
            f"{'bin_mid':>8s} {'n':>5s} {'n_pos':>5s} {'n_neg':>5s} "
            f"{'prev':>5s} {'sub_AUC':>8s}  sub_range"
        )
        for r in cluster_rows:
            if r.get("substrate_auc") is None:
                print(
                    f"{r['judge_bin_mid']:>8.3f} {r['n_pairs']:>5d} "
                    f"{r['n_positive']:>5d} {r['n_negative']:>5d}  -    -        skipped"
                )
            else:
                print(
                    f"{r['judge_bin_mid']:>8.3f} {r['n_pairs']:>5d} "
                    f"{r['n_positive']:>5d} {r['n_negative']:>5d} "
                    f"{r['label_prevalence']:>5.2f} {r['substrate_auc']:>8.3f}  "
                    f"{r['substrate_score_range']}"
                )
        if weighted_auc is not None:
            print(
                f"  weighted mean within-cluster substrate AUC: {weighted_auc:.4f}  "
                f"({len(valid)} clusters; {n_clusters_above_055} clusters > 0.55; "
                f"{n_clusters_above_06} > 0.60)"
            )

    out_path = Path("benchmarks/external/substrate_within_judge_clusters_2026-05-20.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
