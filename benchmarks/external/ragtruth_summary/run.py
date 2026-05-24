"""External validation: RAGTruth Summary corpus.

Compares Touchstone's signals against MiniCheck (Tang et al., EMNLP
2024) on the RAGTruth Summary test split. Both systems predict
whether an output is supported by its source context; ground truth
is the per-example ``hallucination_labels`` span list (empty -> the
output is supported; non-empty -> at least one annotated span of
hallucinated content).

This is the first external corpus comparison for Touchstone. Per
the Standard's falsifiable construct claim (Section 3.5), AUC-ROC
on this corpus speaks directly to whether the substrate generalizes
beyond the validated internal-corpus domain.

Corpus: ``wandb/RAGTruth-processed`` (MIT license; mirror of
RAGTruth, Wu et al. 2024). Streamed from HF Hub at runtime; no
corpus content is included in this repository.

Baseline: MiniCheck Flan-T5-Large (Liyan Tang, Philippe Laban,
Greg Durrett, "MiniCheck: Efficient Fact-Checking of LLMs on
Grounding Documents", EMNLP 2024). Apache-2.0; the runner downloads
the model on first run (~3 GB to ``./ckpts_minicheck/``).

Run::

    pip install -e ".[external]"
    python -m benchmarks.external.ragtruth_summary.run --output \\
        benchmarks/external/ragtruth_summary/results/$(date +%F).json

On CPU the full Summary test split (n=900) takes ~35 min;
``--limit N`` shortens for smoke testing.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

# CPU-only by default for cross-machine determinism. Comment to allow CUDA.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

from datasets import load_dataset  # noqa: E402

from clarethium_touchstone import measure  # noqa: E402


def has_hallucination(row: dict[str, Any]) -> bool:
    """Binary ground-truth: True if the row has any annotated hallucination span."""
    return len(json.loads(row["hallucination_labels"])) > 0


def auc_roc(scores: list[float], labels: list[int]) -> float:
    """Compute AUC-ROC via Mann-Whitney U.

    ``scores[i]`` is the model's score for example ``i``; higher
    indicates "more likely hallucinated". ``labels[i]`` is 1 for
    hallucinated, 0 for supported. Returns the probability that a
    random positive example outranks a random negative example. Ties
    contribute 0.5 each. Returns 0.5 if either class is empty.
    """
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


def balanced_accuracy(predictions: list[int], labels: list[int]) -> float:
    """Balanced accuracy: mean of per-class recall.

    ``predictions[i]`` and ``labels[i]`` are both 0/1 with 1 meaning
    hallucinated. Returns 0.5 if either class is empty.
    """
    tp = sum(1 for p, lab in zip(predictions, labels, strict=True) if p == 1 and lab == 1)
    fn = sum(1 for p, lab in zip(predictions, labels, strict=True) if p == 0 and lab == 1)
    tn = sum(1 for p, lab in zip(predictions, labels, strict=True) if p == 0 and lab == 0)
    fp = sum(1 for p, lab in zip(predictions, labels, strict=True) if p == 1 and lab == 0)
    if (tp + fn) == 0 or (tn + fp) == 0:
        return 0.5
    return 0.5 * (tp / (tp + fn) + tn / (tn + fp))


def touchstone_signals(text: str, source: str) -> dict[str, Any]:
    """Extract Touchstone signals oriented as "higher = more hallucinated".

    Signals returned:

    * ``layer4_unsourced_rate``: ``source_matching.unsourced_rate`` if
      the output has at least one digit-formatted number; else
      ``None`` (no signal).
    * ``layer5_entity_unsourced_rate``: same idea, gated on
      ``n_entities >= 5`` (Layer 5 precision threshold).
    * ``layer6_inverse_proximity``: ``1 - mean_proximity``; lower
      vocabulary overlap with the source increases the score.
    * ``layer10_gap``: ``quality_profile.gap``; positive gap means
      presentation exceeds substance (overclaiming).
    * ``layer11_p_proportion``: ``grounding_decomposition.proportions.P``.

    Each signal is paired with a precision flag so the aggregator can
    decide whether to include it.
    """
    r = measure(text, source=source)
    sm = r["source_matching"]
    ep = r["entity_provenance"]
    vp = r["vocabulary_proximity"]
    qp = r["quality_profile"]
    gd = r["grounding_decomposition"]

    mean_proximity = vp["mean_proximity"]
    return {
        "layer4_unsourced_rate": sm["unsourced_rate"] if sm["n_total"] > 0 else None,
        "layer4_n_total": sm["n_total"],
        "layer5_entity_unsourced_rate": (
            ep["entity_unsourced_rate"] if ep["n_entities"] >= 5 else None
        ),
        "layer5_n_entities": ep["n_entities"],
        "layer6_inverse_proximity": (1.0 - mean_proximity if mean_proximity is not None else None),
        "layer10_gap": qp["gap"],
        "layer10_components_available": qp["components_available"],
        "layer11_p_proportion": gd["proportions"]["P"],
        "layer11_n_sentences": gd["n_sentences"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of examples (for smoke testing).",
    )
    parser.add_argument(
        "--minicheck-model",
        default="flan-t5-large",
        help="MiniCheck model variant (default: flan-t5-large).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path. If omitted, the report prints to stdout.",
    )
    args = parser.parse_args()

    # ----- Load corpus -----
    print("[1/5] Loading wandb/RAGTruth-processed test split", flush=True)
    ds = load_dataset("wandb/RAGTruth-processed", split="test")
    summary = [r for r in ds if r["task_type"] == "Summary"]
    if args.limit:
        summary = summary[: args.limit]
    print(f"      n = {len(summary)} Summary examples", flush=True)

    # ----- Touchstone signals -----
    print("[2/5] Computing Touchstone signals", flush=True)
    t0 = time.perf_counter()
    ts_results: list[dict[str, Any]] = []
    for i, row in enumerate(summary):
        ts_results.append(touchstone_signals(row["output"], row["context"]))
        if (i + 1) % 200 == 0:
            print(f"      {i + 1}/{len(summary)} done", flush=True)
    ts_elapsed = time.perf_counter() - t0
    per_ex_ms = ts_elapsed / max(1, len(summary)) * 1000
    print(
        f"      Touchstone: {ts_elapsed:.1f}s total ({per_ex_ms:.1f}ms/example)",
        flush=True,
    )

    # ----- MiniCheck -----
    print(f"[3/5] Loading MiniCheck {args.minicheck_model} (CPU)", flush=True)
    from minicheck.minicheck import MiniCheck

    scorer = MiniCheck(
        model_name=args.minicheck_model,
        cache_dir="./ckpts_minicheck",
        enable_prefix_caching=False,
    )
    print(
        f"[4/5] Scoring with MiniCheck (~{len(summary) * 2.4 / 60:.0f} min expected on CPU)",
        flush=True,
    )
    t0 = time.perf_counter()
    docs = [r["context"] for r in summary]
    claims = [r["output"] for r in summary]
    pred_labels, raw_probs, _, _ = scorer.score(docs=docs, claims=claims)
    mc_elapsed = time.perf_counter() - t0
    per_ex_s = mc_elapsed / max(1, len(summary))
    print(
        f"      MiniCheck: {mc_elapsed:.1f}s total ({per_ex_s:.2f}s/example)",
        flush=True,
    )

    # ----- Aggregate -----
    print("[5/5] Computing AUCs and balanced accuracy", flush=True)
    labels = [int(has_hallucination(r)) for r in summary]

    aucs: dict[str, dict[str, Any]] = {}

    # MiniCheck: raw_prob = P(supported). For "higher = more hallucinated"
    # orientation, score is (1 - raw_prob).
    mc_scores = [1.0 - float(p) for p in raw_probs]
    mc_binary_preds = [int(1 - lab) for lab in pred_labels]
    aucs["minicheck_flan_t5_large"] = {
        "auc_roc": round(auc_roc(mc_scores, labels), 4),
        "balanced_accuracy_at_native_threshold": round(
            balanced_accuracy(mc_binary_preds, labels), 4
        ),
        "n_used": len(labels),
        "direction_note": ("AUC computed on (1 - raw_prob); raw_prob is MiniCheck's P(supported)"),
    }

    # Touchstone per-signal AUC. ``None`` signals are skipped.
    for signal_key in [
        "layer4_unsourced_rate",
        "layer5_entity_unsourced_rate",
        "layer6_inverse_proximity",
        "layer10_gap",
        "layer11_p_proportion",
    ]:
        usable_scores: list[float] = []
        usable_labels: list[int] = []
        for sig, lab in zip(ts_results, labels, strict=True):
            v = sig.get(signal_key)
            if v is None:
                continue
            usable_scores.append(float(v))
            usable_labels.append(lab)
        if not usable_scores:
            aucs[f"touchstone_{signal_key}"] = {
                "auc_roc": None,
                "n_used": 0,
                "n_skipped_none": len(labels),
            }
            continue
        aucs[f"touchstone_{signal_key}"] = {
            "auc_roc": round(auc_roc(usable_scores, usable_labels), 4),
            "n_used": len(usable_scores),
            "n_skipped_none": len(labels) - len(usable_scores),
        }

    # Per-model breakdown for the strongest Touchstone signal + MiniCheck.
    by_model_data: dict[str, dict[str, list[float] | list[int]]] = defaultdict(
        lambda: cast(
            "dict[str, list[float] | list[int]]",
            {
                "minicheck_scores": [],
                "layer11_p": [],
                "labels": [],
            },
        )
    )
    for row, sig, lab, mc in zip(summary, ts_results, labels, mc_scores, strict=True):
        cast(list, by_model_data[row["model"]]["minicheck_scores"]).append(mc)
        cast(list, by_model_data[row["model"]]["layer11_p"]).append(
            float(sig["layer11_p_proportion"])
        )
        cast(list, by_model_data[row["model"]]["labels"]).append(lab)

    by_model_out: dict[str, dict[str, Any]] = {}
    for model_name, d in sorted(by_model_data.items()):
        labs = cast(list[int], d["labels"])
        mcs = cast(list[float], d["minicheck_scores"])
        l11 = cast(list[float], d["layer11_p"])
        by_model_out[model_name] = {
            "n": len(labs),
            "n_hallucinated": sum(labs),
            "minicheck_auc": round(auc_roc(mcs, labs), 4),
            "touchstone_layer11_p_auc": round(auc_roc(l11, labs), 4),
        }

    output = {
        "experiment": "RAGTruth Summary external validation",
        "corpus": "wandb/RAGTruth-processed (test split, Summary task_type)",
        "library": "clarethium_touchstone",
        "minicheck_model": args.minicheck_model,
        "n_total": len(summary),
        "n_hallucinated": sum(labels),
        "n_supported": len(labels) - sum(labels),
        "hallucination_rate": round(sum(labels) / max(1, len(labels)), 4),
        "auc_roc_by_signal": aucs,
        "auc_roc_by_model": by_model_out,
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
