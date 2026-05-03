"""Tests for Layer 3 temporal instability (Touchstone Standard Section 5.3).

Layer 3 measures cross-version number stability. For each unique
(value, type) number pair found across primary text + comparison
regenerations, classify as stable (in all versions) or unstable
(in some but not all). Returns the unstable fraction.

Construct caveat (Standard Section 5.3 + methodology Construct
Honesty A): instability is a PROXY for fabrication, not a direct
measurement. EXP-081c showed ~46% of unstable numbers coincidentally
match source material — instability overcounts true fabrication.
Cannot detect stable fabrication (consistently wrong numbers).
"""

from __future__ import annotations

from clarethium_touchstone.measure import (
    fabrication_rate,
    temporal_instability,
)

# ---------------------------------------------------------------------------
# Output shape contract
# ---------------------------------------------------------------------------


def test_output_shape_is_well_formed() -> None:
    """All required fields present with correct types."""
    result = temporal_instability("Revenue 12%.", ["Revenue 13%."])
    assert isinstance(result["instability_rate"], float)
    assert isinstance(result["n_unstable"], int)
    assert isinstance(result["n_total"], int)
    assert isinstance(result["versions_compared"], int)


def test_output_keys_are_exact_set() -> None:
    """No extra fields leak from the vault implementation."""
    result = temporal_instability("text", ["comp"])
    assert set(result.keys()) == {
        "instability_rate",
        "n_unstable",
        "n_total",
        "versions_compared",
    }


# ---------------------------------------------------------------------------
# Empty / degenerate inputs
# ---------------------------------------------------------------------------


def test_empty_text_and_empty_comparisons() -> None:
    """Empty inputs: zero counts, zero rate, single version."""
    result = temporal_instability("", [])
    assert result["n_total"] == 0
    assert result["n_unstable"] == 0
    assert result["instability_rate"] == 0.0
    assert result["versions_compared"] == 1  # text counts as version 1


def test_text_with_no_numbers_returns_zero() -> None:
    """Text without digit-formatted numbers: zero unstable, versions counted."""
    result = temporal_instability(
        "The product launched yesterday.",
        ["The product was released yesterday."],
    )
    assert result["n_total"] == 0
    assert result["instability_rate"] == 0.0
    # versions_compared still reflects what was supplied
    assert result["versions_compared"] == 2


def test_empty_string_comparison_treats_as_zero_numbers_in_that_version() -> None:
    """An empty-string comparison contributes no numbers. Numbers from text
    that only exist there → unstable (in some but not all versions).

    Pinned because empty strings are easy to pass accidentally and the
    behaviour is intuitively unsurprising once seen but worth verifying.
    """
    text = "Revenue 12%, $100M, 25% margins."
    result = temporal_instability(text, [""])
    assert result["versions_compared"] == 2
    # All 3 text numbers are absent from the empty version → all unstable
    assert result["n_total"] == 3
    assert result["n_unstable"] == 3
    assert result["instability_rate"] == 1.0


def test_no_comparisons_yields_all_stable() -> None:
    """With zero comparisons, every number in text appears in all 1
    versions → all stable, instability_rate = 0.0.

    Documented uninformative case: callers should supply at least one
    comparison for a meaningful signal.
    """
    text = "Revenue 12%, $100M, 25% margins."
    result = temporal_instability(text, [])
    assert result["versions_compared"] == 1
    assert result["instability_rate"] == 0.0
    assert result["n_unstable"] == 0
    assert result["n_total"] == 3  # three numbers, all stable


# ---------------------------------------------------------------------------
# Stability semantics
# ---------------------------------------------------------------------------


def test_identical_regenerations_yield_zero_instability() -> None:
    """When all versions are identical, every number is stable."""
    text = "Revenue grew 12% to $143M with 25% margins."
    result = temporal_instability(text, [text, text])
    assert result["versions_compared"] == 3
    assert result["instability_rate"] == 0.0


def test_one_changed_number_yields_partial_instability() -> None:
    """Single comparison with one number changed: that pair is unstable."""
    text = "Revenue grew 12% to $100M."
    comp = "Revenue grew 12% to $200M."
    result = temporal_instability(text, [comp])
    # All numbers across versions: 12 (percentage), 100 (dollar), 200 (dollar)
    # Stable: 12 (percentage) — in both versions
    # Unstable: 100 (dollar), 200 (dollar) — only in one each
    assert result["n_total"] == 3
    assert result["n_unstable"] == 2
    assert result["instability_rate"] == round(2 / 3, 3)


