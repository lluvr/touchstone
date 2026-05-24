"""FactScore-class claim-level baseline on pre-extracted (context, output, label) pairs.

Sister script to ``judge_xai_from_pairs.py``. Instead of asking the LLM
for a single output-level probability that the OUTPUT contains an
unsupported claim, this script implements the FactScore (Min et al.,
2023) / RefChecker (Hu et al., 2024) family of "atomic claim
decomposition + per-claim verification" baselines. For each pair:

1. **Extraction.** One LLM call breaks OUTPUT into atomic factual
   claims. The model is instructed to return JSON
   ``{"claims": ["claim1", "claim2", ...]}``.
2. **Per-claim verification.** For each atomic claim (capped at
   ``--max-claims-per-output``), one LLM call checks whether SOURCE
   supports CLAIM. The model returns
   ``{"supported": true|false, "confidence": <0..1>}``.
3. **Aggregation.** Output-level factscore =
   ``1 - mean(supported_per_claim)``. Higher = more hallucinated.
   Edge case: zero claims extracted -> score = 0.0 (no claims, no
   hallucinations).

The LLM backend is xAI Grok via the OpenAI-compatible API, matching
the pattern in ``judge_xai_from_pairs.py``. ``XAI_API_KEY`` is
loaded from the environment at invocation time and lives only in the
child process.

This script makes ~1 + min(n_claims, max_claims) calls per pair,
typically 6-15. Checkpointing is therefore mandatory: a crash midway
through 400 pairs without checkpoints would lose hundreds of paid
calls. The ``--checkpoint-every`` and ``--resume`` mechanics mirror
``judge_anthropic_from_pairs.py``.

Usage::

    XAI_API_KEY=... \\
        .venv-external/bin/python benchmarks/external/factscore_baseline.py \\
        /tmp/alignscore_corpora/summeval_n400.json \\
        --label "SummEval (n=400)" \\
        --corpus-dir summeval \\
        --output benchmarks/external/summeval/results/factscore_grok_n400_2026-05-19.json \\
        --max-claims-per-output 10 \\
        --checkpoint-every 10
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

EXTRACT_SYSTEM_PROMPT = (
    "You are an expert at decomposing text into atomic factual claims. "
    "Given an OUTPUT passage, split it into a list of atomic factual claims. "
    "Each claim must be independently verifiable against a source: a single fact, "
    "in a single short sentence, with no compound conjunctions and no opinion. "
    "Skip pure stylistic phrases (greetings, fillers) and meta-commentary. "
    'Reply with a single JSON object of the form {"claims": ["claim1", "claim2", ...]}. '
    "No prose, no explanation, no other keys. If the OUTPUT contains no verifiable claims, "
    'return {"claims": []}.'
)

VERIFY_SYSTEM_PROMPT = (
    "You are a strict source-grounded fact checker. Given a SOURCE passage and a single "
    "CLAIM, decide whether the SOURCE supports the CLAIM. Treat a CLAIM as supported only "
    "if the SOURCE explicitly states or unambiguously entails the key information. Partial "
    "support, plausible inference, or background knowledge does NOT count. "
    'Reply with a single JSON object: {"supported": true|false, "confidence": <number in [0, 1]>}. '
    "No prose, no explanation, no other keys."
)


def build_extract_user(output: str) -> str:
    return f"OUTPUT:\n{output.strip()}"


def build_verify_user(context: str, claim: str) -> str:
    return f"SOURCE:\n{context.strip()}\n\nCLAIM:\n{claim.strip()}"


def _call_with_retry(client, *, model: str, messages: list[dict], max_retries: int):
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            return response
        except Exception as e:  # noqa: BLE001 - want to retry any transient API error
            last_err = e
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"API call failed after {max_retries} retries: {last_err}")


def extract_claims(
    client, model: str, output: str, max_claims: int, max_retries: int
) -> tuple[list[str], dict[str, int]]:
    """Returns (claims_capped_to_max_claims, usage_dict)."""
    response = _call_with_retry(
        client,
        model=model,
        messages=[
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": build_extract_user(output)},
        ],
        max_retries=max_retries,
    )
    raw = response.choices[0].message.content or ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"extract returned non-JSON: {raw!r}") from e
    claims = parsed.get("claims", [])
    if not isinstance(claims, list):
        raise ValueError(f"extract returned non-list claims: {raw!r}")
    cleaned: list[str] = []
    for c in claims:
        if isinstance(c, str) and c.strip():
            cleaned.append(c.strip())
        if len(cleaned) >= max_claims:
            break
    usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
    }
    return cleaned, usage


def verify_claim(
    client, model: str, context: str, claim: str, max_retries: int
) -> tuple[bool, float, dict[str, int]]:
    """Returns (supported_bool, confidence_float, usage_dict)."""
    response = _call_with_retry(
        client,
        model=model,
        messages=[
            {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
            {"role": "user", "content": build_verify_user(context, claim)},
        ],
        max_retries=max_retries,
    )
    raw = response.choices[0].message.content or ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"verify returned non-JSON: {raw!r}") from e
    supported_raw = parsed.get("supported")
    if isinstance(supported_raw, str):
        supported = supported_raw.strip().lower() in {"true", "yes", "supported", "1"}
    else:
        supported = bool(supported_raw)
    confidence = float(parsed.get("confidence", 1.0 if supported else 0.0))
    confidence = max(0.0, min(1.0, confidence))
    usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
    }
    return supported, confidence, usage


def factscore_for_pair(
    client,
    model: str,
    context: str,
    output: str,
    max_claims: int,
    max_retries: int,
) -> tuple[float, list[str], list[bool], list[float], dict[str, int]]:
    """Run extract + per-claim verify; returns (factscore, claims, supported, conf, usage_totals)."""
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "n_calls": 0}
    claims, u = extract_claims(client, model, output, max_claims, max_retries)
    totals["prompt_tokens"] += u["prompt_tokens"]
    totals["completion_tokens"] += u["completion_tokens"]
    totals["n_calls"] += 1

    if not claims:
        # Honest edge: empty output / no extractable claims => no hallucinations.
        return 0.0, [], [], [], totals

    supported_per_claim: list[bool] = []
    confidence_per_claim: list[float] = []
    for claim in claims:
        sup, conf, u2 = verify_claim(client, model, context, claim, max_retries)
        supported_per_claim.append(sup)
        confidence_per_claim.append(conf)
        totals["prompt_tokens"] += u2["prompt_tokens"]
        totals["completion_tokens"] += u2["completion_tokens"]
        totals["n_calls"] += 1

    factscore = 1.0 - (sum(1 for s in supported_per_claim if s) / len(supported_per_claim))
    return factscore, claims, supported_per_claim, confidence_per_claim, totals


# xAI Grok 4.20-0309-non-reasoning approximate pricing as of 2026-05.
# Input $2 / 1M tokens, output $10 / 1M tokens (per task brief).
PRICE_PER_INPUT_TOKEN = 2.0 / 1_000_000
PRICE_PER_OUTPUT_TOKEN = 10.0 / 1_000_000


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return prompt_tokens * PRICE_PER_INPUT_TOKEN + completion_tokens * PRICE_PER_OUTPUT_TOKEN


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("pairs_json", help="Path to JSON file with [{context, output, label}, ...]")
    p.add_argument("--label", required=True, help="Human-readable corpus name.")
    p.add_argument("--corpus-dir", required=True, help="Corpus dir slug.")
    p.add_argument("--output", required=True, help="Output snapshot JSON path.")
    p.add_argument(
        "--model",
        default="grok-4.20-0309-non-reasoning",
        help="xAI model id (default: grok-4.20-0309-non-reasoning).",
    )
    p.add_argument("--base-url", default="https://api.x.ai/v1")
    p.add_argument("--max-retries-per-pair", type=int, default=3)
    p.add_argument(
        "--max-claims-per-output",
        type=int,
        default=10,
        help="Hard cap on per-output claim verifications. Long outputs are truncated to the first N claims.",
    )
    p.add_argument(
        "--checkpoint-every",
        type=int,
        default=10,
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
            "If the output path already has a partial snapshot for the same "
            "model/corpus/max-claims setting, resume from where it left off."
        ),
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only score the first --limit pairs (0 = score all).",
    )
    p.add_argument(
        "--call-budget",
        type=int,
        default=0,
        help=(
            "Stop after this many total API calls (extract + verify) across this run. "
            "0 = no budget cap. Useful as a hard guardrail against runaway cost."
        ),
    )
    args = p.parse_args()

    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise SystemExit("XAI_API_KEY not set. Export your xAI API key before invoking.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=args.base_url)
    print(f"Loading pairs from {args.pairs_json}", flush=True)
    pairs = json.loads(Path(args.pairs_json).read_text())
    if args.limit > 0:
        pairs = pairs[: args.limit]
        print(f"  --limit applied: scoring only first {len(pairs)} pairs", flush=True)
    print(
        f"  n = {len(pairs)} pairs; model = {args.model}; max_claims = {args.max_claims_per_output}",
        flush=True,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = out_path.with_suffix(out_path.suffix + ".partial")

    factscores: list[float] = []
    n_claims_per: list[int] = []
    claims_per: list[list[str]] = []
    supported_per: list[list[bool]] = []
    confidence_per: list[list[float]] = []
    usage_running = {"prompt_tokens": 0, "completion_tokens": 0, "n_calls": 0}

    if args.resume and partial_path.exists():
        existing = json.loads(partial_path.read_text())
        if (
            existing.get("baseline_model") == f"xAI {args.model}"
            and existing.get("corpus") == args.corpus_dir
            and existing.get("max_claims_per_output") == args.max_claims_per_output
        ):
            factscores = list(existing.get("per_example_factscore", []))
            n_claims_per = list(existing.get("per_example_n_claims", []))
            claims_per = list(existing.get("per_example_claims", []))
            supported_per = [list(s) for s in existing.get("per_example_per_claim_supported", [])]
            confidence_per = [list(c) for c in existing.get("per_example_per_claim_confidence", [])]
            usage_running = dict(
                existing.get(
                    "runtime_usage_totals",
                    {"prompt_tokens": 0, "completion_tokens": 0, "n_calls": 0},
                )
            )
            print(
                f"  Resuming from partial: {len(factscores)} pairs already scored "
                f"({usage_running.get('n_calls', 0)} calls).",
                flush=True,
            )
        else:
            print(
                f"  WARN: partial at {partial_path} has incompatible args; ignoring.",
                flush=True,
            )

    def _write_partial() -> None:
        n_done = len(factscores)
        labels_done = [int(p["label"]) for p in pairs[:n_done]]
        partial = {
            "experiment": f"FactScore-class claim-level baseline PARTIAL on {args.label}",
            "corpus": args.corpus_dir,
            "baseline_model": f"xAI {args.model}",
            "baseline_provider": "xAI (OpenAI-compatible API)",
            "method": "atomic claim extraction + per-claim source-grounding verification",
            "max_claims_per_output": args.max_claims_per_output,
            "n_total_pairs_expected": len(pairs),
            "n_pairs_scored_so_far": n_done,
            "per_example_factscore": [round(float(s), 6) for s in factscores],
            "per_example_n_claims": list(n_claims_per),
            "per_example_claims": list(claims_per),
            "per_example_per_claim_supported": [list(s) for s in supported_per],
            "per_example_per_claim_confidence": [
                [round(float(c), 4) for c in row] for row in confidence_per
            ],
            "per_example_label_hallucinated": labels_done,
            "runtime_usage_totals": dict(usage_running),
            "runtime_cost_usd_estimate": round(
                estimate_cost_usd(
                    usage_running["prompt_tokens"], usage_running["completion_tokens"]
                ),
                4,
            ),
        }
        partial_path.write_text(json.dumps(partial, indent=2))

    t0 = time.perf_counter()
    start_idx = len(factscores)
    for i in range(start_idx, len(pairs)):
        if args.call_budget and usage_running["n_calls"] >= args.call_budget:
            print(
                f"  Call budget {args.call_budget} reached at pair {i}; halting and saving partial.",
                flush=True,
            )
            _write_partial()
            print(
                f"  Partial saved to {partial_path}. Rerun with --resume to continue.",
                flush=True,
            )
            return

        pair = pairs[i]
        try:
            fs, claims, sup, conf, usage = factscore_for_pair(
                client,
                args.model,
                pair["context"],
                pair["output"],
                args.max_claims_per_output,
                args.max_retries_per_pair,
            )
        except Exception as e:  # noqa: BLE001
            _write_partial()
            raise RuntimeError(
                f"Pair {i} failed: {e}. Partial saved to {partial_path} "
                f"({len(factscores)} pairs); rerun with --resume."
            ) from e

        factscores.append(fs)
        n_claims_per.append(len(claims))
        claims_per.append(claims)
        supported_per.append(sup)
        confidence_per.append(conf)
        usage_running["prompt_tokens"] += usage["prompt_tokens"]
        usage_running["completion_tokens"] += usage["completion_tokens"]
        usage_running["n_calls"] += usage["n_calls"]

        if (i + 1) % 8 == 0:
            elapsed = time.perf_counter() - t0
            cost = estimate_cost_usd(
                usage_running["prompt_tokens"], usage_running["completion_tokens"]
            )
            print(
                f"  scored {i + 1}/{len(pairs)}  "
                f"({elapsed:.1f}s, {usage_running['n_calls']} calls, "
                f"~${cost:.3f} so far)",
                flush=True,
            )
        if (i + 1) % args.checkpoint_every == 0:
            _write_partial()

    elapsed = time.perf_counter() - t0
    per_ex = elapsed / max(1, len(pairs) - start_idx)
    cost_total = estimate_cost_usd(
        usage_running["prompt_tokens"], usage_running["completion_tokens"]
    )
    print(
        f"  Done: {elapsed:.1f}s ({per_ex:.2f}s/example for new pairs); "
        f"{usage_running['n_calls']} total calls; ~${cost_total:.3f}",
        flush=True,
    )

    labels = [int(p["label"]) for p in pairs]
    point = auc_roc(factscores, labels)
    ci = bootstrap_auc_ci(factscores, labels, n_resamples=1000, seed=0)
    print(
        f"  FactScore AUC = {point:.4f}  95% CI [{ci['ci_low']:.4f}, {ci['ci_high']:.4f}]  "
        f"(n_pos={ci['n_pos']}, n_neg={ci['n_neg']})",
        flush=True,
    )

    snapshot = {
        "experiment": f"FactScore-class claim-level baseline on {args.label}",
        "corpus": args.corpus_dir,
        "baseline_model": f"xAI {args.model}",
        "baseline_provider": "xAI (OpenAI-compatible API)",
        "method": "atomic claim extraction + per-claim source-grounding verification",
        "extract_prompt_system": EXTRACT_SYSTEM_PROMPT,
        "verify_prompt_system": VERIFY_SYSTEM_PROMPT,
        "max_claims_per_output": args.max_claims_per_output,
        "judge_temperature": 0.0,
        "n_total_pairs": len(pairs),
        "n_positive": ci["n_pos"],
        "n_negative": ci["n_neg"],
        "judge": {
            "auc_roc": round(point, 4),
            "bootstrap_95ci": ci,
            "direction_note": (
                "FactScore is 1 - mean(supported_per_claim). Higher means more "
                "hallucinated, so AUC is computed directly with positive class = "
                "hallucinated, matching the other §4.2 baselines."
            ),
        },
        "per_example_factscore": [round(float(s), 6) for s in factscores],
        "per_example_n_claims": list(n_claims_per),
        "per_example_claims": list(claims_per),
        "per_example_per_claim_supported": [list(s) for s in supported_per],
        "per_example_per_claim_confidence": [
            [round(float(c), 4) for c in row] for row in confidence_per
        ],
        "per_example_label_hallucinated": labels,
        "runtime_seconds": round(elapsed, 1),
        "per_example_seconds_mean": round(per_ex, 4),
        "runtime_usage_totals": dict(usage_running),
        "runtime_cost_usd_estimate": round(cost_total, 4),
        "pricing_note": (
            "Cost estimate uses xAI Grok 4.20 non-reasoning rates "
            "($2/M input, $10/M output) supplied via the runbook brief; "
            "actual billing may differ slightly."
        ),
    }

    out_path.write_text(json.dumps(snapshot, indent=2))
    if partial_path.exists():
        partial_path.unlink()
    print(f"  Wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
