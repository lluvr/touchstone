"""Second-baseline runs: AlignScore on the three external corpora.

Runs AlignScore-base (Zha et al., ACL 2023, MIT) against every
(context, output) pair in the three external corpora already covered
by MiniCheck. Goal: a second independently-trained baseline on the
same inputs, to test whether the Touchstone-vs-MiniCheck gap pattern
is baseline-specific or general to LLM-trained discriminators.

Why a separate runner: AlignScore requires ``torch<2`` and an older
transformers (``AdamW`` is in the public namespace only in
``transformers<4.40``). This venv is ``.venv-alignscore`` on Python
3.10 and is incompatible with the main ``.venv-external`` (Python
3.12, torch 2+). The runner saves a corpus-specific snapshot under
each corpus directory; integration with the main snapshots (which
hold MiniCheck + Touchstone results) is via separate JSON files.

The snapshot now also retains per-example AlignScore scores so that
follow-up bootstrap CIs can be computed without re-running.

Corpus loaders are local copies (datasets is in this venv) — they
match the loaders in the main runners and in ``add_bootstrap_cis``
exactly so the pair ordering is reproducible across runs.

Run::

    source .venv-alignscore/bin/activate
    python benchmarks/external/alignscore_baselines.py
"""

from __future__ import annotations

import json
import os
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

# stdlib bootstrap helper (shipped under benchmarks/external/_bootstrap.py).
# This runner runs in `.venv-alignscore` which does not have clarethium_touchstone
# installed; importing _bootstrap directly via path is enough.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import auc_roc, bootstrap_auc_ci  # noqa: E402
from datasets import load_dataset  # noqa: E402


def load_ragtruth_pairs() -> list[dict[str, Any]]:
    ds = load_dataset("wandb/RAGTruth-processed", split="test")
    pairs: list[dict[str, Any]] = []
    for r in ds:
        if r["task_type"] != "Summary":
            continue
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


CORPORA: list[tuple[str, str, Callable[[], list[dict[str, Any]]]]] = [
    ("ragtruth_summary", "RAGTruth Summary", load_ragtruth_pairs),
    ("summeval", "SummEval", load_summeval_pairs),
    ("halueval_summarization", "HaluEval summarization", load_halueval_pairs),
]


def main() -> None:
    print("Loading AlignScore-base on CPU (one-time init ~80s)", flush=True)
    t0 = time.perf_counter()
    from alignscore import AlignScore

    scorer = AlignScore(
        model="roberta-base",
        batch_size=8,
        device="cpu",
        ckpt_path="./ckpts_alignscore/AlignScore-base.ckpt",
        evaluation_mode="nli_sp",
    )
    print(f"  Init: {time.perf_counter() - t0:.1f}s", flush=True)

    base = Path("benchmarks/external")

    for corpus_dir, label, loader in CORPORA:
        print(f"\n=== {label} ({corpus_dir}) ===", flush=True)
        pairs = loader()
        print(f"  n = {len(pairs)} pairs", flush=True)

        t0 = time.perf_counter()
        # AlignScore returns scores in [0, 1], higher = more supported.
        scores_supported = scorer.score(
            contexts=[p["context"] for p in pairs],
            claims=[p["output"] for p in pairs],
        )
        elapsed = time.perf_counter() - t0
        per_ex = elapsed / max(1, len(pairs))
        print(
            f"  AlignScore: {elapsed:.1f}s total ({per_ex:.2f}s/example)",
            flush=True,
        )

        # For AUC against the "hallucinated" positive class, invert: score = 1 - supported.
        labels = [int(p["label"]) for p in pairs]
        auc_scores = [1.0 - float(s) for s in scores_supported]

        point = auc_roc(auc_scores, labels)
        ci = bootstrap_auc_ci(auc_scores, labels, n_resamples=1000, seed=0)
        print(
            f"  AlignScore AUC = {point:.4f}  95% CI [{ci['ci_low']:.4f}, {ci['ci_high']:.4f}]  "
            f"(n_pos={ci['n_pos']}, n_neg={ci['n_neg']})",
            flush=True,
        )

        snapshot = {
            "experiment": f"AlignScore-base baseline on {label}",
            "corpus": corpus_dir,
            "baseline_model": "AlignScore-base (roberta-base, nli_sp evaluation mode)",
            "baseline_paper": "Zha et al., ACL 2023 (https://aclanthology.org/2023.acl-long.634/)",
            "baseline_license": "MIT",
            "n_total_pairs": len(pairs),
            "n_positive": ci["n_pos"],
            "n_negative": ci["n_neg"],
            "alignscore": {
                "auc_roc": round(point, 4),
                "bootstrap_95ci": ci,
                "direction_note": (
                    "Raw AlignScore output is in [0, 1] with higher meaning "
                    "more supported. AUC is computed on (1 - score) so the "
                    "positive class is 'hallucinated' to match the other "
                    "baselines reported alongside."
                ),
            },
            "per_example_raw_score_supported": [round(float(s), 6) for s in scores_supported],
            "per_example_label": labels,
            "runtime_seconds": round(elapsed, 1),
            "per_example_seconds_mean": round(per_ex, 4),
            "device": "cpu",
        }

        out_path = base / corpus_dir / "results" / "alignscore_baseline_2026-05-15.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(snapshot, indent=2))
        print(f"  Wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
