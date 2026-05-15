"""External validation: SummEval (Fabbri et al. 2021).

Second external corpus comparison. Compares Touchstone's signals
against MiniCheck on the SummEval corpus (mteb mirror, MIT). Each
article has 16 machine-generated summaries with a continuous
``consistency`` rating in ``[1, 5]`` aggregated from three
annotators; the rating measures factual consistency between the
summary and the article.

Two readout modes are reported:

- **AUC-ROC against a binarized label** (``consistency < 4`` =
  "not supported"). This is the same readout family as the RAGTruth
  Summary run, allowing cross-corpus comparison.
- **Spearman correlation against the continuous rating**. This
  captures information that binarization discards on a 5-point scale
  that is heavily skewed toward "supported".

Construct caveat: **MiniCheck (Tang et al. 2024) was trained on
LLM-AggreFact, which includes AggreFact-CNN derived from SummEval.**
The MiniCheck baseline on this corpus has seen the source articles
(though not necessarily the exact summaries) during training.
Touchstone has not been calibrated on any SummEval-derived data.

Corpus: ``mteb/summeval`` on the HF Hub (MIT). 100 CNN/DM articles,
each with 16 machine summaries and per-summary consistency ratings.

Baseline: MiniCheck Flan-T5-Large (Apache-2.0). The runner reuses
the model weights downloaded by the RAGTruth runner if present.

Run::

    pip install -e ".[external]"
    python -m benchmarks.external.summeval.run --output \\
        benchmarks/external/summeval/results/$(date +%F).json
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

from datasets import load_dataset  # noqa: E402

from clarethium_touchstone import measure  # noqa: E402


def auc_roc(scores: list[float], labels: list[int]) -> float:
    """AUC-ROC via Mann-Whitney U. Higher score = more likely positive."""
    pos = [s for s, lab in zip(scores, labels, strict=True) if lab == 1]
    neg = [s for s, lab in zip(scores, labels, strict=True) if lab == 0]
    if not pos or not neg:
        return 0.5
    concordant = 0
    ties = 0
    for p in pos:
        for n in neg:
            if p > n:
                concordant += 1
            elif p == n:
                ties += 1
    return (concordant + 0.5 * ties) / (len(pos) * len(neg))


def spearman_rho(x: list[float], y: list[float]) -> float:
    """Spearman rank correlation between two equal-length sequences.

    Handles ties via the conventional average-rank method. Returns
    Pearson correlation of the ranks. Returns 0.0 if either input is
    constant or empty.
    """
    if len(x) != len(y) or len(x) == 0:
        return 0.0

    def rank(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks

    rx = rank(list(x))
    ry = rank(list(y))
    n = len(rx)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry, strict=True))
    sx = (sum((a - mean_x) ** 2 for a in rx)) ** 0.5
    sy = (sum((b - mean_y) ** 2 for b in ry)) ** 0.5
    if sx == 0 or sy == 0:
        return 0.0
    return num / (sx * sy)


def touchstone_signals(text: str, source: str) -> dict[str, Any]:
    """Same five signals as the RAGTruth runner."""
    r = measure(text, source=source)
    sm = r["source_matching"]
    ep = r["entity_provenance"]
    vp = r["vocabulary_proximity"]
    qp = r["quality_profile"]
    gd = r["grounding_decomposition"]
    mean_proximity = vp["mean_proximity"]
    return {
        "layer4_unsourced_rate": sm["unsourced_rate"] if sm["n_total"] > 0 else None,
        "layer5_entity_unsourced_rate": (
            ep["entity_unsourced_rate"] if ep["n_entities"] >= 5 else None
        ),
        "layer6_inverse_proximity": (1.0 - mean_proximity if mean_proximity is not None else None),
        "layer10_gap": qp["gap"],
        "layer10_components_available": qp["components_available"],
        "layer11_p_proportion": gd["proportions"]["P"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, default=None, help="Cap (article, summary) pairs.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=4.0,
        help="Binarization threshold on consistency rating (< threshold = not-supported = positive class).",
    )
    parser.add_argument("--minicheck-model", default="flan-t5-large")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    print("[1/5] Loading mteb/summeval test split", flush=True)
    ds = load_dataset("mteb/summeval", split="test")
    # Flatten: each row has 16 machine_summaries with parallel consistency ratings.
    pairs: list[dict[str, Any]] = []
    for row in ds:
        article = row["text"]
        article_id = row["id"]
        for i, summary in enumerate(row["machine_summaries"]):
            consistency = float(row["consistency"][i])
            pairs.append(
                {
                    "article_id": article_id,
                    "summary_idx": i,
                    "context": article,
                    "output": summary,
                    "consistency": consistency,
                }
            )
    if args.limit:
        pairs = pairs[: args.limit]
    print(f"      n = {len(pairs)} (article, summary) pairs", flush=True)

    print("[2/5] Computing Touchstone signals", flush=True)
    t0 = time.perf_counter()
    ts_results: list[dict[str, Any]] = []
    for i, p in enumerate(pairs):
        ts_results.append(touchstone_signals(p["output"], p["context"]))
        if (i + 1) % 400 == 0:
            print(f"      {i + 1}/{len(pairs)} done", flush=True)
    ts_elapsed = time.perf_counter() - t0
    per_ex_ms = ts_elapsed / max(1, len(pairs)) * 1000
    print(f"      Touchstone: {ts_elapsed:.1f}s total ({per_ex_ms:.1f}ms/example)", flush=True)

    print(f"[3/5] Loading MiniCheck {args.minicheck_model} (CPU)", flush=True)
    from minicheck.minicheck import MiniCheck

    scorer = MiniCheck(
        model_name=args.minicheck_model,
        cache_dir="./ckpts_minicheck",
        enable_prefix_caching=False,
    )
    print(
        f"[4/5] Scoring with MiniCheck (~{len(pairs) * 2.4 / 60:.0f} min expected on CPU)",
        flush=True,
    )
    t0 = time.perf_counter()
    docs = [p["context"] for p in pairs]
    claims = [p["output"] for p in pairs]
    pred_labels, raw_probs, _, _ = scorer.score(docs=docs, claims=claims)
    mc_elapsed = time.perf_counter() - t0
    per_ex_s = mc_elapsed / max(1, len(pairs))
    print(f"      MiniCheck: {mc_elapsed:.1f}s total ({per_ex_s:.2f}s/example)", flush=True)

    print("[5/5] Computing AUCs + Spearman correlations", flush=True)

    # Binary label: consistency < threshold = "not supported" (positive class = 1).
    consistencies = [p["consistency"] for p in pairs]
    labels = [int(c < args.threshold) for c in consistencies]
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos

    aucs: dict[str, dict[str, Any]] = {}
    spearmans: dict[str, dict[str, Any]] = {}

    # MiniCheck: raw_prob = P(supported). Higher = more supported.
    # For AUC on "not-supported" positive class, score = (1 - raw_prob).
    # For Spearman vs continuous consistency, raw_prob (higher = more consistent)
    # should correlate POSITIVELY with consistency rating.
    mc_scores_for_auc = [1.0 - float(p) for p in raw_probs]
    mc_for_spearman = [float(p) for p in raw_probs]
    aucs["minicheck_flan_t5_large"] = {
        "auc_roc": round(auc_roc(mc_scores_for_auc, labels), 4),
        "n_used": len(labels),
    }
    spearmans["minicheck_flan_t5_large_raw_prob"] = {
        "spearman_rho": round(spearman_rho(mc_for_spearman, consistencies), 4),
        "n_used": len(consistencies),
        "direction_note": "MiniCheck raw_prob and SummEval consistency both increase with 'more supported' -> expect positive rho",
    }

    # Touchstone signals (oriented "higher = more hallucinated" -> negative rho with consistency).
    signal_keys = [
        "layer4_unsourced_rate",
        "layer5_entity_unsourced_rate",
        "layer6_inverse_proximity",
        "layer10_gap",
        "layer11_p_proportion",
    ]
    for key in signal_keys:
        usable_scores: list[float] = []
        usable_labels: list[int] = []
        usable_consistencies: list[float] = []
        for sig, lab, cval in zip(ts_results, labels, consistencies, strict=True):
            v = sig.get(key)
            if v is None:
                continue
            usable_scores.append(float(v))
            usable_labels.append(lab)
            usable_consistencies.append(cval)
        if not usable_scores:
            aucs[f"touchstone_{key}"] = {"auc_roc": None, "n_used": 0}
            spearmans[f"touchstone_{key}"] = {"spearman_rho": None, "n_used": 0}
            continue
        aucs[f"touchstone_{key}"] = {
            "auc_roc": round(auc_roc(usable_scores, usable_labels), 4),
            "n_used": len(usable_scores),
            "n_skipped_none": len(labels) - len(usable_scores),
        }
        spearmans[f"touchstone_{key}"] = {
            "spearman_rho": round(spearman_rho(usable_scores, usable_consistencies), 4),
            "n_used": len(usable_scores),
            "direction_note": "Touchstone signals oriented 'higher = more hallucinated' -> expect negative rho with consistency",
        }

    # Substance-component fire rate (the qualitative finding we want to verify).
    component_fires: dict[str, int] = defaultdict(int)
    for sig in ts_results:
        for c in cast(list[str], sig.get("layer10_components_available", [])):
            component_fires[c] += 1

    output = {
        "experiment": "SummEval external validation",
        "corpus": "mteb/summeval (test split, machine_summaries flattened)",
        "library": "clarethium-touchstone",
        "minicheck_model": args.minicheck_model,
        "binarization_threshold": args.threshold,
        "n_total_pairs": len(pairs),
        "n_articles": len(ds),
        "n_summaries_per_article": 16,
        "label_distribution": {
            "n_supported_consistency_ge_threshold": n_neg,
            "n_not_supported_consistency_lt_threshold": n_pos,
            "positive_rate": round(n_pos / max(1, len(labels)), 4),
        },
        "auc_roc_by_signal": aucs,
        "spearman_by_signal": spearmans,
        "layer10_substance_fire_rate": {
            k: f"{v}/{len(pairs)} ({v / max(1, len(pairs)) * 100:.1f}%)"
            for k, v in sorted(component_fires.items())
        },
        "training_test_leakage_caveat": (
            "MiniCheck Flan-T5-Large was trained on LLM-AggreFact, which "
            "includes AggreFact-CNN derived from SummEval. The MiniCheck "
            "baseline has seen the SummEval source distribution during "
            "training; absolute MiniCheck AUC on this corpus is not "
            "comparable to its AUC on a held-out corpus."
        ),
        "runtime_seconds": {
            "touchstone": round(ts_elapsed, 1),
            "minicheck": round(mc_elapsed, 1),
        },
    }

    output_str = json.dumps(output, indent=2, sort_keys=False)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_str)
        print(f"Wrote {out_path}", flush=True)
    else:
        print(output_str)


if __name__ == "__main__":
    main()
