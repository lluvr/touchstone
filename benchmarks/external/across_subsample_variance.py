"""Across-subsample variance for the n=400 cross-detector metrics.

§4.2's caveats list flagged that the bootstrap CI on AUC ±~0.04 is a
within-sample uncertainty: it re-resamples the same 400 rows with
replacement. The across-sample variance — what happens if we draw a
DIFFERENT 400-row prefix from the full corpus — is not captured by
that bootstrap. This script measures it directly.

For each corpus, K=10 prefix offsets are taken (evenly spaced across
the corpus length minus 400), and for each offset the substrate /
MiniCheck / AlignScore F1-optimal, AUC, P@R90, R@P90, and top-10%
lift are recomputed. The Grok column was only run on offset=0
(existing snapshot); its across-sample variance cannot be measured
without K-1 additional judge calls (~3500 calls at ~$50 each;
deferred per the §7 carried-forward list). The Grok numbers are
included once at offset=0 as reference.

The mean ± std across K=10 offsets is the across-sample variance
estimate. If std is small (≪ within-sample ±0.04), the n=400
prefix at offset=0 is representative. If std is large, the §4.2
headline tables depend on the prefix choice and should be cited
with the across-sample envelope.

Run::

    python -m benchmarks.external.across_subsample_variance
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from pathlib import Path
from typing import Any

from benchmarks.external.operational_metrics import _ops_metrics

N_TOTAL = 400
K_OFFSETS = 10

CORPORA = [
    ("ragtruth_summary", "RAGTruth Summary", 900),
    ("summeval", "SummEval", 1600),
    ("halueval_summarization", "HaluEval Summarization", 1000),
]


def _mean_std(xs: list[float]) -> tuple[float, float]:
    if not xs:
        return float("nan"), float("nan")
    mu = sum(xs) / len(xs)
    var = sum((x - mu) ** 2 for x in xs) / max(1, len(xs) - 1)
    return mu, math.sqrt(var)


def _evenly_spaced_offsets(full_n: int, window: int, k: int) -> list[int]:
    """K evenly-spaced starting offsets so each window of length 'window' fits in [0, full_n)."""
    max_offset = full_n - window
    if max_offset < 0:
        raise ValueError(f"window {window} > full_n {full_n}")
    if k == 1:
        return [0]
    step = max_offset / (k - 1)
    return [int(round(i * step)) for i in range(k)]


def _load_full_n_scores(corpus_dir: str, full_n: int) -> tuple[list[int], dict[str, list[float]]]:
    """Load substrate L6 / MiniCheck / AlignScore full-N arrays and the label array.
    Labels come from the n=400 indices snapshot (which carries them at offset=0);
    for non-zero offsets we need labels from the pair JSON, but the labels are
    the same across offsets — what changes is which contiguous slice we take."""
    base = Path(f"benchmarks/external/{corpus_dir}/results")

    tb = json.loads((base / "trivial_lexical_baselines_2026-05-17.json").read_text())
    substrate = tb["per_example_scores"]["word_overlap_inv"]
    assert len(substrate) == full_n, f"{corpus_dir} substrate: {len(substrate)} != {full_n}"

    mc = json.loads((base / "minicheck_with_cis_2026-05-16.json").read_text())
    minicheck = [1.0 - p for p in mc["per_example_raw_prob_supported"]]
    assert len(minicheck) == full_n, f"{corpus_dir} minicheck: {len(minicheck)} != {full_n}"

    al = json.loads((base / "alignscore_baseline_2026-05-15.json").read_text())
    alignscore = [1.0 - p for p in al["per_example_raw_score_supported"]]
    assert len(alignscore) == full_n, f"{corpus_dir} alignscore: {len(alignscore)} != {full_n}"

    # Labels: pull from the n=400 indices snapshot (these are the first-400 labels);
    # for the full-N label array we need a separate source. The minicheck snapshot
    # carries per_example_label_hallucinated for the full corpus.
    labels = mc["per_example_label_hallucinated"]
    assert len(labels) == full_n

    return labels, {
        "Touchstone substrate L6 (word_overlap_inv)": substrate,
        "MiniCheck Flan-T5-Large": minicheck,
        "AlignScore-base": alignscore,
    }


def main() -> None:
    out: OrderedDict[str, Any] = OrderedDict()
    print()
    for corpus_dir, label, full_n in CORPORA:
        offsets = _evenly_spaced_offsets(full_n, N_TOTAL, K_OFFSETS)
        print(f"=== {label} (full N={full_n}, K={K_OFFSETS} offsets {offsets}) ===")
        all_labels, detectors = _load_full_n_scores(corpus_dir, full_n)
        per_detector: OrderedDict[str, Any] = OrderedDict()
        for name, full_scores in detectors.items():
            f1opt_vals: list[float] = []
            pr90_vals: list[float] = []
            rp90_vals: list[float] = []
            top10_vals: list[float] = []
            base_rate_vals: list[float] = []
            per_offset_rows: list[dict[str, Any]] = []
            for off in offsets:
                sl_scores = full_scores[off : off + N_TOTAL]
                sl_labels = all_labels[off : off + N_TOTAL]
                m = _ops_metrics(sl_scores, sl_labels)
                if "error" in m:
                    continue
                f1opt_vals.append(m["f1_optimal"]["f1"])
                pr = m.get("precision_at_recall_0.9")
                if pr:
                    pr90_vals.append(pr["precision"])
                rp = m.get("recall_at_precision_0.9")
                if rp:
                    rp90_vals.append(rp["recall"])
                top10 = m["lift_at_top_k"].get("top_10_percent")
                if top10:
                    top10_vals.append(top10["lift_vs_random"])
                base_rate_vals.append(m["base_rate"])
                per_offset_rows.append(
                    {
                        "offset": off,
                        "base_rate": m["base_rate"],
                        "f1_optimal": m["f1_optimal"]["f1"],
                        "precision_at_recall_0.9": (pr or {}).get("precision"),
                        "recall_at_precision_0.9": (rp or {}).get("recall"),
                        "top_10_percent_lift": (top10 or {}).get("lift_vs_random"),
                    }
                )
            f1_mu, f1_sd = _mean_std(f1opt_vals)
            pr_mu, pr_sd = _mean_std(pr90_vals) if pr90_vals else (float("nan"), float("nan"))
            rp_mu, rp_sd = _mean_std(rp90_vals) if rp90_vals else (float("nan"), float("nan"))
            top10_mu, top10_sd = (
                _mean_std(top10_vals) if top10_vals else (float("nan"), float("nan"))
            )
            br_mu, br_sd = _mean_std(base_rate_vals)
            per_detector[name] = {
                "k_offsets": K_OFFSETS,
                "offsets": offsets,
                "base_rate_mean": round(br_mu, 4),
                "base_rate_std": round(br_sd, 4),
                "f1_optimal_mean": round(f1_mu, 4),
                "f1_optimal_std": round(f1_sd, 4),
                "precision_at_recall_0.9_mean": round(pr_mu, 4),
                "precision_at_recall_0.9_std": round(pr_sd, 4),
                "recall_at_precision_0.9_mean": round(rp_mu, 4),
                "recall_at_precision_0.9_std": round(rp_sd, 4),
                "top_10_percent_lift_mean": round(top10_mu, 4),
                "top_10_percent_lift_std": round(top10_sd, 4),
                "per_offset": per_offset_rows,
            }
            print(
                f"  {name:42s}  "
                f"F1={f1_mu:.3f}±{f1_sd:.3f}  "
                f"P@R90={pr_mu:.3f}±{pr_sd:.3f}  "
                f"R@P90={rp_mu:.3f}±{rp_sd:.3f}  "
                f"top10={top10_mu:.2f}x±{top10_sd:.2f}  "
                f"(base_rate={br_mu:.3f}±{br_sd:.3f})"
            )
        out[corpus_dir] = {
            "label": label,
            "full_n": full_n,
            "window": N_TOTAL,
            "k_offsets": K_OFFSETS,
            "offsets": offsets,
            "judge_gap_note": (
                "Grok column not in this table; only offset=0 has a judge snapshot. "
                "Across-sample variance for the judge would require K-1 additional API "
                "runs; deferred per §7."
            ),
            "per_detector": per_detector,
        }
        print()
    out_path = Path("benchmarks/external/across_subsample_variance_n400_2026-05-19.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
