"""Bootstrap-CI helper for AUC-ROC.

Provides a Mann-Whitney U based AUC and a percentile bootstrap CI
(stratified resampling within positive/negative classes). Stdlib
only; no numpy dependency.
"""

from __future__ import annotations

import random


def auc_roc(scores: list[float], labels: list[int]) -> float:
    """AUC-ROC via Mann-Whitney U. Higher score = more likely positive.

    Ties contribute 0.5 each. Returns 0.5 if either class is empty.
    """
    pos: list[float] = []
    neg: list[float] = []
    for s, lab in zip(scores, labels, strict=True):
        if lab == 1:
            pos.append(s)
        else:
            neg.append(s)
    if not pos or not neg:
        return 0.5
    concordant = 0
    ties = 0
    for p in pos:
        for n in neg:
            if p > n:
                concordant += 1
            elif p == n:
                ties += 1
    return (concordant + 0.5 * ties) / (len(pos) * len(neg))


def bootstrap_auc_ci(
    scores: list[float],
    labels: list[int],
    *,
    n_resamples: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict[str, float]:
    """Percentile bootstrap CI on AUC-ROC.

    Stratified resampling: positives and negatives are resampled with
    replacement within their respective class to preserve the label
    base rate. Returns the point AUC, the lower/upper CI bounds at
    ``confidence``, and the n_resamples used.

    The seed is fixed for snapshot pinning. For ``n_resamples = 1000``
    with ``confidence = 0.95``, the lower bound is the 2.5th percentile
    of the resample distribution and the upper bound is the 97.5th.
    """
    pos_scores: list[float] = []
    neg_scores: list[float] = []
    for s, lab in zip(scores, labels, strict=True):
        if lab == 1:
            pos_scores.append(s)
        else:
            neg_scores.append(s)

    if not pos_scores or not neg_scores:
        return {
            "auc": 0.5,
            "ci_low": 0.5,
            "ci_high": 0.5,
            "n_resamples": n_resamples,
            "n_pos": len(pos_scores),
            "n_neg": len(neg_scores),
        }

    point = auc_roc(scores, labels)

    rng = random.Random(seed)
    n_pos = len(pos_scores)
    n_neg = len(neg_scores)
    boot_aucs: list[float] = []
    for _ in range(n_resamples):
        # Stratified resample.
        rs_pos = [pos_scores[rng.randrange(n_pos)] for _ in range(n_pos)]
        rs_neg = [neg_scores[rng.randrange(n_neg)] for _ in range(n_neg)]
        # Re-compute AUC on the resampled pools.
        concordant = 0
        ties = 0
        for p in rs_pos:
            for n in rs_neg:
                if p > n:
                    concordant += 1
                elif p == n:
                    ties += 1
        boot_aucs.append((concordant + 0.5 * ties) / (n_pos * n_neg))

    boot_aucs.sort()
    tail = (1.0 - confidence) / 2.0
    low_idx = max(0, int(tail * n_resamples) - 1)
    high_idx = min(n_resamples - 1, int((1.0 - tail) * n_resamples))
    return {
        "auc": round(point, 4),
        "ci_low": round(boot_aucs[low_idx], 4),
        "ci_high": round(boot_aucs[high_idx], 4),
        "n_resamples": n_resamples,
        "n_pos": n_pos,
        "n_neg": n_neg,
    }
