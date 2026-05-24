"""Re-fit the Verifier's logistic regression on your own held-out data.

Touchstone ships with a calibration fitted on the RAGTruth Summary test
split. The shipped coefficients are honest for that distribution and
documented in ``src/clarethium_touchstone/_calibration.py``, but they will
NOT be optimal on your input distribution — especially if your data has
adversarial fabricated numbers (where the shipped negative
``l4_unsourced`` coefficient is empirically valid for naturalistic
RAGTruth-style data but wrong for clean-fabrication corpora).

This example shows the minimal recalibration recipe:

1. Collect a small held-out set of ``(text, source, label)`` triples
   where ``label=1`` indicates "the output is hallucinated."
2. Run ``measure()`` on each pair to extract the six substrate features.
3. Fit a logistic regression (no sklearn dependency; the example
   implements gradient descent in ~30 lines to stay dependency-free).
4. Plug the fitted coefficients into a ``Verifier.with_calibration(...)``
   instance.
5. Compare prob_hallucinated on the same input under the shipped vs
   recalibrated coefficients.

For real adopters, replace the inline ``HOLDOUT`` list with ~100-500 hand-
labeled rows from your production distribution. The bigger and more
representative the holdout, the better the resulting coefficients.

Run from the repository root::

    pip install -e .
    python examples/calibrate_on_holdout.py
"""

from __future__ import annotations

import math
from typing import Any

from clarethium_touchstone import Verifier, measure
from clarethium_touchstone.verifier import _extract_substrate_features

# Held-out training rows: (text, source, label_hallucinated). The toy set
# below is just enough for the gradient descent to converge to coefficients
# that catch clean fabrications. A real adopter uses N=100-500 rows.
SOURCE_A = (
    "Quarterly revenue grew 12% to $143 million, with operating margins of "
    "25%. Headcount declined 8% to 5,000 employees over 18 months. "
    "Retention improved to 94.2% across major segments."
)
SOURCE_B = (
    "Apple reported Q1 fiscal 2026 revenue of $143 billion. iPhone segment "
    "grew 8% year-over-year. Operating margins reached 32% per the earnings "
    "call. Tim Cook commented on AI investments during the call."
)

HOLDOUT: list[tuple[str, str, int]] = [
    # Faithful (label=0)
    ("Revenue grew 12% to $143 million with 25% operating margins.", SOURCE_A, 0),
    ("Headcount fell 8% to 5,000 employees over 18 months.", SOURCE_A, 0),
    ("Retention improved to 94.2% across major segments this quarter.", SOURCE_A, 0),
    ("Apple Q1 revenue was $143 billion; iPhone grew 8%; margins reached 32%.", SOURCE_B, 0),
    ("Tim Cook discussed AI investments on the earnings call.", SOURCE_B, 0),
    # Adversarial fabrications (label=1)
    ("Revenue rocketed to $999 million with 99% margins.", SOURCE_A, 1),
    ("Headcount surged to 50,000 employees this quarter alone.", SOURCE_A, 1),
    ("McKinsey forecasts 47% growth driven by 5G expansion.", SOURCE_A, 1),
    ("Apple Q1 revenue was $250 billion; iPhone grew 38%.", SOURCE_B, 1),
    ("The Federal Reserve will raise rates 75bp next month.", SOURCE_B, 1),
    ("Tesla announced a 2027 product roadmap citing 18% margins.", SOURCE_B, 1),
    ("Apple's Q1 EPS jumped 412% on McKinsey-forecast share gains.", SOURCE_B, 1),
]


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def fit_logistic_regression(
    features: list[dict[str, float]],
    labels: list[int],
    feature_order: list[str],
    *,
    learning_rate: float = 0.5,
    n_epochs: int = 2000,
    l2: float = 0.01,
) -> tuple[float, dict[str, float]]:
    """Minimal stdlib-only logistic-regression fit. Returns (intercept, coef)."""
    n = len(features)
    intercept = 0.0
    coef = dict.fromkeys(feature_order, 0.0)
    for _ in range(n_epochs):
        grad_intercept = 0.0
        grad_coef = dict.fromkeys(feature_order, 0.0)
        for x, y in zip(features, labels, strict=True):
            logit = intercept + sum(coef[name] * x[name] for name in feature_order)
            pred = _sigmoid(logit)
            err = pred - y  # gradient of cross-entropy wrt logit
            grad_intercept += err
            for name in feature_order:
                grad_coef[name] += err * x[name]
        # L2 regularization (no penalty on intercept)
        for name in feature_order:
            grad_coef[name] += l2 * coef[name]
        # SGD-style update on the mean gradient
        intercept -= learning_rate * grad_intercept / n
        for name in feature_order:
            coef[name] -= learning_rate * grad_coef[name] / n
    return intercept, coef


