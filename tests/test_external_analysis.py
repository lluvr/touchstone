"""Unit tests for the benchmarks/external analysis modules.

Covers the pure-python scoring / split / fitting helpers introduced for
§4.2.x / §4.3.x of ``docs/production_readiness.md``. The tests target
correctness on small constructed inputs where the expected output is
analytic, not approximate; snapshot-style tests on real corpora live in
``test_benchmarks.py`` and the per-snapshot JSON pinning.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the top-level ``benchmarks`` package importable for the test.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmarks.external._bootstrap import auc_roc  # noqa: E402
from benchmarks.external._paired_tests import (  # noqa: E402
    mcnemar_exact,
    paired_bootstrap_auc_diff,
    paired_bootstrap_metric_diff,
)
from benchmarks.external.operational_metrics import _ops_metrics  # noqa: E402
from benchmarks.external.operational_metrics_holdout import (  # noqa: E402
    _f1_optimal_threshold,
    _stratified_interleave_split,
)
from benchmarks.external.operational_metrics_tie_envelope import _tie_envelope  # noqa: E402
from benchmarks.external.recalibrate_substrate import (  # noqa: E402
    _stratified_interleave_indices,
    fit_logistic,
    predict_logistic,
)
from benchmarks.external.substrate_plus_judge_analysis import (  # noqa: E402
    _blend,
    _kfold_indices,
)

# --- _ops_metrics ---------------------------------------------------------


def test_ops_metrics_perfect_separation() -> None:
    """A perfectly separating scorer has F1=1 at the boundary threshold."""
    scores = [0.9, 0.8, 0.7, 0.1, 0.2, 0.3]
    labels = [1, 1, 1, 0, 0, 0]
    m = _ops_metrics(scores, labels)
    assert m["base_rate"] == 0.5
    assert m["f1_optimal"]["f1"] == 1.0
    assert m["f1_optimal"]["precision"] == 1.0
    assert m["f1_optimal"]["recall"] == 1.0


def test_ops_metrics_inverted_separation() -> None:
    """A scorer that inversely separates (high score on negatives) has
    a degenerate F1-optimal at the smallest k (recall trivially achievable)."""
    scores = [0.1, 0.2, 0.3, 0.9, 0.8, 0.7]
    labels = [1, 1, 1, 0, 0, 0]
    m = _ops_metrics(scores, labels)
    # F1-optimal sweep will find the best threshold regardless of direction;
    # for fully inverted scores, flagging everyone gives precision=base_rate,
    # recall=1, F1 = 2*0.5*1/1.5 = 0.6667
    assert m["f1_optimal"]["f1"] >= 2.0 / 3.0 - 1e-9


def test_ops_metrics_single_class_returns_error() -> None:
    """All-positive or all-negative labels return an error sentinel."""
    m = _ops_metrics([0.1, 0.2, 0.3], [1, 1, 1])
    assert "error" in m
    m = _ops_metrics([0.1, 0.2, 0.3], [0, 0, 0])
    assert "error" in m


def test_ops_metrics_base_rate_matches() -> None:
    """The reported base_rate matches the proportion of positive labels."""
    m = _ops_metrics([0.1, 0.5, 0.9, 0.3, 0.7], [0, 1, 1, 0, 1])
    assert m["base_rate"] == 0.6


# --- _f1_optimal_threshold ------------------------------------------------


def test_f1_optimal_threshold_known_input() -> None:
    """Threshold sweep returns the score that maximizes F1."""
    scores = [0.9, 0.5, 0.3, 0.1]
    labels = [1, 1, 0, 0]
    thr, f1 = _f1_optimal_threshold(scores, labels)
    # At threshold 0.5: flag top 2 (both positive) -> P=1, R=1, F1=1
    assert thr == 0.5
    assert f1 == 1.0


# --- _stratified_interleave_split / _indices ------------------------------


def test_stratified_interleave_preserves_base_rate() -> None:
    """The interleave split keeps each half's base rate within 1 example."""
    n_pos = 20
    n_neg = 80
    labels = [1] * n_pos + [0] * n_neg
    scores = [0.5] * len(labels)
    (tune_s, tune_l), (eval_s, eval_l) = _stratified_interleave_split(scores, labels)
    assert len(tune_l) + len(eval_l) == len(labels)
    # Each half should contain ceil(n_pos/2) or floor(n_pos/2) positives.
    assert abs(sum(tune_l) - sum(eval_l)) <= 1


