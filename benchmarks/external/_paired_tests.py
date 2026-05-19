"""Paired statistical tests for cross-detector comparison.

Every detector-ordering claim in §4.2 / §4.3 needs paired-test support
or it is just two numbers that happen to differ. Pure-python (stdlib
only) implementations of:

- ``paired_bootstrap_auc_diff``: paired stratified bootstrap on the AUC
  difference between two detectors evaluated on the same labels. Each
  resample draws the SAME row indices for both detectors so the
  difference's variance reflects detector disagreement, not sample
  noise. Returns the percentile CI of the difference + a two-sided
  bootstrap p-value (twice the smaller tail mass beyond zero).

- ``mcnemar_exact``: McNemar's exact binomial test on paired binary
  verdicts at a chosen threshold. Conditional on the discordant pairs
  count (b + c), the count of A-positive-B-negative outcomes is
  Binomial(b + c, 0.5) under H0 of equal verdict-flip rates. Two-sided
  exact p-value, no continuity-correction approximation needed.

- ``paired_bootstrap_metric_diff``: generic paired bootstrap for any
  metric of the form ``f(scores, labels) -> float``. Used for F1-optimal,
  P@R90, R@P90, lift-at-top-K differences.

All bootstrap functions use a stratified resample (positives and
negatives sampled independently within their respective indices) so
each resample preserves the base rate, matching the stratified-bootstrap
discipline already established in ``_bootstrap.py``.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from math import comb

from benchmarks.external._bootstrap import auc_roc


def _stratified_resample_indices(
    pos_indices: list[int], neg_indices: list[int], rng: random.Random
) -> list[int]:
    n_pos = len(pos_indices)
    n_neg = len(neg_indices)
    rs_pos = [pos_indices[rng.randrange(n_pos)] for _ in range(n_pos)]
    rs_neg = [neg_indices[rng.randrange(n_neg)] for _ in range(n_neg)]
    return rs_pos + rs_neg


def paired_bootstrap_auc_diff(
    scores_a: list[float],
    scores_b: list[float],
    labels: list[int],
    *,
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict[str, float | int | bool]:
    """Paired stratified bootstrap on AUC(A) - AUC(B).

    Each resample draws the same row indices for both detectors. The
    distribution of per-resample (auc_a - auc_b) gives the paired
    sampling variance of the difference, which is what should be used
    to test "is A better than B" rather than the marginal variances of
    each detector.
    """
    if len(scores_a) != len(scores_b) or len(scores_a) != len(labels):
        raise ValueError("scores_a, scores_b, labels must have equal length")
    pos_indices = [i for i, lab in enumerate(labels) if lab == 1]
    neg_indices = [i for i, lab in enumerate(labels) if lab == 0]
    if not pos_indices or not neg_indices:
        return {
            "auc_a": 0.5,
            "auc_b": 0.5,
            "diff_point": 0.0,
            "diff_ci_low": 0.0,
            "diff_ci_high": 0.0,
            "p_two_sided": 1.0,
            "n_resamples": n_resamples,
            "n_pos": len(pos_indices),
            "n_neg": len(neg_indices),
            "significant_at_0.05": False,
        }

    auc_a_point = auc_roc(scores_a, labels)
    auc_b_point = auc_roc(scores_b, labels)

    rng = random.Random(seed)
    diffs: list[float] = []
    for _ in range(n_resamples):
        rs_idx = _stratified_resample_indices(pos_indices, neg_indices, rng)
        rs_labels = [labels[i] for i in rs_idx]
        rs_scores_a = [scores_a[i] for i in rs_idx]
        rs_scores_b = [scores_b[i] for i in rs_idx]
        diffs.append(auc_roc(rs_scores_a, rs_labels) - auc_roc(rs_scores_b, rs_labels))

    diffs.sort()
    tail = (1.0 - confidence) / 2.0
    low_idx = max(0, int(tail * n_resamples) - 1)
    high_idx = min(n_resamples - 1, int((1.0 - tail) * n_resamples))
    low = diffs[low_idx]
    high = diffs[high_idx]
    # Two-sided percentile p-value: twice the smaller tail's mass beyond zero.
    n_le_zero = sum(1 for d in diffs if d <= 0)
    n_ge_zero = sum(1 for d in diffs if d >= 0)
    p_two_sided = 2.0 * min(n_le_zero, n_ge_zero) / n_resamples
    p_two_sided = min(p_two_sided, 1.0)
    return {
        "auc_a": round(auc_a_point, 4),
        "auc_b": round(auc_b_point, 4),
        "diff_point": round(auc_a_point - auc_b_point, 4),
        "diff_ci_low": round(low, 4),
        "diff_ci_high": round(high, 4),
        "p_two_sided": round(p_two_sided, 4),
        "n_resamples": n_resamples,
        "n_pos": len(pos_indices),
        "n_neg": len(neg_indices),
        "significant_at_0.05": bool(low > 0 or high < 0),
    }


def mcnemar_exact(
    verdicts_a: list[int], verdicts_b: list[int], labels: list[int] | None = None
) -> dict[str, float | int]:
    """McNemar's exact binomial test on paired binary verdicts.

    ``verdicts_a`` and ``verdicts_b`` are 0/1 arrays of length n. The
    statistic is conditional on the discordant pairs only: b = count of
    rows where A=1 and B=0; c = count where A=0 and B=1. Under H0
    (equal verdict-flip rates), b ~ Binomial(b + c, 0.5); the
    two-sided exact p-value is ``2 * P(X <= min(b, c))`` clipped to 1.

    ``labels`` is accepted for API symmetry with the bootstrap helpers
    but not required by McNemar (the test compares verdicts, not
    correctness). Pass it for self-documenting calls.
    """
    if len(verdicts_a) != len(verdicts_b):
        raise ValueError("verdicts_a and verdicts_b must have equal length")
    if labels is not None and len(labels) != len(verdicts_a):
        raise ValueError("labels length must match verdicts when provided")
    b = sum(1 for va, vb in zip(verdicts_a, verdicts_b, strict=True) if va == 1 and vb == 0)
    c = sum(1 for va, vb in zip(verdicts_a, verdicts_b, strict=True) if va == 0 and vb == 1)
    n_diff = b + c
    if n_diff == 0:
        return {"b": 0, "c": 0, "n_discordant": 0, "p_two_sided": 1.0}
    k = min(b, c)
    # P(X <= k) under Binomial(n_diff, 0.5)
    cdf = sum(comb(n_diff, i) for i in range(k + 1)) * (0.5**n_diff)
    p_two_sided = min(1.0, 2.0 * cdf)
    return {
        "b": b,
        "c": c,
        "n_discordant": n_diff,
        "p_two_sided": round(p_two_sided, 6),
    }


def paired_bootstrap_metric_diff(
    scores_a: list[float],
    scores_b: list[float],
    labels: list[int],
    metric_fn: Callable[[list[float], list[int]], float],
    *,
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict[str, float | int | bool]:
    """Paired stratified bootstrap on metric_fn(A) - metric_fn(B).

    Generic version for any scalar metric. Each resample draws the same
    row indices for both detectors. The metric is recomputed on the
    resample for each detector, and the difference is recorded. Returns
    the percentile CI of the difference + two-sided p-value.
    """
    if len(scores_a) != len(scores_b) or len(scores_a) != len(labels):
        raise ValueError("scores_a, scores_b, labels must have equal length")
    pos_indices = [i for i, lab in enumerate(labels) if lab == 1]
    neg_indices = [i for i, lab in enumerate(labels) if lab == 0]
    if not pos_indices or not neg_indices:
        return {
            "metric_a": 0.0,
            "metric_b": 0.0,
            "diff_point": 0.0,
            "diff_ci_low": 0.0,
            "diff_ci_high": 0.0,
            "p_two_sided": 1.0,
            "n_resamples": n_resamples,
            "significant_at_0.05": False,
        }
    metric_a_point = metric_fn(scores_a, labels)
    metric_b_point = metric_fn(scores_b, labels)

    rng = random.Random(seed)
    diffs: list[float] = []
    for _ in range(n_resamples):
        rs_idx = _stratified_resample_indices(pos_indices, neg_indices, rng)
        rs_labels = [labels[i] for i in rs_idx]
        rs_scores_a = [scores_a[i] for i in rs_idx]
        rs_scores_b = [scores_b[i] for i in rs_idx]
        try:
            a = metric_fn(rs_scores_a, rs_labels)
            b = metric_fn(rs_scores_b, rs_labels)
            diffs.append(a - b)
        except Exception:
            continue

    if not diffs:
        return {
            "metric_a": round(metric_a_point, 4),
            "metric_b": round(metric_b_point, 4),
            "diff_point": round(metric_a_point - metric_b_point, 4),
            "diff_ci_low": 0.0,
            "diff_ci_high": 0.0,
            "p_two_sided": 1.0,
            "n_resamples": 0,
            "significant_at_0.05": False,
        }

    diffs.sort()
    tail = (1.0 - confidence) / 2.0
    low = diffs[max(0, int(tail * len(diffs)) - 1)]
    high = diffs[min(len(diffs) - 1, int((1.0 - tail) * len(diffs)))]
    n_le_zero = sum(1 for d in diffs if d <= 0)
    n_ge_zero = sum(1 for d in diffs if d >= 0)
    p_two_sided = min(1.0, 2.0 * min(n_le_zero, n_ge_zero) / len(diffs))
    return {
        "metric_a": round(metric_a_point, 4),
        "metric_b": round(metric_b_point, 4),
        "diff_point": round(metric_a_point - metric_b_point, 4),
        "diff_ci_low": round(low, 4),
        "diff_ci_high": round(high, 4),
        "p_two_sided": round(p_two_sided, 6),
        "n_resamples": len(diffs),
        "significant_at_0.05": bool(low > 0 or high < 0),
    }
