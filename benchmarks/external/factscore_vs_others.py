"""Compare FactScore-class baseline against the other §4.2 detectors on n=400 subsamples.

Loads the FactScore snapshot per corpus alongside the existing
substrate / MiniCheck / AlignScore / Grok cued / Grok blind / Claude
cued / Claude blind / GPT-4o cued / GPT-5-mini cued snapshots, then
prints a per-corpus comparison table of:

- AUC + 95% bootstrap CI
- F1-optimal threshold + precision/recall
- Precision at recall >= 0.9
- Recall at precision >= 0.9
- Per-example latency (seconds) when available
- Per-example cost (USD) when available

MiniCheck and AlignScore snapshots are computed on the FULL n
(1600/1000/900); they are restricted to the n=400 subsample via the
``subsample_n400_indices_2026-05-18.json`` files so the comparison
is apples-to-apples with the n=400 judge / FactScore / substrate
snapshots.

Pure-python; reuses ``_bootstrap.py`` and the per-row metric logic
from ``operational_metrics.py``.

Usage::

    python -m benchmarks.external.factscore_vs_others \\
        --output benchmarks/external/factscore_comparison_2026-05-20.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import auc_roc, bootstrap_auc_ci  # noqa: E402
from operational_metrics import _ops_metrics  # noqa: E402

BASE = Path("benchmarks/external")

CORPORA = [
    ("summeval", "SummEval"),
    ("halueval_summarization", "HaluEval Summarization"),
    ("ragtruth_summary", "RAGTruth Summary"),
]


def _load_subsample(corpus_dir: str) -> dict[str, Any]:
    return json.loads(
        (BASE / corpus_dir / "results" / "subsample_n400_indices_2026-05-18.json").read_text()
    )


def _maybe(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text()) if path.exists() else None


def _restrict(scores: list[float], labels_full: list[int], idx: list[int]) -> list[float]:
    return [scores[i] for i in idx]


def _load_detector_scores(corpus_dir: str) -> dict[str, dict[str, Any]]:
    """Return system_name -> {scores, labels, latency_per_ex_s, cost_per_ex_usd}.

    Higher score = more likely hallucinated. Latency / cost are optional.
    """
    sub = _load_subsample(corpus_dir)
    sub_idx = sub["indices_in_original"]
    sub_lab = sub["labels"]

    results: dict[str, dict[str, Any]] = OrderedDict()

    base = BASE / corpus_dir / "results"

    # Substrate-only (already on n=400 indices).
    d = _maybe(base / "substrate_only_n400_2026-05-18.json")
    if d:
        results["substrate_only"] = {
            "scores": list(d["per_example_prob_hallucinated"]),
            "labels": list(sub_lab),
            "latency_per_ex_s": None,
            "cost_per_ex_usd": 0.0,
            "_kind": "substrate",
        }

    # MiniCheck (on full n => restrict).
    d = _maybe(base / "minicheck_with_cis_2026-05-16.json")
    if d:
        full_p = d["per_example_raw_prob_supported"]
        full_l = d["per_example_label_hallucinated"]
        rs_p = _restrict(full_p, full_l, sub_idx)
        rs_l = _restrict(full_l, full_l, sub_idx)
        assert rs_l == sub_lab, f"{corpus_dir}: minicheck subsample label mismatch"
        results["minicheck_flan_t5_large"] = {
            "scores": [1.0 - p for p in rs_p],  # invert (raw is P(supported))
            "labels": rs_l,
            "latency_per_ex_s": None,
            "cost_per_ex_usd": 0.0,
            "_kind": "encoder",
        }

    # AlignScore (on full n => restrict).
    d = _maybe(base / "alignscore_baseline_2026-05-15.json")
    if d:
        full_p = d["per_example_raw_score_supported"]
        full_l = d["per_example_label"]
        rs_p = _restrict(full_p, full_l, sub_idx)
        rs_l = _restrict(full_l, full_l, sub_idx)
        assert rs_l == sub_lab, f"{corpus_dir}: alignscore subsample label mismatch"
        results["alignscore_base"] = {
            "scores": [1.0 - p for p in rs_p],
            "labels": rs_l,
            "latency_per_ex_s": None,
            "cost_per_ex_usd": 0.0,
            "_kind": "encoder",
        }

    # Judge snapshots are already on n=400 indices.
    judge_specs = [
        ("judge_xai_grok420_n400_2026-05-18.json", "grok_cued"),
        ("judge_xai_grok420_blind_n400_2026-05-18.json", "grok_blind"),
        ("judge_anthropic_sonnet_46_cued_n400_2026-05-19.json", "claude_sonnet46_cued"),
        ("judge_anthropic_sonnet_46_blind_n400_2026-05-19.json", "claude_sonnet46_blind"),
        ("judge_openai_gpt4o_cued_n400_2026-05-19.json", "gpt4o_cued"),
        ("judge_openai_gpt5_mini_cued_n400_2026-05-19.json", "gpt5_mini_cued"),
        ("judge_openai_gpt5_mini_blind_n400_2026-05-19.json", "gpt5_mini_blind"),
    ]
    for fname, name in judge_specs:
        d = _maybe(base / fname)
        if d and "per_example_prob_hallucinated" in d:
            results[name] = {
                "scores": list(d["per_example_prob_hallucinated"]),
                "labels": list(d.get("per_example_label_hallucinated", sub_lab)),
                "latency_per_ex_s": None,
                "cost_per_ex_usd": None,
                "_kind": "judge",
            }

    # FactScore (this one is the new baseline).
    d = _maybe(base / "factscore_grok_n400_2026-05-19.json")
    if d:
        latency = d.get("per_example_seconds_mean")
        cost_total = d.get("runtime_cost_usd_estimate")
        n_total = d.get("n_total_pairs", 400)
        cost_per_ex = (cost_total / n_total) if (cost_total and n_total) else None
        results["factscore_grok"] = {
            "scores": list(d["per_example_factscore"]),
            "labels": list(d["per_example_label_hallucinated"]),
            "latency_per_ex_s": latency,
            "cost_per_ex_usd": cost_per_ex,
            "_kind": "decomposition_judge",
            "_aux": {
                "median_claims_per_output": _median(d.get("per_example_n_claims", [])),
                "mean_claims_per_output": _mean(d.get("per_example_n_claims", [])),
                "n_total_calls": (d.get("runtime_usage_totals") or {}).get("n_calls", None),
            },
        }
    return results


def _median(xs: list[int]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return float(s[n // 2]) if n % 2 == 1 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def _mean(xs: list[int]) -> float | None:
    return (sum(xs) / len(xs)) if xs else None


def _row_for(name: str, sd: dict[str, Any]) -> dict[str, Any]:
    scores = sd["scores"]
    labels = sd["labels"]
    ci = bootstrap_auc_ci(scores, labels, n_resamples=1000, seed=0)
    auc_pt = auc_roc(scores, labels)
    ops = _ops_metrics(scores, labels)
    row = {
        "system": name,
        "kind": sd.get("_kind"),
        "auc": round(auc_pt, 4),
        "auc_ci_low": ci["ci_low"],
        "auc_ci_high": ci["ci_high"],
        "f1_optimal": ops.get("f1_optimal"),
        "precision_at_recall_0.9": ops.get("precision_at_recall_0.9"),
        "recall_at_precision_0.9": ops.get("recall_at_precision_0.9"),
        "latency_per_ex_s": sd.get("latency_per_ex_s"),
        "cost_per_ex_usd": sd.get("cost_per_ex_usd"),
    }
    if "_aux" in sd:
        row["aux"] = sd["_aux"]
    return row


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--output", required=False, default=None)
    args = p.parse_args()

    summary: OrderedDict[str, Any] = OrderedDict()
    for corpus_dir, label in CORPORA:
        print(f"\n=== {label} ===")
        per_system = _load_detector_scores(corpus_dir)
        rows = [_row_for(name, sd) for name, sd in per_system.items()]
        summary[corpus_dir] = rows
        header = (
            f"  {'system':28s}  {'AUC':>6s}  {'CI':>15s}  "
            f"{'F1opt':>6s}  {'P@R90':>6s}  {'R@P90':>6s}  {'lat/ex':>8s}  {'$/ex':>8s}"
        )
        print(header)
        for r in rows:
            f1opt = (r["f1_optimal"] or {}).get("f1")
            p_r90 = (r["precision_at_recall_0.9"] or {}).get("precision")
            r_p90 = (r["recall_at_precision_0.9"] or {}).get("recall")
            lat = r.get("latency_per_ex_s")
            cost = r.get("cost_per_ex_usd")
            ci_str = f"[{r['auc_ci_low']:.3f},{r['auc_ci_high']:.3f}]"
            print(
                f"  {r['system']:28s}  {r['auc']:.4f}  {ci_str:>15s}  "
                f"{(f'{f1opt:.3f}' if f1opt is not None else '   -  '):>6s}  "
                f"{(f'{p_r90:.3f}' if p_r90 is not None else '   -  '):>6s}  "
                f"{(f'{r_p90:.3f}' if r_p90 is not None else '   -  '):>6s}  "
                f"{(f'{lat:.2f}s' if lat is not None else '       -'):>8s}  "
                f"{(f'${cost:.4f}' if cost is not None else '       -'):>8s}"
            )

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2))
        print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
