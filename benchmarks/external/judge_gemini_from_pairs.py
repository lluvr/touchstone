"""Gemini judge on pre-extracted pairs, via an OpenAI-compatible proxy.

Sister to ``judge_openai_from_pairs.py`` / ``judge_anthropic_from_pairs.py`` /
``judge_xai_from_pairs.py``. Routes through an OpenAI-compatible local
proxy (default ``http://localhost:4000``, overridable via
``OPENAI_BASE_URL``). The credential is loaded at invocation time via
``OPENAI_API_KEY`` and lives only in the child process. Same
OpenAI-compatible interface, just a different model id.

Available Gemini models via the proxy at the time of writing:
``gemini-2.5-flash``, ``gemini-3-flash-preview``,
``gemini-3.1-flash-lite-preview``, ``gemini-3.1-pro-preview``. The
default below is ``gemini-3-flash-preview`` (fast tier, fits the
multi-vendor cross-judge methodology that pairs xAI's
``grok-4.20-0309-non-reasoning`` and Anthropic's ``claude-sonnet-4-6``).

Cost (Gemini Flash class via proxy): a 400-row n=400 run costs roughly
$0.10 in proxy-charged tokens. Cheap enough that adding Gemini to the
cross-vendor matrix is essentially free.

Prompt text (cued / blind) is byte-identical to
``judge_xai_from_pairs.py`` so cross-vendor comparisons are not
confounded by prompt variation.

Usage::

    OPENAI_API_KEY=... \\
        .venv-external/bin/python benchmarks/external/judge_gemini_from_pairs.py \\
        /tmp/alignscore_corpora/ragtruth_summary_n400.json \\
        --label "RAGTruth Summary (n=400 cued)" \\
        --corpus-dir ragtruth_summary \\
        --model gemini-3-flash-preview \\
        --prompt-variant cued \\
        --output benchmarks/external/ragtruth_summary/results/judge_gemini_3_flash_cued_n400_2026-05-19.json
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
from judge_xai_from_pairs import PROMPT_VARIANTS, build_user_message  # noqa: E402


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
    p.add_argument("pairs_json")
    p.add_argument("--label", required=True)
    p.add_argument("--corpus-dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument(
        "--model",
        default="gemini-3-flash-preview",
        help="Gemini model id exposed by the proxy.",
    )
    p.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL", "http://localhost:4000"),
    )
    p.add_argument("--max-retries-per-pair", type=int, default=3)
    p.add_argument("--prompt-variant", choices=sorted(PROMPT_VARIANTS), default="cued")
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only score the first --limit pairs (0 = score all).",
    )
    args = p.parse_args()

    system_prompt = PROMPT_VARIANTS[args.prompt_variant]
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set. Export your provider API key before invoking.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=args.base_url)
    print(f"Loading pairs from {args.pairs_json}", flush=True)
    pairs = json.loads(Path(args.pairs_json).read_text())
    if args.limit > 0:
        pairs = pairs[: args.limit]
        print(f"  --limit applied: scoring only first {len(pairs)} pairs", flush=True)
    print(
        f"  n = {len(pairs)} pairs; model = {args.model}; variant = {args.prompt_variant}; "
        f"base_url = {args.base_url}",
        flush=True,
    )

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
            raise RuntimeError(f"Pair {i} failed after retries: {last_err}")
        if (i + 1) % 8 == 0:
            print(f"  scored {i + 1}/{len(pairs)} ({time.perf_counter() - t0:.1f}s)", flush=True)

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
        "experiment": f"Gemini judge baseline on {args.label}",
        "corpus": args.corpus_dir,
        "baseline_model": f"Google {args.model}",
        "baseline_provider": "Google Gemini",
        "judge_prompt_variant": args.prompt_variant,
        "judge_prompt_system": system_prompt,
        "judge_temperature": 0.0,
        "n_total_pairs": len(pairs),
        "n_positive": ci["n_pos"],
        "n_negative": ci["n_neg"],
        "judge": {
            "auc_roc": round(point, 4),
            "bootstrap_95ci": ci,
        },
        "per_example_prob_hallucinated": [round(float(p), 6) for p in probs],
        "per_example_raw_response": raws,
        "per_example_label_hallucinated": labels,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2))
    print(f"  Wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
