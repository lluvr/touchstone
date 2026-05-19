"""Extract per-pair substrate feature vectors on the n=400 subsamples.

The Verifier's substrate-only mode composes six features into a single
calibrated probability via logistic regression. The default calibration
(``DEFAULT_CALIBRATION_2026_05_17``) is fit on RAGTruth Summary; on
SummEval and HaluEval it is out-of-distribution. To characterize the
out-of-distribution penalty and the per-corpus achievable AUC, we need
the raw feature vectors per pair.

This script reads each n=400 subsample pair file and produces a
per-corpus snapshot with one feature dict per row, aligned to the same
indices as the ``substrate_only_n400_2026-05-18.json`` snapshots used
elsewhere.

Run::

    python -m benchmarks.external.extract_substrate_features
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from pathlib import Path

from clarethium_touchstone import measure
from clarethium_touchstone.verifier import _FEATURE_NAMES, _extract_substrate_features

CORPORA = [
    ("ragtruth_summary", "/tmp/alignscore_corpora/ragtruth_summary_n400.json", "RAGTruth Summary"),
    ("summeval", "/tmp/alignscore_corpora/summeval_n400.json", "SummEval"),
    (
        "halueval_summarization",
        "/tmp/alignscore_corpora/halueval_n400.json",
        "HaluEval Summarization",
    ),
]


def main() -> None:
    for corpus_dir, pairs_path, label in CORPORA:
        print(f"\n=== {label} (n=400) ===")
        pairs = json.loads(Path(pairs_path).read_text())
        features_per_pair: list[dict[str, float]] = []
        labels: list[int] = []
        t0 = time.perf_counter()
        for i, pair in enumerate(pairs):
            m = measure(pair["output"], source=pair["context"])
            features_per_pair.append(_extract_substrate_features(m))
            labels.append(int(pair["label"]))
            if (i + 1) % 100 == 0:
                print(f"  extracted {i + 1}/{len(pairs)} ({time.perf_counter() - t0:.1f}s)")
        elapsed = time.perf_counter() - t0
        print(f"  Done: {elapsed:.1f}s ({elapsed / max(1, len(pairs)) * 1000:.1f}ms/example)")

        out = OrderedDict()
        out["experiment"] = f"Per-pair substrate feature extraction on {label}"
        out["corpus"] = corpus_dir
        out["n_total_pairs"] = len(pairs)
        out["feature_names"] = _FEATURE_NAMES
        out["per_example_features"] = features_per_pair
        out["per_example_label_hallucinated"] = labels
        # Runtime intentionally omitted from snapshot for hash stability.

        out_path = Path(
            f"benchmarks/external/{corpus_dir}/results/substrate_features_n400_2026-05-19.json"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, indent=2))
        print(f"  Wrote {out_path}")


if __name__ == "__main__":
    main()
