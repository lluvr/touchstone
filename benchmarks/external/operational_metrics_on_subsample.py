"""Compute operational metrics on the n=400 subsample of each corpus,
with all four detectors scored on the same indices.

The companion ``operational_metrics.py`` script computes metrics on
the canonical full-N MiniCheck/AlignScore/trivial-baseline snapshots.
This sister script narrows to the n=400 subsample produced by
``subsample_pairs.py`` and adds the xAI Grok judge row, so all four
detectors (substrate L6 / MiniCheck / AlignScore / Grok) are compared
on identical pair indices.

The full-N tables in ``production_readiness.md`` §2 remain the
canonical operational reference. This script's output is the
apples-to-apples cross-detector view including the frontier judge,
sized for budget (1200 judge calls instead of 3500).

Run::

    python -m benchmarks.external.operational_metrics_on_subsample
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from benchmarks.external.operational_metrics import _ops_metrics

BASE = Path("benchmarks/external")

CORPORA = [
    (
        "ragtruth_summary",
        "RAGTruth Summary",
        "results/judge_xai_grok420_n400_2026-05-18.json",
    ),
    (
        "summeval",
        "SummEval",
        "results/judge_xai_grok420_n400_2026-05-18.json",
    ),
    (
        "halueval_summarization",
        "HaluEval Summarization",
        "results/judge_xai_grok420_n400_2026-05-18.json",
    ),
]


def _select(values: list, indices: list[int]) -> list:
    return [values[i] for i in indices]


def _load_detector_scores_on_subsample(
    corpus_dir: str, judge_snapshot_rel: str
) -> tuple[list[int], OrderedDict[str, list[float]]]:
    """Return (labels, {detector_name: scores}) where every score
    array is aligned to the subsample indices for this corpus and
    higher means more likely hallucinated.
    """
    base = BASE / corpus_dir / "results"

    idx_path = base / "subsample_n400_indices_2026-05-18.json"
    idx_doc = json.loads(idx_path.read_text())
    indices = idx_doc["indices_in_original"]
    labels = idx_doc["labels"]

    # Substrate (L6 word-overlap inverse, the strongest trivial lexical
    # baseline and the substrate-comparable row used in production
    # readiness §2).
    tb_path = base / "trivial_lexical_baselines_2026-05-17.json"
    tb_doc = json.loads(tb_path.read_text())
    substrate_full = tb_doc["per_example_scores"]["word_overlap_inv"]
    substrate = _select(substrate_full, indices)

    # MiniCheck (raw prob is P(supported), invert).
    mc_path = base / "minicheck_with_cis_2026-05-16.json"
    mc_doc = json.loads(mc_path.read_text())
    minicheck_full = [1.0 - p for p in mc_doc["per_example_raw_prob_supported"]]
    minicheck = _select(minicheck_full, indices)

    # AlignScore (raw is P(supported), invert).
    as_path = base / "alignscore_baseline_2026-05-15.json"
    as_doc = json.loads(as_path.read_text())
    alignscore_full = [1.0 - p for p in as_doc["per_example_raw_score_supported"]]
    alignscore = _select(alignscore_full, indices)

    # Judge variants (raw is P(hallucinated), no inversion).
    judge_paths = {
        "xAI Grok 4.20 cued": "judge_xai_grok420_n400_2026-05-18.json",
        "xAI Grok 4.20 blind": "judge_xai_grok420_blind_n400_2026-05-18.json",
        "Anthropic Claude Sonnet 4.6 cued": "judge_anthropic_sonnet_46_cued_n400_2026-05-19.json",
        "Anthropic Claude Sonnet 4.6 blind": "judge_anthropic_sonnet_46_blind_n400_2026-05-19.json",
    }
    judges: dict[str, list[float]] = {}
    for name, rel in judge_paths.items():
        path = base / rel
        if not path.exists():
            # Skip judges whose snapshot hasn't been produced yet (e.g.
            # OpenAI judge pending the vault token fix); the rest still
            # form a valid cross-detector comparison.
            continue
        arr = json.loads(path.read_text())["per_example_prob_hallucinated"]
        if len(arr) != len(indices):
            raise SystemExit(
                f"{corpus_dir}: {name} snapshot has {len(arr)} scores, "
                f"expected {len(indices)} (judge was run on the subsample)."
            )
        judges[name] = arr

    detectors: OrderedDict[str, list[float]] = OrderedDict()
    detectors["Touchstone substrate L6 (word_overlap_inv)"] = substrate
    detectors["MiniCheck Flan-T5-Large"] = minicheck
    detectors["AlignScore-base"] = alignscore
    for name, arr in judges.items():
        detectors[name] = arr
    return labels, detectors


def main() -> None:
    out: OrderedDict[str, Any] = OrderedDict()
    for corpus_dir, label, judge_snap_rel in CORPORA:
        print(f"\n=== {label} (n=400 subsample) ===")
        labels, detectors = _load_detector_scores_on_subsample(corpus_dir, judge_snap_rel)
        per_detector: OrderedDict[str, Any] = OrderedDict()
        for name, scores in detectors.items():
            m = _ops_metrics(scores, labels)
            per_detector[name] = m
            if "error" in m:
                print(f"  {name}: {m['error']}")
                continue
            f1opt = m["f1_optimal"]
            p_r90 = m["precision_at_recall_0.9"]
            r_p90 = m["recall_at_precision_0.9"]
            top10 = m["lift_at_top_k"].get("top_10_percent")
            print(
                f"  {name:42s}  base_rate {m['base_rate']:.2f}  "
                f"F1-opt {f1opt['f1']:.3f}  "
                f"P@R90 {p_r90['precision']:.3f}"
                if p_r90
                else f"  {name:42s}  base_rate {m['base_rate']:.2f}  "
                f"F1-opt {f1opt['f1']:.3f}  P@R90 n/a"
            )
            if r_p90:
                print(
                    f"    R@P90 {r_p90['recall']:.3f} (catches {r_p90['tp']}/{m['n_positive']})  "
                    f"top10 lift {top10['lift_vs_random']:.2f}x"
                    if top10
                    else ""
                )
            elif top10:
                print(f"    R@P90 n/a  top10 lift {top10['lift_vs_random']:.2f}x")
        out[corpus_dir] = {
            "label": label,
            "n_subsample": len(labels),
            "n_positive": sum(labels),
            "n_negative": len(labels) - sum(labels),
            "base_rate": round(sum(labels) / len(labels), 4),
            "per_detector": per_detector,
        }

    out_path = Path("benchmarks/external/operational_metrics_n400_2026-05-18.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
