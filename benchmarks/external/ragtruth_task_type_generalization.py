"""Task-type generalization analysis on RAGTruth.

The three external benchmarks shipped so far (RAGTruth Summary,
SummEval, HaluEval summarization) all test summarization outputs.
RAGTruth's `test` split also covers QA (n=900) and Data2Txt (n=900);
this analysis re-uses Touchstone on those task types to test whether
the cross-corpus signal pattern (Layer 6 generalizes; Layer 10 gap
degenerates) holds across task types within a single corpus.

This is Touchstone-only: MiniCheck baselines for the QA and
Data2Txt task types are deferred (each task type would require a
separate ~100 min CPU run; the Summary task type is already covered
in `ragtruth_summary/results/`).

Usage::

    python -m benchmarks.external.ragtruth_task_type_generalization
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

from datasets import load_dataset  # noqa: E402

from benchmarks.external._bootstrap import bootstrap_auc_ci  # noqa: E402
from clarethium_touchstone import measure  # noqa: E402


def _signals(text: str, source: str) -> dict[str, float | None]:
    r = measure(text, source=source)
    sm = r["source_matching"]
    ep = r["entity_provenance"]
    vp = r["vocabulary_proximity"]
    qp = r["quality_profile"]
    gd = r["grounding_decomposition"]
    mp = vp["mean_proximity"]
    return {
        "layer4_unsourced_rate": sm["unsourced_rate"] if sm["n_total"] > 0 else None,
        "layer5_entity_unsourced_rate": (
            ep["entity_unsourced_rate"] if ep["n_entities"] >= 5 else None
        ),
        "layer6_inverse_proximity": (1.0 - mp if mp is not None else None),
        "layer10_gap": qp["gap"],
        "layer11_p_proportion": gd["proportions"]["P"],
    }


SIGNAL_KEYS = [
    "layer4_unsourced_rate",
    "layer5_entity_unsourced_rate",
    "layer6_inverse_proximity",
    "layer10_gap",
    "layer11_p_proportion",
]


def main() -> None:
    print("[1/3] Loading wandb/RAGTruth-processed test split", flush=True)
    ds = load_dataset("wandb/RAGTruth-processed", split="test")
    print(f"      n_total = {len(ds)}", flush=True)

    output: dict[str, Any] = {
        "experiment": "RAGTruth task-type generalization (Touchstone only)",
        "corpus": "wandb/RAGTruth-processed (test split)",
        "library": "clarethium-touchstone",
        "task_types_evaluated": ["Summary", "QA", "Data2txt"],
        "minicheck_note": (
            "MiniCheck baselines for QA and Data2Txt task types are not "
            "computed in this analysis. The Summary task type has a full "
            "MiniCheck baseline in `ragtruth_summary/results/2026-05-15.json`; "
            "extending the head-to-head to QA and Data2Txt is open work."
        ),
        "results_by_task": {},
    }

    for task in ["Summary", "QA", "Data2txt"]:
        print(f"\n[2/3] Task: {task}", flush=True)
        pairs = [r for r in ds if r["task_type"] == task]
        labels = [int(bool(json.loads(r["hallucination_labels"]))) for r in pairs]
        n_pos = sum(labels)
        print(
            f"      n = {len(pairs)}  hallucinated = {n_pos} ({n_pos / len(pairs):.1%})", flush=True
        )

        t0 = time.perf_counter()
        sigs = [_signals(r["output"], r["context"]) for r in pairs]
        ts_elapsed = time.perf_counter() - t0
        print(f"      Touchstone: {ts_elapsed:.1f}s", flush=True)

        task_result: dict[str, Any] = {
            "n_total": len(pairs),
            "n_hallucinated": n_pos,
            "hallucination_rate": round(n_pos / max(1, len(pairs)), 4),
            "touchstone_signals": {},
            "touchstone_runtime_s": round(ts_elapsed, 2),
        }
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
                task_result["touchstone_signals"][key] = {
                    "auc": None,
                    "ci_low": None,
                    "ci_high": None,
                    "n_used": len(scores),
                    "n_skipped_none": len(labels) - len(scores),
                }
                continue
            ci = bootstrap_auc_ci(scores, labs, n_resamples=1000, seed=0)
            ci["n_skipped_none"] = len(labels) - len(scores)
            task_result["touchstone_signals"][key] = ci

        output["results_by_task"][task] = task_result

    # Brief stdout summary.
    print("\n[3/3] Summary across task types", flush=True)
    print(
        f"{'task':12s} {'L4 AUC':>14s} {'L6_inv AUC':>14s} {'L10 gap AUC':>14s} {'L11 P AUC':>14s}",
        flush=True,
    )
    for task, r in output["results_by_task"].items():
        row = []
        for key in [
            "layer4_unsourced_rate",
            "layer6_inverse_proximity",
            "layer10_gap",
            "layer11_p_proportion",
        ]:
            d = r["touchstone_signals"][key]
            if d.get("auc") is None:
                row.append("N/A".rjust(14))
            else:
                row.append(f"{d['auc']:.4f}".rjust(14))
        print(f"{task:12s} {' '.join(row)}", flush=True)

    out_path = Path(
        "benchmarks/external/ragtruth_summary/results/task_type_generalization_2026-05-15.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nWrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