def build_calibration(intercept: float, coef: dict[str, float]) -> dict[str, Any]:
    """Wrap fitted coefficients in the calibration dict the Verifier expects."""
    return {
        "substrate_only": {
            "intercept": intercept,
            "coef": coef,
        },
        # If you fit baselines too, mirror the same shape under the relevant
        # mode keys: "substrate_plus_minicheck" / "_alignscore" / "_judge".
    }


def main() -> int:
    print("Touchstone calibration-on-holdout example")
    print(
        f"Holdout size: {len(HOLDOUT)} rows ({sum(HOLDOUT[i][2] for i in range(len(HOLDOUT)))} positive)"
    )

    # Step 1: extract substrate features for every holdout row.
    feature_rows: list[dict[str, float]] = []
    labels: list[int] = []
    for text, source, label in HOLDOUT:
        m = measure(text, source=source)
        feature_rows.append(_extract_substrate_features(m))
        labels.append(label)

    feature_order = [
        "l6_inv",
        "l4_unsourced",
        "l4_n_total_norm",
        "l11_p",
        "l5_entity_unsourced",
        "l5_n_entities_norm",
    ]

    # Step 2: fit logistic regression.
    intercept, coef = fit_logistic_regression(feature_rows, labels, feature_order)

    print("\nFitted coefficients:")
    print(f"  intercept: {intercept:+.4f}")
    for name in feature_order:
        print(f"  {name:<24s} {coef[name]:+.4f}")

    # Step 3: wrap and use the fitted calibration.
    custom = build_calibration(intercept, coef)
    v_custom = Verifier.with_calibration(custom)
    v_shipped = Verifier()

    print()
    print("Comparison on the holdout set (shipped vs recalibrated):")
    print(f"  {'#':<3s} {'label':<5s} {'p_shipped':>10s} {'p_recal':>9s} text")
    print("  " + "-" * 100)
    shipped_correct = 0
    recal_correct = 0
    for i, (text, source, label) in enumerate(HOLDOUT):
        r_shipped = v_shipped.score(text, source=source)
        r_custom = v_custom.score(text, source=source)
        p_shipped = r_shipped.prob_hallucinated
        p_recal = r_custom.prob_hallucinated
        # At threshold 0.5 (illustrative; tune yours)
        shipped_correct += int((p_shipped >= 0.5) == bool(label))
        recal_correct += int((p_recal >= 0.5) == bool(label))
        preview = text[:55].replace("\n", " ")
        print(f"  {i:<3d} {label:<5d} {p_shipped:>10.3f} {p_recal:>9.3f} {preview}")

    print()
    print(
        f"Accuracy at threshold 0.5 — shipped: {shipped_correct}/{len(HOLDOUT)}, "
        f"recalibrated: {recal_correct}/{len(HOLDOUT)}"
    )

    print()
    print("How to use this in production:")
    print(" • Replace the toy HOLDOUT with N=100-500 hand-labeled rows from your")
    print("   real data. Larger and more representative is always better.")
    print(" • Refit periodically as your model distribution shifts.")
    print(" • Save the fitted calibration dict to JSON and load it at runtime")
    print("   via Verifier.with_calibration(json.load(open('my_calib.json'))).")
    print(" • For multi-mode deployment, fit each mode separately on the rows")
    print("   where that mode's baseline scores are available.")
    print(" • The shipped DEFAULT_CALIBRATION_2026_05_17 is fitted on RAGTruth")
    print("   Summary; expect coefficient signs to differ on your distribution,")
    print("   especially l4_unsourced (negative on RAGTruth, typically positive")
    print("   on adversarial fabrication corpora).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
