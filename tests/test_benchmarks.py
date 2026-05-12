"""Benchmark smoke tests.

Runs the validation benchmarks against the bundled ground-truth
corpus and asserts non-fragile invariants. The point is to catch
regressions that would meaningfully change detection accuracy, not
to pin exact numbers (the dated snapshot files in
``benchmarks/*/results/`` serve that purpose via diff review).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the top-level ``benchmarks`` package importable for the test.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def test_exp_095_benchmark_runs_to_completion() -> None:
    """The EXP-095 benchmark runs against the bundled corpus without
    raising. All 13 ground-truth outputs are processed.
    """
    from benchmarks.exp_095_grounding.run import aggregate, run_all

    results = run_all()
    assert len(results) == 13, "expected all 13 ground-truth outputs to run"

    agg = aggregate(results)
    assert agg["n"] == 13
    assert agg["n_with_full_manual"] == 7


def test_exp_095_p_direction_agreement_is_perfect() -> None:
    """Touchstone Layer 11 must agree with manual classification on the
    binary "any projected content present?" question across all
    ground-truth outputs.

    This is the key product invariant: a tool that misses projected
    content half the time is useless, regardless of how close its
    proportion estimates are. The benchmark currently shows 100%
    direction agreement; the threshold here is 0.9 so this test
    catches a meaningful regression but is not fragile to small
    classification-edge changes.
    """
    from benchmarks.exp_095_grounding.run import aggregate, run_all

    agg = aggregate(run_all())
    rate = agg["p_direction_agreement_rate"]
    assert rate is not None
    assert rate >= 0.9, (
        f"P-direction agreement dropped to {rate} - Touchstone "
        f"started disagreeing with manual on whether P > 0. Investigate."
    )


def test_exp_095_close_agreement_with_detector_v031() -> None:
    """Touchstone Layer 11 closely reproduces the validated detector
    v0.3.1 results from the EXP-095 paper. Mean absolute error per
    category should stay below 0.10 (current baseline: 0.02-0.04).

    A regression past 0.10 means the extraction has drifted from the
    reference implementation in a way the per-layer unit tests
    didn't catch. Investigate before merging.
    """
    from benchmarks.exp_095_grounding.run import aggregate, run_all

    agg = aggregate(run_all())
    mae = agg["mae_vs_detector_v031"]
    for category in ("G", "F", "P"):
        assert mae[category] <= 0.10, (
            f"MAE vs detector v0.3.1 on {category} grew to {mae[category]} - "
            f"the extraction has drifted beyond the documented detector."
        )


def test_exp_095_predictions_in_unit_range() -> None:
    """Sanity: every predicted G/F/P value is a valid probability
    (in [0, 1]); proportions per output sum to ~1.0 (within rounding).
    """
    from benchmarks.exp_095_grounding.run import run_all

    for r in run_all():
        for cat in ("G", "F", "P"):
            v = r.predicted[cat]
            assert 0.0 <= v <= 1.0, f"output {r.output_id} {cat}={v} out of [0,1]"
        total = sum(r.predicted.values())
        assert abs(total - 1.0) < 0.01 or total == 0.0, (
            f"output {r.output_id} proportions sum to {total}, expected ~1.0"
        )


@pytest.mark.parametrize(
    "model_substring,expected_high_p",
    [
        # When manual classification shows substantial P, Touchstone should
        # also detect P > 0 (not zero). xAI on BLS run 1 has manual P=48%.
        ("xai BLS run 1", True),
    ],
)
def test_exp_095_canonical_high_p_case_detected(
    model_substring: str, expected_high_p: bool
) -> None:
    """Pinning canonical cases: outputs that the manual classification
    showed high projected content should not regress to P=0.
    """
    from benchmarks.exp_095_grounding.run import run_all

    # Find xAI BLS run 1 by id (output #7 per ground truth)
    target_id = 7
    matches = [r for r in run_all() if r.output_id == target_id]
    assert len(matches) == 1, f"expected exactly one match for id {target_id}"
    r = matches[0]
    if expected_high_p:
        assert r.predicted["P"] > 0, (
            f"output {r.output_id} ({r.model} on {r.topic}) had manual P=48% "
            f"but Touchstone predicts P=0 - significant detection regression"
        )


# ===========================================================================
# EXP-081 adversarial discrimination benchmark
# ===========================================================================


def test_exp_081_benchmark_runs_to_completion() -> None:
    """The EXP-081 benchmark runs against the bundled 12-doc corpus
    without raising. Faithful and embellished sets are evenly split.
    """
    from benchmarks.exp_081_discrimination.run import aggregate, run_all

    results = run_all()
    assert len(results) == 12

    agg = aggregate(results)
    assert agg["n"] == 12
    assert agg["n_faithful"] == 6
    assert agg["n_embellished"] == 6


def test_exp_081_reproduces_published_effect_size() -> None:
    """Touchstone reproduces the published d=-5.43 effect size for
    faithful-vs-embellished gap discrimination. Published CI is
    [-9.077, -4.681]; current Touchstone result is -5.238.

    The threshold here (-4.0) catches a regression that would
    meaningfully weaken the discrimination signal but tolerates
    small drift around the published point estimate. Tightening
    further than the published CI's upper bound (-4.681) would be
    fragile.
    """
    from benchmarks.exp_081_discrimination.run import aggregate, run_all

    agg = aggregate(run_all())
    d = agg["cohens_d_faithful_vs_embellished"]
    # Direction (sign) and substantial-magnitude both required.
    assert d < -4.0, (
        f"Cohen's d for faithful-vs-embellished gap regressed to {d}. "
        f"Published value -5.43 (CI [-9.077, -4.681]); current baseline -5.238."
    )


def test_exp_081_gap_direction_agreement_is_perfect() -> None:
    """Per-output: predicted gap sign matches the published gap sign
    for every doc. A faithful doc always has gap < 0; embellished > 0.
    """
    from benchmarks.exp_081_discrimination.run import aggregate, run_all

    agg = aggregate(run_all())
    assert agg["gap_direction_agreement_with_published"] == 1.0


def test_exp_081_close_agreement_with_published_metrics() -> None:
    """MAE per metric vs published values stays under 0.05 across
    unsourced_rate, gap, substance_index, presentation_index.

    Current baseline: 0.014 on unsourced_rate (driven by a small
    extraction count drift on rich sources), 0.0097 on gap, 0.0095
    on substance, 0.0 on presentation. The threshold here detects a
    real regression but tolerates expected float-rounding drift.
    """
    from benchmarks.exp_081_discrimination.run import aggregate, run_all

    agg = aggregate(run_all())
    mae = agg["mae_vs_published"]
    for metric in ("unsourced_rate", "gap", "substance_index", "presentation_index"):
        assert mae[metric] <= 0.05, (
            f"MAE on {metric} grew to {mae[metric]} - Touchstone is "
            f"diverging from the EXP-081 published values."
        )


def test_exp_081_snapshot_matches_committed_baseline() -> None:
    """Per-doc predictions byte-match the committed snapshot (drift
    detection, same pattern as EXP-095).
    """
    import json

    from benchmarks.exp_081_discrimination.run import (
        BENCHMARK_DIR,
        aggregate,
        render_report,
        run_all,
    )

    snapshot_path = BENCHMARK_DIR / "results" / "snapshot_2026-05-12.json"
    if not snapshot_path.exists():
        pytest.skip(f"baseline snapshot missing: {snapshot_path}")

    fresh = json.loads(render_report(run_all(), aggregate(run_all())))
    committed = json.loads(snapshot_path.read_text())

    fresh_pred = {p["id"]: p["predicted"] for p in fresh["per_output"]}
    committed_pred = {p["id"]: p["predicted"] for p in committed["per_output"]}
    assert fresh_pred == committed_pred, (
        "Per-doc predictions drifted from committed EXP-081 snapshot.\n"
        "Update: python -m benchmarks.exp_081_discrimination.run "
        "--output benchmarks/exp_081_discrimination/results/snapshot_NEWDATE.json"
    )


def test_exp_081_aggregate_statistics_stable() -> None:
    """Cohen's d, Hedges' g, and the 95% bootstrap CI on Cohen's d are
    deterministic given the fixed seed in ``bootstrap_ci_cohens_d``.
    Pin them so a regression in either the gap signal or the
    aggregation math is caught by CI rather than silently shifting the
    headline number.
    """
    from benchmarks.exp_081_discrimination.run import aggregate, run_all

    agg = aggregate(run_all())
    assert agg["cohens_d_faithful_vs_embellished"] == -5.238
    assert agg["hedges_g_faithful_vs_embellished"] == -4.835
    assert agg["cohens_d_bootstrap_ci_95"] == [-8.926, -4.498]


def test_exp_095_snapshot_matches_committed_baseline() -> None:
    """The committed snapshot file (results/snapshot_2026-05-03.json) must
    byte-match a fresh run. This catches silent drift: if a library
    change shifts the per-output predicted proportions, the snapshot
    diff in code review surfaces it. Re-running the benchmark to
    update the snapshot is a deliberate act, not an accident.

    To update the snapshot when a change is intentional::

        python -m benchmarks.exp_095_grounding.run \\
            --output benchmarks/exp_095_grounding/results/snapshot_$(date +%F).json
        # then review the diff and rename if accepting the change

    The test compares a single canonical filename (the 2026-05-03
    baseline) to keep the assertion stable; future-dated snapshots
    can co-exist as historical record.
    """
    import json

    from benchmarks.exp_095_grounding.run import (
        BENCHMARK_DIR,
        aggregate,
        render_report,
        run_all,
    )

    snapshot_path = BENCHMARK_DIR / "results" / "snapshot_2026-05-03.json"
    if not snapshot_path.exists():
        pytest.skip(f"baseline snapshot missing: {snapshot_path}")

    fresh = json.loads(render_report(run_all(), aggregate(run_all())))
    committed = json.loads(snapshot_path.read_text())

    # Compare per-output predictions; aggregate stats are derived.
    fresh_pred = {p["id"]: p["predicted"] for p in fresh["per_output"]}
    committed_pred = {p["id"]: p["predicted"] for p in committed["per_output"]}
    assert fresh_pred == committed_pred, (
        "Layer 11 predictions drifted from committed snapshot.\n"
        "Update: python -m benchmarks.exp_095_grounding.run "
        "--output benchmarks/exp_095_grounding/results/snapshot_NEWDATE.json"
    )