def test_three_versions_with_unstable_percentage() -> None:
    """Three versions with one number that differs in each: 3 unstable
    pairs, 1 stable pair → rate = 3/4 = 0.75.
    """
    text = "Revenue grew 12% to $143M."
    comp1 = "Revenue grew 13% to $143M."
    comp2 = "Revenue grew 14% to $143M."
    result = temporal_instability(text, [comp1, comp2])
    # Numbers: (12, %), (13, %), (14, %), (143, $)
    # Stable: (143, $) only
    # Unstable: (12, %), (13, %), (14, %)
    assert result["n_total"] == 4
    assert result["n_unstable"] == 3
    assert result["instability_rate"] == 0.75


def test_versions_compared_includes_primary() -> None:
    """``versions_compared`` counts text + len(comparisons)."""
    text = "x"
    for n_comp in (0, 1, 2, 5):
        result = temporal_instability(text, ["c"] * n_comp)
        assert result["versions_compared"] == 1 + n_comp


# ---------------------------------------------------------------------------
# Filtering parity with Layer 4 / source matching
# ---------------------------------------------------------------------------


def test_year_filtering_consistent_with_layer_4() -> None:
    """Years (1990-2035) are filtered out before instability computation,
    matching the same filter used by Layer 4 source matching.
    """
    text = "In 2024, revenue grew 12%."
    comp = "In 2025, revenue grew 12%."
    result = temporal_instability(text, [comp])
    # 2024 and 2025 are filtered as years; only 12% remains, present in both → stable
    assert result["n_total"] == 1
    assert result["instability_rate"] == 0.0


def test_word_count_callouts_filtered() -> None:
    """Word-count callout numbers are filtered before instability.

    The 60-char proximity window of the word-count filter (vault-faithful)
    can also drop other nearby numbers; pad the data with distance so
    the 12% number escapes the proximity filter.
    """
    padding = "And then context unrelated to counting. " * 3
    text = f"Revenue 12%. {padding}Word count: 1,247 words."
    comp = f"Revenue 12%. {padding}Word count: 2,500 words."
    result = temporal_instability(text, [comp])
    # 1,247 and 2,500 filtered as word counts; 12% kept (outside window)
    assert result["n_total"] == 1
    assert result["instability_rate"] == 0.0


def test_type_aware_dedup_distinct_from_value_alone() -> None:
    """A number is keyed by (value, type), so '12 customers' (integer 12)
    and '12%' are distinct entries even though they share the value.
    """
    text = "Revenue 12% for 12 customers."
    # Comparison only has the percentage
    comp = "Revenue 12%."
    result = temporal_instability(text, [comp])
    # text: (12, percentage), (12, integer); comp: (12, percentage)
    # stable: (12, percentage) only
    # unstable: (12, integer)
    assert result["n_total"] == 2
    assert result["n_unstable"] == 1


# ---------------------------------------------------------------------------
# Deprecated alias
# ---------------------------------------------------------------------------


def test_fabrication_rate_alias_still_works() -> None:
    """Deprecated ``fabrication_rate`` alias (slated for v2.0 removal)
    forwards to ``temporal_instability``.
    """
    text = "Revenue 12%."
    comp = "Revenue 14%."
    via_alias = fabrication_rate(text, [comp])
    via_canonical = temporal_instability(text, [comp])
    assert via_alias == via_canonical


# ---------------------------------------------------------------------------
# Adversarial discrimination
# ---------------------------------------------------------------------------


def test_stable_text_strictly_lower_instability_than_unstable() -> None:
    """Stable regenerations have strictly lower instability than divergent
    regenerations of the same task.
    """
    base = "Revenue 12%, $100M, 25% margins, 5,000 employees, 18 months."
    stable_comp = base  # identical
    unstable_comp = "Revenue 47%, $999M, 88% margins, 9,999 employees, 47 months."

    stable_result = temporal_instability(base, [stable_comp])
    unstable_result = temporal_instability(base, [unstable_comp])
    assert stable_result["instability_rate"] < unstable_result["instability_rate"]


# ---------------------------------------------------------------------------
# Rounding contract
# ---------------------------------------------------------------------------


def test_instability_rate_rounded_to_three_decimals() -> None:
    """instability_rate rounds to 3 decimal places."""
    text = "Revenue grew 12% to $100M."
    comp = "Revenue grew 14% to $200M."
    result = temporal_instability(text, [comp])
    assert result["instability_rate"] == round(result["instability_rate"], 3)
