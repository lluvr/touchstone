"""Run the Verifier substrate-only Verifier on each pair of an n=400 subsample.

Outputs per-example substrate probabilities aligned to the same row
order as the subsample-indices file and the Grok per-example
probability snapshot. The §4.3 substrate-plus-judge analysis joins
these arrays.

Run::

    python -m benchmarks.external.score_substrate_on_subsample \\
        --pairs /tmp/alignscore_corpora/ragtruth_summary_n400.json \\
        --output benchmarks/external/ragtruth_summary/results/substrate_only_n400_2026-05-18.json \\
        --corpus-dir ragtruth_summary --label "RAGTruth Summary"
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from clarethium_touchstone import Verifier


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--pairs", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--corpus-dir", required=True)
    p.add_argument("--label", required=True)
    args = p.parse_args()

    pairs = json.loads(Path(args.pairs).read_text())
    verifier = Verifier()

    probs: list[float] = []
    t0 = time.perf_counter()
    for i, pair in enumerate(pairs):
        result = verifier.score(pair["output"], source=pair["context"])
        probs.append(float(result.prob_hallucinated))
        if (i + 1) % 100 == 0:
            print(f"  scored {i + 1}/{len(pairs)} ({(time.perf_counter() - t0):.1f}s)", flush=True)
    elapsed = time.perf_counter() - t0
    print(f"  Substrate: {elapsed:.1f}s ({elapsed / max(1, len(pairs)):.3f}s/example)")

    labels = [int(p["label"]) for p in pairs]
    out = {
        "experiment": f"Verifier substrate-only baseline on {args.label}",
        "corpus": args.corpus_dir,
        "verifier_mode": "substrate_only",
        "calibration": "DEFAULT_CALIBRATION_2026_05_17",
        "n_total_pairs": len(pairs),
        "per_example_prob_hallucinated": [round(p, 6) for p in probs],
        "per_example_label_hallucinated": labels,
        "runtime_seconds": round(elapsed, 1),
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
