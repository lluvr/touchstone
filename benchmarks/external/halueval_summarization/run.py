"""External validation: HaluEval summarization subset.

Third external corpus comparison. Compares Touchstone's signals
against MiniCheck (Tang et al. EMNLP 2024) on the HaluEval
summarization corpus (Li et al. EMNLP 2023).

HaluEval was constructed by sampling summaries from CNN/DM and
using ChatGPT to synthesize hallucinated variants. Each example
pairs a CNN/DM article with two summaries on it: a ``right_summary``
(real CNN/DM training-set summary) and a ``hallucinated_summary``
(ChatGPT-synthesized variant with intentionally introduced errors).
This is an adversarially-constructed corpus, not in-the-wild
hallucination data. Touchstone's signal may capture synthetic-vs-real
distributional differences in addition to the construct of interest;
this is documented as a caveat.

Two readouts are reported:

- **AUC-ROC**, with the binary label "1 = hallucinated, 0 = right".
- **Per-document accuracy of ranking** (does the signal rank the
  right_summary higher in supported-ness than the hallucinated
  variant on the same document?). This pair-internal readout
  bypasses any synthetic-vs-real distributional confound; it is
  the natural metric for HaluEval's construction.

Corpus: ``pminervini/HaluEval`` on the HF Hub (Apache-2.0). 10000
(article, right_summary, hallucinated_summary) triplets.

This runner subsets to a stratified random sample of 500 documents
(yielding 1000 (article, summary, label) pairs, 500 right + 500
hallucinated) for tractable CPU runtime. Seed is fixed for
reproducibility.

Run::

    pip install -e ".[external]"
    python -m benchmarks.external.halueval_summarization.run --output \\
        benchmarks/external/halueval_summarization/results/$(date +%F).json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path
from typing import Any

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


def touchstone_signals(text: str, source: str) -> dict[str, Any]:
    """Same five signals as the prior external runners."""
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
        "layer11_p_proportion": gd["proportions"]["P"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--n-documents",
        type=int,
        default=500,
        help="Number of documents to sample (each contributes one right + one hallucinated summary).",
    )
    parser.add_argument("--seed", type=int, default=0, help="Random seed for sampling.")
    parser.add_argument(
        "--limit", type=int, default=None, help="Cap total (doc, summary) pairs for smoke testing."
    )
    parser.add_argument("--minicheck-model", default="flan-t5-large")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    print("[1/5] Loading pminervini/HaluEval summarization subset", flush=True)
    ds = load_dataset("pminervini/HaluEval", "summarization", split="data")
    print(f"      Full corpus: {len(ds)} documents", flush=True)

    rng = random.Random(args.seed)
    indices = rng.sample(range(len(ds)), min(args.n_documents, len(ds)))
    sampled = [ds[i] for i in indices]
    print(f"      Sampled: {len(sampled)} documents (seed={args.seed})", flush=True)

    # Flatten: each document yields (article, right_summary, 0) and (article, hallucinated_summary, 1).
    pairs: list[dict[str, Any]] = []
    for doc_idx, row in enumerate(sampled):
        pairs.append(
            {
                "doc_idx": doc_idx,
                "context": row["document"],
                "output": row["right_summary"],
                "label": 0,
                "kind": "right",
            }
        )
        pairs.append(
            {
                "doc_idx": doc_idx,
                "context": row["document"],
                "output": row["hallucinated_summary"],
                "label": 1,
                "kind": "hallucinated",
            }
        )
    if args.limit:
        pairs = pairs[: args.limit]
    n_right = sum(1 for p in pairs if p["label"] == 0)
    n_halluc = sum(1 for p in pairs if p["label"] == 1)
    print(f"      Total pairs: {len(pairs)} (right={n_right}, hallucinated={n_halluc})", flush=True)

    print("[2/5] Computing Touchstone signals", flush=True)
    t0 = time.perf_counter()
    ts_results: list[dict[str, Any]] = []
    for i, p in enumerate(pairs):
        ts_results.append(touchstone_signals(p["output"], p["context"]))
        if (i + 1) % 200 == 0:
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

    print("[5/5] Computing AUC + paired-ranking accuracy", flush=True)
    labels = [p["label"] for p in pairs]

    aucs: dict[str, dict[str, Any]] = {}

    # MiniCheck: raw_prob = P(supported). AUC for "hallucinated" positive class = AUC on (1 - raw_prob).
    mc_scores = [1.0 - float(p) for p in raw_probs]
    aucs["minicheck_flan_t5_large"] = {
        "auc_roc": round(auc_roc(mc_scores, labels), 4),
        "n_used": len(labels),
    }

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
        for sig, lab in zip(ts_results, labels, strict=True):
            v = sig.get(key)
            if v is None:
                continue
            usable_scores.append(float(v))
            usable_labels.append(lab)
        if not usable_scores:
            aucs[f"touchstone_{key}"] = {"auc_roc": None, "n_used": 0}
            continue
        aucs[f"touchstone_{key}"] = {
            "auc_roc": round(auc_roc(usable_scores, usable_labels), 4),
            "n_used": len(usable_scores),
            "n_skipped_none": len(labels) - len(usable_scores),
        }

    # Paired-ranking accuracy. For each document, the runner emitted
    # (right, hallucinated) consecutively. Within each pair the signal
    # should rank the hallucinated output higher than the right output
    # under the "higher = more hallucinated" orientation. The MiniCheck
    # baseline uses (1 - raw_prob) which has the same orientation.
    def paired_accuracy(scores_aligned: list[float | None]) -> dict[str, Any]:
        n_correct = 0
        n_tied = 0
        n_compared = 0
        for i in range(0, len(scores_aligned), 2):
            s_right = scores_aligned[i]
            s_halluc = scores_aligned[i + 1]
            if s_right is None or s_halluc is None:
                continue
            n_compared += 1
            if s_halluc > s_right:
                n_correct += 1
            elif s_halluc == s_right:
                n_tied += 1
        return {
            "n_doc_pairs_with_both_scores": n_compared,
            "n_correct": n_correct,
            "n_tied": n_tied,
            "accuracy": (
                round((n_correct + 0.5 * n_tied) / n_compared, 4) if n_compared > 0 else None
            ),
        }

    paired: dict[str, Any] = {}
    paired["minicheck_flan_t5_large"] = paired_accuracy(mc_scores)
    for key in signal_keys:
        aligned: list[float | None] = [sig.get(key) for sig in ts_results]
        paired[f"touchstone_{key}"] = paired_accuracy(aligned)

    output = {
        "experiment": "HaluEval summarization external validation",
        "corpus": "pminervini/HaluEval (summarization subset, data split, stratified sample)",
        "library": "clarethium-touchstone",
        "minicheck_model": args.minicheck_model,
        "n_documents_sampled": len(sampled),
        "n_total_pairs": len(pairs),
        "n_right": n_right,
        "n_hallucinated": n_halluc,
        "sampling_seed": args.seed,
        "construct_caveat": (
            "HaluEval is adversarially constructed: hallucinated_summary "
            "fields are ChatGPT-synthesized variants of real CNN/DM "
            "summaries with intentionally introduced errors. Touchstone's "
            "signals may capture synthetic-vs-real distributional "
            "differences in addition to the construct of interest. The "
            "paired-ranking accuracy readout (within-document right vs "
            "hallucinated) is the natural metric for this construction "
            "and bypasses any synthetic-vs-real population confound."
        ),
        "auc_roc_by_signal": aucs,
        "paired_ranking_accuracy_by_signal": paired,
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
