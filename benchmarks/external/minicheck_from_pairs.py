"""Re-score the external corpora with MiniCheck, saving per-example probs.

Companion to ``alignscore_from_pairs.py``. The original per-corpus
runners (``ragtruth_summary/run.py`` etc.) computed aggregate MiniCheck
AUCs but did not retain per-example probabilities, which means bootstrap
CIs on the MiniCheck side were not computable from the original
snapshots. This script re-runs MiniCheck on pre-extracted (context,
output, label) pair files, saves per-example probabilities AND computes
95% percentile bootstrap CIs (stratified, 1000 resamples, fixed seed).

Each corpus's snapshot gets an additional file ``minicheck_with_cis_*.json``
under the corpus's ``results/`` directory, leaving the original snapshot
untouched. The bootstrap CI values are the canonical reference for
MiniCheck-side CIs going forward; the new file is the source of truth.

Usage::

    source .venv-external/bin/activate
    python benchmarks/external/minicheck_from_pairs.py \\
        /tmp/alignscore_corpora/summeval.json \\
        --label SummEval \\
        --corpus-dir summeval \\
        --output benchmarks/external/summeval/results/minicheck_with_cis_2026-05-15.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import auc_roc, bootstrap_auc_ci  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("pairs_json", help="Path to JSON file with [{context, output, label}, ...]")
    p.add_argument("--label", required=True, help="Human-readable corpus name.")
    p.add_argument("--corpus-dir", required=True, help="Corpus dir slug.")
    p.add_argument("--output", required=True, help="Output snapshot JSON path.")
    p.add_argument("--minicheck-model", default="flan-t5-large")
    args = p.parse_args()

    print(f"Loading pairs from {args.pairs_json}", flush=True)
    pairs = json.loads(Path(args.pairs_json).read_text())
    print(f"  n = {len(pairs)} pairs", flush=True)

    print(f"Loading MiniCheck {args.minicheck_model} (CPU)", flush=True)
    t0 = time.perf_counter()
    from minicheck.minicheck import MiniCheck

    scorer = MiniCheck(
        model_name=args.minicheck_model,
        cache_dir="./ckpts_minicheck",
        enable_prefix_caching=False,
    )
    print(f"  Init: {time.perf_counter() - t0:.1f}s", flush=True)

    print(f"\n=== {args.label} ===", flush=True)
    t0 = time.perf_counter()
    docs = [p["context"] for p in pairs]
    claims = [p["output"] for p in pairs]
    pred_labels, raw_probs, _, _ = scorer.score(docs=docs, claims=claims)
    elapsed = time.perf_counter() - t0
    per_ex = elapsed / max(1, len(pairs))
    print(f"  MiniCheck: {elapsed:.1f}s ({per_ex:.2f}s/example)", flush=True)

    labels = [int(p["label"]) for p in pairs]
    # raw_prob = P(supported); for AUC on "hallucinated" positive class, score = 1 - raw_prob.
    auc_scores = [1.0 - float(rp) for rp in raw_probs]
    point = auc_roc(auc_scores, labels)
    ci = bootstrap_auc_ci(auc_scores, labels, n_resamples=1000, seed=0)
    print(
        f"  MiniCheck AUC = {point:.4f}  95% CI [{ci['ci_low']:.4f}, {ci['ci_high']:.4f}]  "
        f"(n_pos={ci['n_pos']}, n_neg={ci['n_neg']})",
        flush=True,
    )

    snapshot = {
        "experiment": f"MiniCheck Flan-T5-Large baseline with bootstrap CIs on {args.label}",
        "corpus": args.corpus_dir,
        "baseline_model": f"MiniCheck {args.minicheck_model}",
        "baseline_paper": "Tang et al., EMNLP 2024 (https://aclanthology.org/2024.emnlp-main.499)",
        "baseline_license": "Apache-2.0",
        "n_total_pairs": len(pairs),
        "n_positive": ci["n_pos"],
        "n_negative": ci["n_neg"],
        "minicheck": {
            "auc_roc": round(point, 4),
            "bootstrap_95ci": ci,
            "direction_note": (
                "Raw MiniCheck output is P(supported) in [0, 1]. AUC is "
                "computed on (1 - raw_prob) so the positive class is "
                "'hallucinated' to match the other baselines reported alongside."
            ),
        },
        "per_example_raw_prob_supported": [round(float(rp), 6) for rp in raw_probs],
        "per_example_predicted_label_supported": [int(pl) for pl in pred_labels],
        "per_example_label_hallucinated": labels,
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
