"""Run an xAI Grok judge on pre-extracted (context, output, label) pairs.

Sister script to ``minicheck_from_pairs.py`` / ``alignscore_from_pairs.py``.
Uses xAI's OpenAI-compatible API to call a fast Grok model and have it
return a structured ``{"probability_hallucinated": <0..1>}`` verdict for
each pair. The credential is decrypted from the vault at invocation
time and lives only in the child process; never read from a file on
disk and never written to the snapshot.

Two judge prompt variants ship in this module:

- ``cued`` (``JUDGE_SYSTEM_PROMPT_CUED``). The original prompt the
  §4.1 and §4.2 snapshots in ``production_readiness.md`` were scored
  under. It enumerates six failure modes (polarity flip, attribute
  swap, scope shift, time-frame shift, relation reversal, imputed
  cause) that the §4 wall claim names as the substrate's structural
  blind spots. Earlier docstrings called this prompt "deliberately
  minimal and unparameterised"; that framing was wrong. The category
  enumeration is steering. The 100% separation in §4.1 and the
  judge column in §4.2 reflect cued-judge performance, not a generic
  frontier-judge ceiling. See §4.1's prompt-cueing confound bullet
  in ``docs/production_readiness.md`` for the load-bearing caveat.
- ``blind`` (``JUDGE_SYSTEM_PROMPT_BLIND``). Same task, no category
  enumeration. Use this for the cueing-effect ablation. The
  cued-vs-blind delta on naturalistic data measures how much of the
  cued judge's advantage is from the prompt steering versus from
  general source-reading capability. The 16-case fixture is at
  ceiling under both prompts (see the in-session stress test summary
  written into the §4.1 confounds box); the cueing ablation has to
  run on naturalistic data to be informative.

Pass ``--prompt-variant {cued,blind}``; ``cued`` is the default for
backward compatibility with the existing snapshots. The snapshot
records ``judge_prompt_variant`` and the literal ``judge_prompt_system``
text so downstream consumers can tell the variants apart.

Usage::

    XAI_API_KEY=$(vault decrypt XAI_API_KEY) \\
        .venv-external/bin/python benchmarks/external/judge_xai_from_pairs.py \\
        benchmarks/adversarial_subtle/pairs.json \\
        --label "Adversarial Subtle 16-case" \\
        --corpus-dir adversarial_subtle \\
        --model grok-4.20-0309-non-reasoning \\
        --prompt-variant cued \\
        --output benchmarks/adversarial_subtle/judge_xai_2026-05-18.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import auc_roc, bootstrap_auc_ci  # noqa: E402

JUDGE_SYSTEM_PROMPT_CUED = (
    "You are a strict hallucination detector. Given a SOURCE passage and an OUTPUT passage, "
    "estimate the probability in [0, 1] that the OUTPUT contains any claim that is not directly "
    "supported by the SOURCE. Higher means more likely to contain an unsupported claim. "
    "Treat polarity flips, attribute swaps, scope shifts, time-frame shifts, relation reversals, "
    "and imputed causes as unsupported even when the vocabulary overlaps with the source. "
    'Reply with a single JSON object: {"probability_hallucinated": <number in [0, 1]>}. '
    "No prose, no explanation, no other keys."
)

JUDGE_SYSTEM_PROMPT_BLIND = (
    "You are a strict hallucination detector. Given a SOURCE passage and an OUTPUT passage, "
    "estimate the probability in [0, 1] that the OUTPUT contains any claim that is not directly "
    "supported by the SOURCE. Higher means more likely to contain an unsupported claim. "
    'Reply with a single JSON object: {"probability_hallucinated": <number in [0, 1]>}. '
    "No prose, no explanation, no other keys."
)

PROMPT_VARIANTS = {
    "cued": JUDGE_SYSTEM_PROMPT_CUED,
    "blind": JUDGE_SYSTEM_PROMPT_BLIND,
}

# Backward-compatible alias. Pre-existing imports of JUDGE_SYSTEM_PROMPT
# continue to resolve to the cued prompt (the prompt the existing
# snapshots were scored under).
JUDGE_SYSTEM_PROMPT = JUDGE_SYSTEM_PROMPT_CUED


def build_user_message(context: str, output: str) -> str:
    return f"SOURCE:\n{context.strip()}\n\nOUTPUT:\n{output.strip()}"


def score_one(
    client, model: str, context: str, output: str, system_prompt: str
) -> tuple[float, str]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_user_message(context, output)},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    parsed = json.loads(raw)
    prob = float(parsed["probability_hallucinated"])
    if not 0.0 <= prob <= 1.0:
        raise ValueError(f"probability_hallucinated out of [0,1]: {prob} (raw={raw!r})")
    return prob, raw


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("pairs_json", help="Path to JSON file with [{context, output, label}, ...]")
    p.add_argument("--label", required=True, help="Human-readable corpus name.")
    p.add_argument("--corpus-dir", required=True, help="Corpus dir slug.")
    p.add_argument("--output", required=True, help="Output snapshot JSON path.")
    p.add_argument(
        "--model",
        default="grok-4.20-0309-non-reasoning",
        help=(
            "xAI model id. The default is the fast non-reasoning variant. "
            "List available models with `client.models.list()` against base_url. "
            "Model ids change with xAI's release cadence; pass --model explicitly "
            "to pin a snapshot."
        ),
    )
    p.add_argument("--base-url", default="https://api.x.ai/v1")
    p.add_argument(
        "--max-retries-per-pair",
        type=int,
        default=3,
        help="On transient API or parse failures, retry up to this many times before raising.",
    )
    p.add_argument(
        "--prompt-variant",
        choices=sorted(PROMPT_VARIANTS),
        default="cued",
        help=(
            "Which judge prompt to use. 'cued' (default, matches the existing §4.1/§4.2 "
            "snapshots) enumerates the six §4 wall-claim categories. 'blind' omits the "
            "category enumeration; use it for the cueing-effect ablation. The chosen "
            "variant is recorded in the output snapshot under 'judge_prompt_variant'."
        ),
    )
    args = p.parse_args()
    system_prompt = PROMPT_VARIANTS[args.prompt_variant]

    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "XAI_API_KEY not set. Invoke via: XAI_API_KEY=$(vault decrypt XAI_API_KEY) python ..."
        )

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=args.base_url)
    print(f"Loading pairs from {args.pairs_json}", flush=True)
    pairs = json.loads(Path(args.pairs_json).read_text())
    print(f"  n = {len(pairs)} pairs; model = {args.model}", flush=True)

    probs: list[float] = []
    raws: list[str] = []
    t0 = time.perf_counter()
    for i, pair in enumerate(pairs):
        last_err: Exception | None = None
        for attempt in range(args.max_retries_per_pair):
            try:
                prob, raw = score_one(
                    client, args.model, pair["context"], pair["output"], system_prompt
                )
                probs.append(prob)
                raws.append(raw)
                break
            except Exception as e:
                last_err = e
                time.sleep(1.0 * (attempt + 1))
        else:
            raise RuntimeError(
                f"Pair {i} failed after {args.max_retries_per_pair} attempts: {last_err}"
            )
        if (i + 1) % 8 == 0:
            print(f"  scored {i + 1}/{len(pairs)} ({(time.perf_counter() - t0):.1f}s)", flush=True)

    elapsed = time.perf_counter() - t0
    per_ex = elapsed / max(1, len(pairs))
    print(f"  Judge done: {elapsed:.1f}s ({per_ex:.2f}s/example)", flush=True)

    labels = [int(p["label"]) for p in pairs]
    point = auc_roc(probs, labels)
    ci = bootstrap_auc_ci(probs, labels, n_resamples=1000, seed=0)
    print(
        f"  Judge AUC = {point:.4f}  95% CI [{ci['ci_low']:.4f}, {ci['ci_high']:.4f}]  "
        f"(n_pos={ci['n_pos']}, n_neg={ci['n_neg']})",
        flush=True,
    )

    snapshot = {
        "experiment": f"xAI Grok judge baseline on {args.label}",
        "corpus": args.corpus_dir,
        "baseline_model": f"xAI {args.model}",
        "baseline_provider": "xAI (OpenAI-compatible API)",
        "judge_prompt_variant": args.prompt_variant,
        "judge_prompt_system": system_prompt,
        "judge_temperature": 0.0,
        "n_total_pairs": len(pairs),
        "n_positive": ci["n_pos"],
        "n_negative": ci["n_neg"],
        "judge": {
            "auc_roc": round(point, 4),
            "bootstrap_95ci": ci,
            "direction_note": (
                "Judge output is already P(hallucinated) in [0, 1]. AUC "
                "is computed directly on the judge probability so the "
                "positive class is 'hallucinated' to match the other "
                "baselines reported alongside."
            ),
        },
        "per_example_prob_hallucinated": [round(float(p), 6) for p in probs],
        "per_example_raw_response": raws,
        "per_example_label_hallucinated": labels,
        "runtime_seconds": round(elapsed, 1),
        "per_example_seconds_mean": round(per_ex, 4),
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2))
    print(f"  Wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
