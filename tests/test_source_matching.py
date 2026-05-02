"""Tests for Layer 4 source matching (Touchstone Standard Section 5.4).

These tests exercise the validated behaviour documented in the methodology:
* 0% false positive rate when document equals source (every number found)
* Type-aware matching for percentages, dollar amounts, multipliers, integers
* Year filtering (1990-2035 treated as years, not data)
* Word count filtering (numbers in word-count callouts ignored)
* Comma-formatted integer variants (2,000 ↔ 2000)
"""

from __future__ import annotations

import pytest

from clarethium_touchstone.measure import source_matching

# ---------------------------------------------------------------------------
# Validated invariant: 0% FPR when document == source
# ---------------------------------------------------------------------------


def test_self_source_zero_false_positives() -> None:
    """When document equals source, every number must be found.

    Validated by EXP-081: 0/309 false positives across 5 self-source files.
    """
    text = (
        "Acme Corp reported revenue of $143.8B in fiscal year 2024, up 12% "
        "year-over-year. Operating margin improved to 18.4% on a 2.5x "
        "expansion in enterprise contracts. Cash reserves grew from $45,000 "
        "to $67,500 over the period."
    )
    result = source_matching(text, text)

    assert result["unsourced_rate"] == 0.0
    assert result["n_unsourced"] == 0
    assert result["n_in_source"] == result["n_total"]
    assert result["unsourced_details"] == []


def test_self_source_finds_multiple_types() -> None:
    """Self-source must find numbers across all canonical types."""
    text = (
        "Revenue grew 12% to $143.8B with a 2.5x multiplier on margins. "
        "The 18,400 employees produced 47.3 thousand units."
    )
    result = source_matching(text, text)
    assert result["unsourced_rate"] == 0.0
    assert result["n_total"] >= 4  # at least percentage, dollar, multiplier, decimal


# ---------------------------------------------------------------------------
# Fabrication detection
# ---------------------------------------------------------------------------


def test_unsourced_number_detected() -> None:
    """A number not in source must be flagged."""
    source = "Revenue was $100M and grew 10% year-over-year."
    output = (
        "Revenue was $100M and grew 10% year-over-year, with margin reaching "
        "23.7% (a fabricated figure not present in source)."
    )
    result = source_matching(output, source)
    assert result["unsourced_rate"] > 0
    assert result["n_unsourced"] >= 1
    unsourced_values = {d["value"] for d in result["unsourced_details"]}
    assert "23.7" in unsourced_values


def test_completely_fabricated_output() -> None:
    """An output with no overlap with source should have high unsourced rate."""
    source = "Apple grew. Revenue increased."
    output = (
        "Microsoft reported $211B revenue with 15% YoY growth and a 35.6% "
        "operating margin across 220,000 employees."
    )
    result = source_matching(output, source)
    assert result["unsourced_rate"] == 1.0


# ---------------------------------------------------------------------------
# Type-aware matching
# ---------------------------------------------------------------------------


def test_percentage_requires_percent_sign() -> None:
    """Percentage 18% must not match a bare integer 18 in source."""
    source = "There were 18 customers in the segment."
    output = "Margin was 18%."
    result = source_matching(output, source)
    # The 18% is not in source (only "18 customers" exists)
    assert result["n_unsourced"] == 1


def test_dollar_requires_dollar_sign() -> None:
    """Dollar amount $45,000 must not match bare 45000 in source."""
    source = "We sold 45,000 units in Q3."
    output = "Revenue reached $45,000."
    result = source_matching(output, source)
    # The $45,000 not in source as dollar
    assert result["n_unsourced"] == 1


def test_multiplier_requires_x_suffix() -> None:
    """Multiplier 2x must not match bare integer 2 in source."""
    source = "We had 2 product lines."
    output = "Margin grew 2x year over year."
    result = source_matching(output, source)
    assert result["n_unsourced"] == 1


# ---------------------------------------------------------------------------
# Comma-formatted variants
# ---------------------------------------------------------------------------


