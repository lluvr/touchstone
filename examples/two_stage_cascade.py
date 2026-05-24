"""Two-stage cascade: substrate cheap-screen + LLM judge on the maybe pile.

Production hallucination detection at scale is rarely about running the
most expensive judge on every output. The cheap-screen-plus-judge pattern
is what makes it economically viable:

* **Stage 1 (substrate):** Run :class:`Verifier` in ``substrate_only`` mode
  on every output. Sub-100 ms per 5 KB document, zero per-call cost,
  AUC ≈ 0.67-0.76 on the published external corpora.
* **Stage 2 (judge):** For outputs in the substrate's uncertain band
  (typically substrate probability 0.20-0.70), call a frontier LLM judge
  for a second-pass probability. The Verifier supports this directly via
  the ``substrate_plus_judge`` mode (see Standard §13.6 and
  ``docs/production_readiness.md`` §4.3.1).

This example simulates the judge with a deterministic stub so the script
runs offline; replace ``simulated_judge_call()`` with your real LLM
client. The simulated judge returns a fixed mapping per item id; in
production it makes one chat-completion call per uncertain trace.

Run from the repository root::

    pip install -e .
    python examples/two_stage_cascade.py
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from clarethium_touchstone import Verifier, VerifierResult

# Tune-half F1-optimal thresholds for the cheap-screen substrate. The
# 0.07-0.27 band is documented in production_readiness.md §2 across the
# three external corpora; the uncertain band below brackets that center.
# Adopters MUST re-tune these on their own held-out data.
LOW_BAND = 0.10  # substrate prob below this → ACCEPT without judge call
HIGH_BAND = 0.45  # substrate prob above this → FLAG without judge call
# Anything in [LOW_BAND, HIGH_BAND] → call the judge for a second opinion.

JUDGE_ALPHA = 0.3  # Substrate weight in the blend; tune on your data.


SOURCE = (
    "Apple reported Q1 fiscal 2026 revenue of $143 billion. The iPhone segment "
    "grew 8% year-over-year. Operating margins reached 32% per the earnings "
    "call. Tim Cook discussed AI investments during the call."
)

# Eight candidate outputs spanning the three expected cascade outcomes:
# auto-accept, auto-flag, and the maybe-pile that gets the judge call.
CANDIDATES: list[tuple[str, str]] = [
    (
        "id_01_clear_faithful",
        "Apple's Q1 fiscal 2026 revenue was $143 billion. iPhone grew 8% year-"
        "over-year and operating margins reached 32%. Tim Cook discussed AI "
        "investments during the earnings call.",
    ),
    (
        "id_02_clear_hallucination",
        "Apple's Q1 revenue was $250 billion driven by McKinsey's 47% growth "
        "forecast. The Federal Reserve will cut rates next month. Tesla "
        "announced a competing AR roadmap for 2027.",
    ),
    (
        "id_03_subtle_maybe",
        "Apple's Q1 revenue reached $143 billion, with iPhone growing roughly "
        "8% and operating margins at 32%. The earnings call featured Tim Cook "
        "outlining the company's AI investment posture for the next quarter.",
    ),
    (
        "id_04_partial_maybe",
        "Apple Q1 fiscal 2026 revenue was $143 billion. iPhone segment grew "
        "8%. Operating margins held steady around 30%. CEO Tim Cook addressed "
        "shareholders on AI investment plans.",
    ),
    (
        "id_05_off_topic_maybe",
        "Quarterly revenue grew 12% to $143 million, with operating margins "
        "reaching 25%. Headcount declined 8% to 5,000 employees over 18 "
        "months.",
    ),
    (
        "id_06_short_faithful",
        "Apple Q1 revenue: $143 billion. iPhone grew 8%. Margins 32%.",
    ),
    (
        "id_07_paraphrase",
        "First-quarter revenues at Apple climbed to $143 billion. iPhone unit "
        "sales rose 8% year-over-year. Operating margins were reported at "
        "32%, and Tim Cook spoke about AI investments on the earnings call.",
    ),
    (
        "id_08_empty",
        "",
    ),
]


def simulated_judge_call(text: str, source: str, item_id: str) -> float:
    """Deterministic stub for an LLM judge.

    In production, replace this with a real call:

    .. code-block:: python

        def judge(text, source, item_id):
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": JUDGE_PROMPT},
                    {"role": "user", "content": f"SOURCE:\\n{source}\\n\\nOUTPUT:\\n{text}"},
                ],
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)["probability_hallucinated"]

    The stub below returns a fixed probability per item so the example
    output is deterministic and reproducible.
    """
    fixtures = {
        "id_03_subtle_maybe": 0.18,  # Judge: actually faithful, paraphrase
        "id_04_partial_maybe": 0.62,  # Judge: margin number drifted (~30% vs 32%)
        "id_05_off_topic_maybe": 0.93,  # Judge: wrong domain entirely
        "id_06_short_faithful": 0.08,  # Judge: very short but faithful
        "id_07_paraphrase": 0.12,  # Judge: faithful paraphrase
    }
    return fixtures.get(item_id, 0.5)


@dataclass(frozen=True)
class CascadeRow:
    """One row of the cascade output: substrate decision + (optional) judge."""

    item_id: str
    substrate_prob: float
    scope: str
    stage: str  # "auto_accept" | "auto_flag" | "judge_called"
    final_prob: float
    judge_prob: float | None
    final_decision: str  # "accept" | "flag"
    result: VerifierResult


def run_cascade(candidates: list[tuple[str, str]], source: str) -> list[CascadeRow]:
    """Execute the substrate-screen-plus-judge cascade."""
    v_substrate = Verifier()  # substrate_only mode for the screen
    v_judge = Verifier()  # same Verifier; mode auto-selects to substrate_plus_judge
    rows: list[CascadeRow] = []

    for item_id, text in candidates:
        # Stage 1: cheap screen.
        screen = v_substrate.score(text, source=source)

        # Scope gate: insufficient_input is a separate routing path.
        if screen.scope == "insufficient_input":
            rows.append(
                CascadeRow(
                    item_id=item_id,
                    substrate_prob=screen.prob_hallucinated,
                    scope=screen.scope,
                    stage="route_to_review",
                    final_prob=screen.prob_hallucinated,
                    judge_prob=None,
                    final_decision="manual_review",
                    result=screen,
                )
            )
            continue

        if screen.prob_hallucinated < LOW_BAND:
            rows.append(
                CascadeRow(
                    item_id=item_id,
                    substrate_prob=screen.prob_hallucinated,
                    scope=screen.scope,
                    stage="auto_accept",
                    final_prob=screen.prob_hallucinated,
                    judge_prob=None,
                    final_decision="accept",
                    result=screen,
                )
            )
            continue

        if screen.prob_hallucinated > HIGH_BAND:
            rows.append(
                CascadeRow(
                    item_id=item_id,
                    substrate_prob=screen.prob_hallucinated,
                    scope=screen.scope,
                    stage="auto_flag",
                    final_prob=screen.prob_hallucinated,
                    judge_prob=None,
                    final_decision="flag",
                    result=screen,
                )
            )
            continue

        # Stage 2: judge call on the uncertain band.
        judge_prob = simulated_judge_call(text, source, item_id)
        blended = v_judge.score(
            text,
            source=source,
            judge_hallucinated_prob=judge_prob,
            judge_alpha=JUDGE_ALPHA,
        )
        decision = "flag" if blended.prob_hallucinated >= 0.5 else "accept"
        rows.append(
            CascadeRow(
                item_id=item_id,
                substrate_prob=screen.prob_hallucinated,
                scope=blended.scope,
                stage="judge_called",
                final_prob=blended.prob_hallucinated,
                judge_prob=judge_prob,
                final_decision=decision,
                result=blended,
            )
        )

    return rows


def print_cascade_report(rows: list[CascadeRow]) -> None:
    """Pretty-print the cascade results plus cost summary."""
    print()
    print("=" * 100)
    print("  Two-stage cascade — substrate screen + judge on the maybe pile")
    print("=" * 100)
    print(
        f"{'item_id':<30s} {'sub':>6s} {'stage':<16s} {'judge':>7s} {'final':>7s} {'decision':<14s}"
    )
    print("-" * 100)
    n_judge_called = 0
    for r in rows:
        judge_str = "—" if r.judge_prob is None else f"{r.judge_prob:.3f}"
        if r.stage == "judge_called":
            n_judge_called += 1
        print(
            f"{r.item_id:<30s} {r.substrate_prob:>6.3f} {r.stage:<16s} "
            f"{judge_str:>7s} {r.final_prob:>7.3f} {r.final_decision:<14s}"
        )

    print()
    print(f"Substrate evaluations: {len(rows)} (sub-100 ms per pair, $0)")
    print(
        f"Judge calls:           {n_judge_called} of {len(rows)} ({100 * n_judge_called / len(rows):.0f}%)"
    )
    print(f"Cost reduction vs judge-on-every-trace: {100 * (1 - n_judge_called / len(rows)):.0f}%")

    print()
    print("Tuning notes:")
    print(f" • LOW_BAND  = {LOW_BAND}  (below this: skip judge, auto-accept)")
    print(f" • HIGH_BAND = {HIGH_BAND}  (above this: skip judge, auto-flag)")
    print(f" • JUDGE_ALPHA = {JUDGE_ALPHA}  (substrate weight in the blend)")
    print(" • All three knobs must be tuned on your own held-out data; the")
    print("   defaults above bracket the typical F1-optimal substrate range.")


def main() -> int:
    print("Touchstone two-stage cascade example")
    print(f"Candidates: {len(CANDIDATES)} outputs against source ({len(SOURCE)} chars)")
    start = time.perf_counter()
    rows = run_cascade(CANDIDATES, SOURCE)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    print(f"Cascade ran in {elapsed_ms:.1f} ms (substrate stage only; judge stub is offline)")
    print_cascade_report(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
