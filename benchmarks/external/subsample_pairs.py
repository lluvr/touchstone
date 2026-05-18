"""Emit a deterministic subsample of a (context, output, label) pairs JSON.

Decouples the judge-cost question (3500 calls is excessive when 1200
is decisive for a directional comparison) from the apples-to-apples
question (Grok scored on subset N=400 needs MiniCheck/AlignScore
re-tabulated on the same indices for a fair table).

This script writes BOTH artifacts: the sub-pairs JSON for the judge
run and the index list for re-tabulating existing per-example arrays.

Sampling strategy: takes the first ``n_total`` rows of the source
file in their original order. The source pair files were assembled
without label-correlated ordering, so first-N preserves base rate to
within ~1.5 percentage points across the three external corpora.
First-N is preferred over stratified sampling because the operational
metrics (F1-optimal threshold, precision-at-recall, recall-at-precision,
lift-at-top-K) are base-rate dependent; balanced stratification would
distort them.

The fully reproducible sample is determined by the source file path
and ``n_total`` only; no seed is needed.

Run::

    python -m benchmarks.external.subsample_pairs \\
        /tmp/alignscore_corpora/ragtruth_summary.json \\
        --n-total 400 \\
        --pairs-out /tmp/alignscore_corpora/ragtruth_summary_n400.json \\
        --indices-out benchmarks/external/ragtruth_summary/results/subsample_n400_indices.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("pairs_json", help="Full pairs JSON.")
    p.add_argument("--n-total", type=int, required=True)
    p.add_argument("--pairs-out", required=True)
    p.add_argument("--indices-out", required=True)
    args = p.parse_args()

    pairs = json.loads(Path(args.pairs_json).read_text())
    if len(pairs) < args.n_total:
        raise SystemExit(f"n_total={args.n_total} but only {len(pairs)} rows in {args.pairs_json}")

    sub_pairs = pairs[: args.n_total]
    indices_in_original = list(range(args.n_total))
    labels = [int(p["label"]) for p in sub_pairs]
    base_rate = sum(labels) / len(labels)

    Path(args.pairs_out).write_text(json.dumps(sub_pairs, indent=2))
    Path(args.indices_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.indices_out).write_text(
        json.dumps(
            {
                "source": str(args.pairs_json),
                "sampling_strategy": "first_n_in_original_order",
                "n_total": len(sub_pairs),
                "n_positive": sum(labels),
                "n_negative": len(labels) - sum(labels),
                "base_rate": round(base_rate, 4),
                "indices_in_original": indices_in_original,
                "labels": labels,
            },
            indent=2,
        )
    )
    print(
        f"Wrote {args.pairs_out} ({len(sub_pairs)} rows, base rate {base_rate:.3f}) "
        f"and {args.indices_out}"
    )


if __name__ == "__main__":
    main()