def test_comma_variant_matches_raw_integer() -> None:
    """Source has 2,000 and output has 2000: should match."""
    source = "Headcount reached 2,000 by year end."
    output = "Headcount reached 2000."
    result = source_matching(output, source)
    assert result["n_unsourced"] == 0


def test_raw_integer_matches_comma_variant() -> None:
    """Source has 2000 and output has 2,000: should match via comma insertion."""
    source = "Headcount reached 2000 by year end."
    output = "Headcount reached 2,000."
    result = source_matching(output, source)
    assert result["n_unsourced"] == 0


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def test_years_filtered() -> None:
    """Years (1990-2035) must not count as data numerical claims."""
    source = "Revenue was discussed."
    output = "In 2024 revenue grew. The company was founded in 1995."
    result = source_matching(output, source)
    # Years are filtered, so total should be 0
    assert result["n_total"] == 0


def test_word_count_callouts_filtered() -> None:
    """Word-count callouts must not count as data: filter drops them entirely
    so they affect neither n_total nor unsourced_details.
    """
    source = "Brief content."
    output = "Word count: 1,247 words. Other content here without other digits."
    result = source_matching(output, source)
    assert result["n_total"] == 0
    assert result["unsourced_details"] == []


def test_word_count_filter_does_not_drop_distant_numbers() -> None:
    """A word-count callout filters numbers within ~60 chars (the vault's
    proximity window). Numbers further away are NOT affected.
    """
    source = "Revenue was $100M."
    # Pad to push $100M outside the 60-char window of the word-count callout
    output = (
        "Revenue was $100M. "
        + ("And then context unrelated to counting. " * 3)
        + "Word count: 1,247 words."
    )
    result = source_matching(output, source)
    # $100M is far enough from "Word count" to escape the filter
    assert result["n_total"] == 1
    assert result["n_unsourced"] == 0


# ---------------------------------------------------------------------------
# Empty inputs and edge cases
# ---------------------------------------------------------------------------


def test_empty_output() -> None:
    """Empty output yields zero numbers and zero rate."""
    result = source_matching("", "Source has $100M revenue.")
    assert result["n_total"] == 0
    assert result["unsourced_rate"] == 0.0
    assert result["unsourced_details"] == []


def test_no_numbers_in_output() -> None:
    """Prose-only output has zero numerical claims to verify."""
    result = source_matching("Just text without any digits.", "Source has $100M.")
    assert result["n_total"] == 0
    assert result["unsourced_rate"] == 0.0


def test_empty_source_marks_all_unsourced() -> None:
    """Empty source: every output number is flagged unsourced."""
    result = source_matching("Revenue $100M, growth 10%, 2.5x margin.", "")
    assert result["n_total"] >= 3
    assert result["n_in_source"] == 0
    assert result["unsourced_rate"] == 1.0


# ---------------------------------------------------------------------------
# Vault-fidelity behaviour pinning
#
# These tests document algorithm choices preserved from the operator's
# research vault. Changing them requires a Standard version bump
# (Section 10). Failing one of these tests means the algorithm drifted.
# ---------------------------------------------------------------------------


def test_claimed_range_dedup_prevents_phantom_subtokens() -> None:
    """A "2.58%" match must not also yield phantom 2.58 (decimal) and 2/258
    (integer) extractions. Higher-priority patterns claim the range first.
    """
    # Self-source: every number must be found, AND there must be exactly
    # one number found (the percentage), not multiple.
    text = "Operating margin reached 2.58% in the most recent reporting period."
    result = source_matching(text, text)
    assert result["n_total"] == 1
    assert result["unsourced_rate"] == 0.0


def test_year_boundary_inclusive_at_1990_and_2035() -> None:
    """Year filter range is inclusive: 1990 and 2035 are filtered as years,
    1989 and 2036 are kept as data values.
    """
    in_range_text = "We launched in 1990 and ramped through 2035 across markets."
    out_range_text = "Founded in 1989 with a 2036 horizon for the next product."
    src = "Reference."
    in_range = source_matching(in_range_text, src)
    out_range = source_matching(out_range_text, src)
    assert in_range["n_total"] == 0
    assert out_range["n_total"] == 2  # 1989 and 2036 are integers, kept


