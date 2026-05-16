"""Run AlignScore-base on pre-extracted (context, output, label) pairs.

Companion to ``alignscore_baselines.py``. The same runner-style script,
but reads pairs from a JSON file instead of loading the corpus via the
``datasets`` library. This decouples the AlignScore venv (which pins
torch<2 and therefore an older ``datasets``) from corpus loading.

The intermediate JSON should be a list of dicts each with at least
``context``, ``output``, and ``label`` keys, produced by exporting
from the main ``.venv-external`` (newer datasets) which can parse
schemas the AlignScore venv's older datasets cannot.

Usage::

    source .venv-alignscore/bin/activate
    python benchmarks/external/alignscore_from_pairs.py \\
        /tmp/alignscore_corpora/summeval.json \\
        --label SummEval \\
        --output benchmarks/external/summeval/results/alignscore_baseline_2026-05-15.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import auc_roc, bootstrap_auc_ci  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("pairs_json", help="Path to JSON file with [{context, output, label}, ...]")
    p.add_argument("--label", required=True, help="Human-readable corpus name for the snapshot.")
    p.add_argument("--corpus-dir", required=True, help="Corpus dir slug for the snapshot.")
    p.add_argument("--output", required=True, help="Output snapshot JSON path.")
    p.add_argument("--ckpt", default="./ckpts_alignscore/AlignScore-base.ckpt")
    args = p.parse_args()

    print(f"Loading pairs from {args.pairs_json}", flush=True)
    pairs = json.loads(Path(args.pairs_json).read_text())
    print(f"  n = {len(pairs)} pairs", flush=True)

    print("Loading AlignScore-base on CPU", flush=True)
    t0 = time.perf_counter()
    from alignscore import AlignScore

    scorer = AlignScore(
        model="roberta-base",
        batch_size=8,
        device="cpu",
        ckpt_path=args.ckpt,
        evaluation_mode="nli_sp",
    )
    print(f"  Init: {time.perf_counter() - t0:.1f}s", flush=True)

    print(f"\n=== {args.label} ===", flush=True)
    t0 = time.perf_counter()
    scores_supported = scorer.score(
        contexts=[p["context"] for p in pairs],
        claims=[p["output"] for p in pairs],
    )
    elapsed = time.perf_counter() - t0
    per_ex = elapsed / max(1, len(pairs))
    print(f"  AlignScore: {elapsed:.1f}s ({per_ex:.2f}s/example)", flush=True)

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
        "experiment": f"AlignScore-base baseline on {args.label}",
        "corpus": args.corpus_dir,
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

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2))
    print(f"  Wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