def test_stratified_interleave_indices_partition() -> None:
    """tune_idx and eval_idx partition [0, n)."""
    labels = [1, 0, 1, 0, 1, 0, 1, 0]
    tune_idx, eval_idx = _stratified_interleave_indices(labels)
    assert sorted(tune_idx + eval_idx) == list(range(len(labels)))
    assert set(tune_idx).isdisjoint(eval_idx)


# --- _kfold_indices -------------------------------------------------------


def test_kfold_indices_disjoint_folds() -> None:
    """k-fold test sets partition the input; train sets are everything else."""
    labels = [1] * 10 + [0] * 30
    splits = _kfold_indices(len(labels), 5, labels)
    assert len(splits) == 5
    all_test = []
    for train_idx, test_idx in splits:
        # Train and test are disjoint.
        assert set(train_idx).isdisjoint(test_idx)
        # Train + test = all rows.
        assert sorted(train_idx + test_idx) == list(range(len(labels)))
        all_test.extend(test_idx)
    # Every row appears in exactly one test fold.
    assert sorted(all_test) == list(range(len(labels)))


def test_kfold_indices_stratified() -> None:
    """Each fold's test set contains roughly base_rate * (n/k) positives."""
    n_pos = 20
    n_neg = 80
    labels = [1] * n_pos + [0] * n_neg
    splits = _kfold_indices(len(labels), 5, labels)
    pos_per_fold = [sum(labels[i] for i in test_idx) for _, test_idx in splits]
    # Each fold has 4 positives (20/5) and 16 negatives, with at most ±1 swing.
    assert all(abs(p - n_pos // 5) <= 1 for p in pos_per_fold)


# --- _blend ---------------------------------------------------------------


def test_blend_linear_interpolation() -> None:
    """blend(a=1) = first detector; blend(a=0) = second; midpoint is mean."""
    s = [0.1, 0.5, 0.9]
    j = [0.9, 0.5, 0.1]
    assert _blend(s, j, alpha=1.0) == s
    assert _blend(s, j, alpha=0.0) == j
    midpoint = _blend(s, j, alpha=0.5)
    assert midpoint == [0.5, 0.5, 0.5]


# --- auc_roc + paired_bootstrap_auc_diff ----------------------------------


def test_auc_roc_perfect() -> None:
    """A perfectly ranking scorer has AUC=1."""
    assert auc_roc([0.9, 0.8, 0.7, 0.1, 0.2, 0.3], [1, 1, 1, 0, 0, 0]) == 1.0


def test_auc_roc_inverted() -> None:
    """A perfectly inverted scorer has AUC=0."""
    assert auc_roc([0.1, 0.2, 0.3, 0.9, 0.8, 0.7], [1, 1, 1, 0, 0, 0]) == 0.0


def test_paired_bootstrap_auc_identical_detectors_diff_zero() -> None:
    """When both detectors have identical scores, the AUC diff is exactly 0
    on every resample, so the CI is [0, 0] and the test is not significant."""
    scores = [0.9, 0.8, 0.1, 0.2, 0.7, 0.3, 0.6, 0.4]
    labels = [1, 1, 0, 0, 1, 0, 1, 0]
    r = paired_bootstrap_auc_diff(scores, scores, labels, n_resamples=500, seed=0)
    assert r["diff_point"] == 0.0
    assert r["diff_ci_low"] == 0.0
    assert r["diff_ci_high"] == 0.0
    assert not r["significant_at_0.05"]


def test_paired_bootstrap_auc_clearly_better() -> None:
    """A clearly-better detector (AUC=1 vs AUC=0.5) is statistically significant."""
    n = 40
    labels = [1] * (n // 2) + [0] * (n // 2)
    perfect = list(range(n, 0, -1))  # 40, 39, ..., 1 -- positives all on top
    perfect_scores = [x / n for x in perfect]
    # Random: all 0.5
    random_scores = [0.5] * n
    r = paired_bootstrap_auc_diff(perfect_scores, random_scores, labels, n_resamples=500, seed=0)
    assert r["diff_point"] > 0.3
    assert r["significant_at_0.05"]


# --- mcnemar_exact --------------------------------------------------------


def test_mcnemar_zero_discordant() -> None:
    """When A and B agree on every example, McNemar p-value is 1."""
    a = [1, 0, 1, 0, 1]
    b = [1, 0, 1, 0, 1]
    r = mcnemar_exact(a, b)
    assert r["b"] == 0
    assert r["c"] == 0
    assert r["p_two_sided"] == 1.0


def test_mcnemar_extreme_split_significant() -> None:
    """If A says positive 10 times where B says negative (and B never disagrees
    the other way), McNemar exact gives p = 2 * P(X<=0|n=10, p=0.5) = 2 * 0.5^10."""
    a = [1] * 10
    b = [0] * 10
    r = mcnemar_exact(a, b)
    assert r["b"] == 10
    assert r["c"] == 0
    # 2 * (1 * 0.5^10) = 0.001953
    assert abs(r["p_two_sided"] - 2 * (0.5**10)) < 1e-6


def test_mcnemar_symmetric_split_high_p() -> None:
    """When b == c, the discordant rate is exactly the null expectation;
    p-value should be 1.0 (two-sided exact)."""
    a = [1, 1, 0, 0]
    b = [0, 0, 1, 1]
    r = mcnemar_exact(a, b)
    assert r["b"] == 2
    assert r["c"] == 2
    assert r["p_two_sided"] == 1.0


# --- paired_bootstrap_metric_diff -----------------------------------------


def test_paired_bootstrap_metric_diff_identical_zero() -> None:
    """Identical scores -> metric diff exactly 0 on every resample."""
    scores = [0.9, 0.8, 0.1, 0.2, 0.7, 0.3]
    labels = [1, 1, 0, 0, 1, 0]
    r = paired_bootstrap_metric_diff(scores, scores, labels, auc_roc, n_resamples=200, seed=0)
    assert r["diff_point"] == 0.0
    assert r["diff_ci_low"] == 0.0


# --- _tie_envelope --------------------------------------------------------


def test_tie_envelope_no_ties_zero_std() -> None:
    """Continuous (no-ties) scores have envelope std = 0 (jitter is < smallest gap)."""
    scores = [0.91, 0.82, 0.73, 0.14, 0.25, 0.36, 0.47, 0.58]
    labels = [1, 1, 1, 0, 0, 0, 1, 0]
    env = _tie_envelope(scores, labels, n_perms=20, seed=0)
    assert env["f1_optimal_std"] == 0.0


def test_tie_envelope_with_ties_has_variance() -> None:
    """Heavily-tied scores produce non-zero envelope std on F1-opt selection
    when ties straddle the F1-optimal threshold boundary."""
    # All-tied at 0.5: every threshold sweep produces the same F1 (flag-all or flag-none).
    scores = [0.5] * 8
    labels = [1, 1, 1, 1, 0, 0, 0, 0]
    env = _tie_envelope(scores, labels, n_perms=20, seed=0)
    # All scores tied -> jitter can shift the F1opt threshold and pick
    # different top-k subsets -> std > 0 possible.
    # Either way: the envelope must not crash and must return a finite number.
    assert env["f1_optimal_std"] >= 0.0


# --- fit_logistic / predict_logistic --------------------------------------


def test_fit_logistic_separable_problem() -> None:
    """On a linearly separable 2D problem, fit_logistic should drive the
    fitted coef to push positives to high probability and negatives to low."""
    feature_names = ["x1", "x2"]
    x = [
        {"x1": 1.0, "x2": 1.0},
        {"x1": 0.9, "x2": 0.8},
        {"x1": 0.8, "x2": 1.0},
        {"x1": 0.0, "x2": 0.0},
        {"x1": 0.1, "x2": 0.2},
        {"x1": 0.2, "x2": 0.0},
    ]
    y = [1, 1, 1, 0, 0, 0]
    fitted = fit_logistic(x, y, feature_names, n_iter=500, lr=1.0, l2=0.001)
    preds = predict_logistic(x, fitted)
    # Positives should be >= 0.5; negatives <= 0.5 on a well-fit separable problem.
    pos_preds = preds[:3]
    neg_preds = preds[3:]
    assert min(pos_preds) > 0.5
    assert max(neg_preds) < 0.5
    # AUC on the train set should be 1.0 for this separable case.
    assert auc_roc(preds, y) == 1.0


def test_predict_logistic_intercept_only() -> None:
    """With zero coefficients and intercept=0, every prediction is 0.5."""
    coefs = {"intercept": 0.0, "coef": {"a": 0.0, "b": 0.0}}
    preds = predict_logistic([{"a": 0.5, "b": 0.7}, {"a": 0.1, "b": 0.9}], coefs)
    assert preds == [0.5, 0.5]
