"""Emit a 32-row pairs JSON for the 16-case subtle stress test.

The companion scripts ``benchmarks/external/minicheck_from_pairs.py``,
``benchmarks/external/alignscore_from_pairs.py``, and
``benchmarks/external/judge_xai_from_pairs.py`` all consume the
``[{context, output, label}, ...]`` shape. This script lifts the 16
``(source, faithful, hallucinated)`` triples from
``benchmarks/adversarial_subtle/run.py`` into that shape (32 rows: the
faithful side gets label=0, the hallucinated side gets label=1) and
adds two carry-through fields, ``case_idx`` and ``category``, that the
join step uses to rebuild per-case deltas.

Run::

    python -m benchmarks.adversarial_subtle.build_pairs
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.adversarial_subtle.run import CASES


def main() -> None:
    pairs: list[dict] = []
    for idx, (category, source, faithful, hallucinated) in enumerate(CASES):
        pairs.append(
            {
                "context": source,
                "output": faithful,
                "label": 0,
                "case_idx": idx,
                "category": category,
                "side": "faithful",
            }
        )
        pairs.append(
            {
                "context": source,
                "output": hallucinated,
                "label": 1,
                "case_idx": idx,
                "category": category,
                "side": "hallucinated",
            }
        )
    out_path = Path("benchmarks/adversarial_subtle/pairs.json")
    out_path.write_text(json.dumps(pairs, indent=2))
    print(f"Wrote {out_path} with {len(pairs)} rows ({len(CASES)} cases x 2 sides)")


if __name__ == "__main__":
    main()
