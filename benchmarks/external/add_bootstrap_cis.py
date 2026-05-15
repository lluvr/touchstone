"""Add 95% bootstrap CIs to existing external-benchmark snapshots.

This is a post-hoc augmentation. The existing snapshots written by
each runner contain point AUCs computed in a single pass; this
script re-runs Touchstone (fast, ~3 seconds per corpus) and computes
percentile bootstrap CIs (1000 stratified resamples, seed=0) on
each Touchstone signal's AUC. The original snapshot is updated in
place with a new ``touchstone_bootstrap_95ci`` section.

MiniCheck-side CIs are not computed in this pass because the
per-example MiniCheck raw probabilities were not retained in the
original snapshots. Re-running MiniCheck to add MiniCheck CIs is
roughly 4.5 hours of CPU compute across the three corpora and is
deferred; the runners now save per-example MiniCheck probabilities
so a future invocation of this script can fill those in without
re-running MiniCheck.

Usage::

    python -m benchmarks.external.add_bootstrap_cis
"""

from __future__ import annotations

import json
import os
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

from datasets import load_dataset  # noqa: E402

from benchmarks.external._bootstrap import bootstrap_auc_ci  # noqa: E402
from clarethium_touchstone import measure  # noqa: E402


def _signals_for_pair(text: str, source: str) -> dict[str, float | None]:
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


def load_ragtruth_pairs() -> list[dict[str, Any]]:
    ds = load_dataset("wandb/RAGTruth-processed", split="test")
    summary = [r for r in ds if r["task_type"] == "Summary"]
    pairs: list[dict[str, Any]] = []
    for r in summary:
        spans = json.loads(r["hallucination_labels"])
        pairs.append(
            {
                "context": r["context"],
                "output": r["output"],
                "label": int(bool(spans)),
            }
        )
    return pairs


def load_summeval_pairs() -> list[dict[str, Any]]:
    ds = load_dataset("mteb/summeval", split="test")
    pairs: list[dict[str, Any]] = []
    for row in ds:
        for i, summary in enumerate(row["machine_summaries"]):
            cons = float(row["consistency"][i])
            pairs.append(
                {
                    "context": row["text"],
                    "output": summary,
                    "label": int(cons < 4.0),
                }
            )
    return pairs


def load_halueval_pairs() -> list[dict[str, Any]]:
    ds = load_dataset("pminervini/HaluEval", "summarization", split="data")
    rng = random.Random(0)
    indices = rng.sample(range(len(ds)), 500)
    pairs: list[dict[str, Any]] = []
    for i in indices:
        row = ds[i]
        pairs.append({"context": row["document"], "output": row["right_summary"], "label": 0})
        pairs.append(
            {"context": row["document"], "output": row["hallucinated_summary"], "label": 1}
        )
    return pairs


CORPORA: list[tuple[str, Callable[[], list[dict[str, Any]]]]] = [
    ("ragtruth_summary/results/2026-05-15.json", load_ragtruth_pairs),
    ("summeval/results/2026-05-15.json", load_summeval_pairs),
    ("halueval_summarization/results/2026-05-15.json", load_halueval_pairs),
]


SIGNAL_KEYS = [
    "layer4_unsourced_rate",
    "layer5_entity_unsourced_rate",
    "layer6_inverse_proximity",
    "layer10_gap",
    "layer11_p_proportion",
]


def main() -> None:
    base = Path("benchmarks/external")
    for snapshot_rel, loader in CORPORA:
        snapshot_path = base / snapshot_rel
        print(f"--- {snapshot_path}", flush=True)
        if not snapshot_path.exists():
            print("  skip (missing snapshot)", flush=True)
            continue

        print("  loading corpus", flush=True)
        pairs = loader()
        print(f"  n = {len(pairs)} pairs", flush=True)

        print("  computing Touchstone signals", flush=True)
        sigs = [_signals_for_pair(p["output"], p["context"]) for p in pairs]
        labels = [p["label"] for p in pairs]

        cis: dict[str, dict[str, Any]] = {}
        for key in SIGNAL_KEYS:
            scores: list[float] = []
            labs: list[int] = []
            for sig, lab in zip(sigs, labels, strict=True):
                v = sig[key]
                if v is None:
                    continue
                scores.append(float(v))
                labs.append(lab)
            if not scores or len(set(labs)) < 2:
                cis[f"touchstone_{key}"] = {
                    "auc": None,
                    "ci_low": None,
                    "ci_high": None,
                    "n_used": len(scores),
                }
                continue
            cis[f"touchstone_{key}"] = bootstrap_auc_ci(scores, labs, n_resamples=1000, seed=0)

        snapshot = json.loads(snapshot_path.read_text())
        snapshot["touchstone_bootstrap_95ci"] = cis
        snapshot["bootstrap_methodology"] = (
            "Stratified percentile bootstrap on AUC-ROC, 1000 resamples, seed=0. "
            "Positives and negatives are resampled with replacement within their "
            "respective class to preserve the label base rate. MiniCheck CIs are "
            "not computed in this pass: per-example MiniCheck raw probabilities "
            "were not retained in the original snapshots, and re-running MiniCheck "
            "on all three corpora costs roughly 4.5 hours of CPU compute. The "
            "point AUCs in `auc_roc_by_signal` are unchanged."
        )

        snapshot_path.write_text(json.dumps(snapshot, indent=2))
        print(f"  augmented: {snapshot_path}", flush=True)
        # Print a compact summary
        print("  Touchstone 95% bootstrap CIs:", flush=True)
        for key in SIGNAL_KEYS:
            row = cis[f"touchstone_{key}"]
            if row.get("auc") is None:
                print(f"    {key:35s}  AUC=N/A (n={row.get('n_used', 0)})", flush=True)
                continue
            print(
                f"    {key:35s}  AUC={row['auc']:.4f}  "
                f"95% CI [{row['ci_low']:.4f}, {row['ci_high']:.4f}]  "
                f"(n_pos={row['n_pos']}, n_neg={row['n_neg']})",
                flush=True,
            )


if __name__ == "__main__":
    main()