def test_multiplier_uses_substring_match_in_source() -> None:
    """Vault behaviour: multiplier source matching uses unanchored substring
    search, so "2x" output matches "12x" in source. This is generous and
    intentional; pinned here so future tightening is visible.
    """
    out = "Margin grew 2x year over year for sustained profitable growth here."
    src = "Margin grew 12x year over year for sustained profitable growth here."
    result = source_matching(out, src)
    # "2x" output is marked in-source because "12x" contains the substring
    assert result["n_unsourced"] == 0


def test_percentage_decimal_falls_back_to_integer_part() -> None:
    """Vault behaviour: when an output percentage like 10.5% is not found
    verbatim in source, the algorithm searches for the integer part (10%).
    This is generous and intentional; pinned here so future tightening is
    visible.
    """
    out = "Margin reached 10.5% in Q3 after seasonal demand normalised steadily."
    src = "Margin reached 10% in Q3 after seasonal demand normalised steadily."
    result = source_matching(out, src)
    # 10.5% is accepted because 10% is in source
    assert result["n_unsourced"] == 0


# ---------------------------------------------------------------------------
# Precision indicator
# ---------------------------------------------------------------------------


def test_precision_low_when_few_numbers() -> None:
    """Precision is 'low' when total numbers < 10."""
    result = source_matching("Revenue was $100M and grew 10%.", "Source.")
    assert result["precision"] == "low"


def test_precision_adequate_when_many_numbers() -> None:
    """Precision is 'adequate' when 10 <= total < 30."""
    text = " ".join(f"Metric {i} was {i * 5}% with ${i * 100}M revenue." for i in range(1, 6))
    result = source_matching(text, text)
    assert result["precision"] in ("adequate", "good")


# ---------------------------------------------------------------------------
# Output shape contract (TypedDict conformance)
# ---------------------------------------------------------------------------


def test_output_shape_is_well_formed() -> None:
    """All required fields present with correct types."""
    result = source_matching("Revenue $100M, growth 10%.", "Revenue $100M.")

    assert isinstance(result["unsourced_rate"], float)
    assert isinstance(result["n_in_source"], int)
    assert isinstance(result["n_unsourced"], int)
    assert isinstance(result["n_total"], int)
    assert result["precision"] in ("low", "adequate", "good")
    assert isinstance(result["unsourced_details"], list)

    assert result["n_in_source"] + result["n_unsourced"] == result["n_total"], (
        "in_source + unsourced must equal total"
    )

    for detail in result["unsourced_details"]:
        assert "value" in detail
        assert "type" in detail
        assert "context" in detail


# ---------------------------------------------------------------------------
# Adversarial discrimination (mini-EXP-081 reproduction)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "faithful_output,expected_max_rate",
    [
        # Faithful output cites only sourced numbers
        ("Revenue was $100M with 10% growth.", 0.0),
    ],
)
def test_faithful_outputs_have_low_unsourced_rate(
    faithful_output: str, expected_max_rate: float
) -> None:
    """Faithful outputs (only sourced numbers) should have low unsourced rate."""
    source = "Revenue was $100M with 10% growth in Q4."
    result = source_matching(faithful_output, source)
    assert result["unsourced_rate"] <= expected_max_rate


def test_embellished_output_has_high_unsourced_rate() -> None:
    """Embellished outputs (added unsourced numbers) should have higher rate."""
    source = "Revenue was $100M with 10% growth in Q4."
    embellished = (
        "Revenue was $100M with 10% growth in Q4. According to McKinsey, "
        "the market grew 47.3%, with $250B in TAM and a 3.5x competitive "
        "moat over the next 18,000 customers."
    )

    faithful_result = source_matching("Revenue was $100M with 10% growth.", source)
    embellished_result = source_matching(embellished, source)

    assert embellished_result["unsourced_rate"] > faithful_result["unsourced_rate"]
    assert embellished_result["n_unsourced"] > faithful_result["n_unsourced"]
