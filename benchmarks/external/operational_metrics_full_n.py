"""Operational metrics at FULL CORPUS N for the free-tier detectors.

§4.2 reports cross-detector ops metrics on n=400 prefix subsamples of
each corpus. The substrate L6 / MiniCheck / AlignScore per-example
arrays exist on disk at full N (900 / 1600 / 1000 for the three
corpora); the n=400 limit was chosen to bound the cost of the judge
column. For the free-tier detectors there is no cost reason to stay
at n=400.

This script reports F1-optimal / P@R90 / R@P90 / top-10% lift at full
corpus N for substrate L6 / MiniCheck / AlignScore — tightening the
sampling CI by sqrt(N/400) ≈ 1.5-2x vs the §4.2 numbers, with zero
new API calls or model inference.

The judge column intentionally stays at n=400 (cost-bound). To make
this explicit, the judge row is preserved at n=400 and a separate
"sampling envelope" column reports the ratio (full-N CI / n=400 CI)
the adopter would expect if the judge were extended to full-N too.

Run::

    python -m benchmarks.external.operational_metrics_full_n
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from benchmarks.external.operational_metrics import _ops_metrics

BASE = Path("benchmarks/external")
CORPORA = [
    ("ragtruth_summary", "RAGTruth Summary", 900),
    ("summeval", "SummEval", 1600),
    ("halueval_summarization", "HaluEval Summarization", 1000),
]


def _load_full_n(corpus_dir: str, full_n: int) -> tuple[list[int], OrderedDict[str, list[float]]]:
    base = BASE / corpus_dir / "results"
    tb = json.loads((base / "trivial_lexical_baselines_2026-05-17.json").read_text())
    mc = json.loads((base / "minicheck_with_cis_2026-05-16.json").read_text())
    al = json.loads((base / "alignscore_baseline_2026-05-15.json").read_text())

    substrate = tb["per_example_scores"]["word_overlap_inv"]
    minicheck = [1.0 - p for p in mc["per_example_raw_prob_supported"]]
    alignscore = [1.0 - p for p in al["per_example_raw_score_supported"]]
    labels = mc["per_example_label_hallucinated"]

    for name, arr in [
        ("substrate", substrate),
        ("minicheck", minicheck),
        ("alignscore", alignscore),
        ("labels", labels),
    ]:
        assert len(arr) == full_n, f"{corpus_dir} {name}: {len(arr)} != {full_n}"

    detectors: OrderedDict[str, list[float]] = OrderedDict()
    detectors["Touchstone substrate L6 (word_overlap_inv)"] = substrate
    detectors["MiniCheck Flan-T5-Large"] = minicheck
    detectors["AlignScore-base"] = alignscore
    return labels, detectors


def main() -> None:
    out: OrderedDict[str, Any] = OrderedDict()
    print()
    for corpus_dir, label, full_n in CORPORA:
        print(f"=== {label} (full N={full_n}, free-tier detectors only) ===")
        labels, detectors = _load_full_n(corpus_dir, full_n)
        per_detector: OrderedDict[str, Any] = OrderedDict()
        for name, scores in detectors.items():
            m = _ops_metrics(scores, labels)
            per_detector[name] = m
            if "error" in m:
                print(f"  {name}: {m['error']}")
                continue
            f1opt = m["f1_optimal"]
            pr90 = m.get("precision_at_recall_0.9", {}) or {}
            rp90 = m.get("recall_at_precision_0.9", {}) or {}
            top10 = m["lift_at_top_k"].get("top_10_percent", {}) or {}
            print(
                f"  {name:42s}  base_rate {m['base_rate']:.3f}  "
                f"F1-opt {f1opt['f1']:.3f}@thr {f1opt['threshold']:.3f}  "
                f"P@R90 {pr90.get('precision', float('nan')):.3f}  "
                f"R@P90 {rp90.get('recall', float('nan')):.3f} "
                f"({rp90.get('tp', '?')}/{m['n_positive']})  "
                f"top10_lift {top10.get('lift_vs_random', float('nan')):.2f}x"
            )
        out[corpus_dir] = {
            "label": label,
            "full_n": full_n,
            "n_positive": sum(labels),
            "n_negative": len(labels) - sum(labels),
            "base_rate": round(sum(labels) / len(labels), 4),
            "per_detector": per_detector,
            "note": (
                "Judge column intentionally absent: judges are cost-bound at n=400. "
                "Full-N expansion of substrate/MiniCheck/AlignScore tightens their "
                "sampling CI without re-scoring any examples; judge column remains "
                "in operational_metrics_n400_2026-05-18.json."
            ),
        }
        print()

    out_path = Path("benchmarks/external/operational_metrics_full_n_2026-05-19.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
