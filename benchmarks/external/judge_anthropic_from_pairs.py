"""Anthropic Claude judge on pre-extracted pairs.

Sister to ``judge_xai_from_pairs.py``. Uses the same two prompt
variants (``cued`` enumerating the §4 wall-claim categories,
``blind`` not enumerating). Calls Anthropic's Messages API directly
via the official ``anthropic`` SDK. The credential is loaded from
the environment at invocation time and lives only in the child
process.

The cued / blind text is byte-identical to ``judge_xai_from_pairs.py``
so cross-vendor comparisons are not confounded by prompt variation.

Usage::

    ANTHROPIC_API_KEY=... \\
        .venv-external/bin/python benchmarks/external/judge_anthropic_from_pairs.py \\
        benchmarks/adversarial_subtle/pairs.json \\
        --label "Adversarial Subtle 16-case" \\
        --corpus-dir adversarial_subtle \\
        --model claude-sonnet-4-6 \\
        --prompt-variant cued \\
        --output benchmarks/adversarial_subtle/judge_anthropic_2026-05-19.json
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

_VERDICT_TOOL = {
    "name": "record_hallucination_verdict",
    "description": (
        "Record a single hallucination-detection verdict as a probability in [0, 1] "
        "that OUTPUT contains a claim not supported by SOURCE."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "probability_hallucinated": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Probability OUTPUT contains an unsupported claim, in [0, 1].",
            }
        },
        "required": ["probability_hallucinated"],
    },
}


def score_one(
    client, model: str, context: str, output: str, system_prompt: str
) -> tuple[float, str]:
    """Single judge call via Claude's tool-use API. Returns (prob, raw_text).

    Claude Sonnet 4.6 does not support assistant-message prefill. Tool use
    is the alternative that guarantees a structured output: we expose a
    single tool with a required ``probability_hallucinated`` parameter
    and use ``tool_choice={"type": "tool", "name": ...}`` to force Claude
    to call it. Returns the tool input dict directly.
    """
    # Opus 4.7 deprecates the temperature parameter; pass it only for
    # models that still accept it (Sonnet 4.6, Haiku, etc.).
    kwargs: dict = {
        "model": model,
        "max_tokens": 512,
        "system": system_prompt,
        "tools": [_VERDICT_TOOL],
        "tool_choice": {"type": "tool", "name": _VERDICT_TOOL["name"]},
        "messages": [{"role": "user", "content": build_user_message(context, output)}],
    }
    if not model.startswith("claude-opus"):
        kwargs["temperature"] = 0.0
    message = client.messages.create(**kwargs)
    tool_input = None
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == _VERDICT_TOOL["name"]:
            tool_input = block.input
            break
    if tool_input is None:
        raise ValueError("no tool_use block in response")
    prob = float(tool_input["probability_hallucinated"])
    if not 0.0 <= prob <= 1.0:
        raise ValueError(f"probability_hallucinated out of [0,1]: {prob} (input={tool_input!r})")
    return prob, json.dumps(tool_input)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("pairs_json")
    p.add_argument("--label", required=True)
    p.add_argument("--corpus-dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--max-retries-per-pair", type=int, default=3)
    p.add_argument("--prompt-variant", choices=sorted(PROMPT_VARIANTS), default="cued")
    p.add_argument(
        "--checkpoint-every",
        type=int,
        default=20,
        help=(
            "Write a partial snapshot every N pairs so credit/rate-limit failures "
            "do not waste prior work. Restart the same command with --resume to "
            "continue from the partial."
        ),
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help=(
            "If the output path already contains a partial snapshot for the same "
            "model + prompt-variant + corpus, resume from where it left off "
            "instead of restarting from pair 0."
        ),
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only score the first --limit pairs (0 = score all). Useful for budget-bounded probes.",
    )
    args = p.parse_args()

    system_prompt = PROMPT_VARIANTS[args.prompt_variant]
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY not set. Export your Anthropic API key before invoking."
        )

    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    print(f"Loading pairs from {args.pairs_json}", flush=True)
    pairs = json.loads(Path(args.pairs_json).read_text())
    if args.limit > 0:
        pairs = pairs[: args.limit]
        print(f"  --limit applied: scoring only first {len(pairs)} pairs", flush=True)
    print(
        f"  n = {len(pairs)} pairs; model = {args.model}; variant = {args.prompt_variant}",
        flush=True,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = out_path.with_suffix(out_path.suffix + ".partial")

    probs: list[float] = []
    raws: list[str] = []
    if args.resume and partial_path.exists():
        existing = json.loads(partial_path.read_text())
        if (
            existing.get("baseline_model") == f"Anthropic {args.model}"
            and existing.get("judge_prompt_variant") == args.prompt_variant
            and existing.get("corpus") == args.corpus_dir
        ):
            probs = list(existing.get("per_example_prob_hallucinated", []))
            raws = list(existing.get("per_example_raw_response", []))
            print(
                f"  Resuming from partial: {len(probs)} pairs already scored.",
                flush=True,
            )
        else:
            print(
                f"  WARN: partial at {partial_path} has incompatible args; ignoring.",
                flush=True,
            )

    def _write_partial(probs_so_far: list[float], raws_so_far: list[str]) -> None:
        n_done = len(probs_so_far)
        labels_done = [int(p["label"]) for p in pairs[:n_done]]
        partial = {
            "experiment": f"Anthropic Claude judge PARTIAL on {args.label}",
            "corpus": args.corpus_dir,
            "baseline_model": f"Anthropic {args.model}",
            "baseline_provider": "Anthropic (Messages API)",
            "judge_prompt_variant": args.prompt_variant,
            "judge_prompt_system": system_prompt,
            "n_total_pairs_expected": len(pairs),
            "n_pairs_scored_so_far": n_done,
            "per_example_prob_hallucinated": [round(float(p), 6) for p in probs_so_far],
            "per_example_raw_response": raws_so_far,
            "per_example_label_hallucinated": labels_done,
        }
        partial_path.write_text(json.dumps(partial, indent=2))

    t0 = time.perf_counter()
    start_idx = len(probs)
    for i in range(start_idx, len(pairs)):
        pair = pairs[i]
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
            # Save partial before crashing so prior work survives.
            _write_partial(probs, raws)
            raise RuntimeError(
                f"Pair {i} failed after retries: {last_err}. "
                f"Partial saved to {partial_path} ({len(probs)} pairs); rerun with --resume."
            )
        if (i + 1) % 8 == 0:
            print(f"  scored {i + 1}/{len(pairs)} ({time.perf_counter() - t0:.1f}s)", flush=True)
        if (i + 1) % args.checkpoint_every == 0:
            _write_partial(probs, raws)

    elapsed = time.perf_counter() - t0
    per_ex = elapsed / max(1, len(pairs) - start_idx)
    print(f"  Judge done: {elapsed:.1f}s ({per_ex:.2f}s/example for new pairs)", flush=True)

    labels = [int(p["label"]) for p in pairs]
    point = auc_roc(probs, labels)
    ci = bootstrap_auc_ci(probs, labels, n_resamples=1000, seed=0)
    print(
        f"  Judge AUC = {point:.4f}  95% CI [{ci['ci_low']:.4f}, {ci['ci_high']:.4f}]  "
        f"(n_pos={ci['n_pos']}, n_neg={ci['n_neg']})",
        flush=True,
    )

    snapshot = {
        "experiment": f"Anthropic Claude judge baseline on {args.label}",
        "corpus": args.corpus_dir,
        "baseline_model": f"Anthropic {args.model}",
        "baseline_provider": "Anthropic (Messages API)",
        "judge_prompt_variant": args.prompt_variant,
        "judge_prompt_system": system_prompt,
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
    out_path.write_text(json.dumps(snapshot, indent=2))
    if partial_path.exists():
        partial_path.unlink()
    print(f"  Wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
