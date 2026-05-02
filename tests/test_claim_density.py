"""Tests for Layer 2 claim density (Touchstone Standard Section 5.2).

Layer 2 counts sentences containing digit-formatted numerical claims
or causal-language markers, normalised per 1000 words.
"""

from __future__ import annotations

import pytest

from clarethium_touchstone.measure import claim_density

# ---------------------------------------------------------------------------
# Output shape contract
# ---------------------------------------------------------------------------


def test_output_shape_is_well_formed() -> None:
    """All required fields present with correct types."""
    result = claim_density("Revenue grew 10%. The product is great.")
    assert isinstance(result["numerical_per_1kw"], float)
    assert isinstance(result["causal_per_1kw"], float)
    assert isinstance(result["n_numerical"], int)
    assert isinstance(result["n_causal"], int)
    assert isinstance(result["n_words"], int)


def test_empty_text_returns_zero() -> None:
    """Empty input yields zero counts and zero densities."""
    result = claim_density("")
    assert result["n_numerical"] == 0
    assert result["n_causal"] == 0
    assert result["n_words"] == 0
    assert result["numerical_per_1kw"] == 0.0
    assert result["causal_per_1kw"] == 0.0


# ---------------------------------------------------------------------------
# Numerical claim detection
# ---------------------------------------------------------------------------


def test_percentage_counted() -> None:
    """A sentence with a percentage counts as one numerical claim."""
    text = "Revenue grew 23% in the last quarter of fiscal year reporting."
    result = claim_density(text)
    assert result["n_numerical"] == 1


def test_dollar_amount_counted() -> None:
    """A sentence with a dollar amount counts as one numerical claim."""
    text = "Total revenue reached $143.8B last year across all segments."
    result = claim_density(text)
    assert result["n_numerical"] == 1


def test_multiplier_counted() -> None:
    """A sentence with a multiplier (Nx) counts as one numerical claim."""
    text = "Operating margin expanded 2.5x year over year reliably this period."
    result = claim_density(text)
    assert result["n_numerical"] == 1


def test_duration_counted() -> None:
    """A sentence with a duration unit counts as one numerical claim."""
    text = "The migration completed in 14 days across the entire infrastructure."
    result = claim_density(text)
    assert result["n_numerical"] == 1


def test_entity_count_counted() -> None:
    """A sentence with N <entity> counts as a numerical claim."""
    text = "We surveyed 250 companies across the European software market."
    result = claim_density(text)
    assert result["n_numerical"] == 1


def test_multiple_numbers_one_sentence_count_once() -> None:
    """A sentence with multiple numbers counts as ONE numerical claim sentence."""
    text = "Revenue of $100M grew 15% over 6 months across 25 customers steadily."
    result = claim_density(text)
    assert result["n_numerical"] == 1


def test_word_form_numbers_not_counted() -> None:
    """Word-form numbers ('twenty percent') are NOT detected (known recall gap)."""
    text = "Revenue grew twenty percent year over year throughout the period."
    result = claim_density(text)
    assert result["n_numerical"] == 0


def test_no_numbers_yields_zero() -> None:
    """Pure prose without digits has zero numerical claims."""
    text = "The product is excellent and the team works hard every single day."
    result = claim_density(text)
    assert result["n_numerical"] == 0


# ---------------------------------------------------------------------------
# Causal claim detection
# ---------------------------------------------------------------------------


def test_because_marker_counted() -> None:
    """'Because' triggers a causal claim count."""
    text = "We migrated because the legacy system was reaching end of life."
    result = claim_density(text)
    assert result["n_causal"] == 1


def test_due_to_marker_counted() -> None:
    """'Due to' triggers a causal claim count."""
    text = "Performance degraded due to memory pressure on the primary database."
    result = claim_density(text)
    assert result["n_causal"] == 1


def test_results_in_marker_counted() -> None:
    """'Results in' triggers a causal claim count."""
    text = "Higher cache hit rates result in improved response latency overall."
    result = claim_density(text)
    assert result["n_causal"] == 1


def test_therefore_marker_counted() -> None:
    """'Therefore' triggers a causal claim count."""
    text = "Tests pass cleanly. Therefore the migration is safe to deploy now."
    result = claim_density(text)
    assert result["n_causal"] >= 1


def test_multiple_causal_markers_one_sentence_count_once() -> None:
    """Multiple markers in a single sentence count as ONE causal claim."""
    text = (
        "Latency dropped because cache hit rates improved, which therefore "
        "results in better user experience over the entire production fleet."
    )
    result = claim_density(text)
    assert result["n_causal"] == 1


def test_no_causal_markers_yields_zero() -> None:
    """Descriptive prose without causal language has zero causal claims."""
    text = "The product launched yesterday. Customers received it well overall."
    result = claim_density(text)
    assert result["n_causal"] == 0


def test_since_followed_by_digit_not_counted_as_causal() -> None:
    """'Since 2020' is temporal, not causal: must NOT trigger the marker."""
    text = "Revenue has been growing since 2020 across all five business segments."
    result = claim_density(text)
    # The pattern excludes "since <digit>" so this should not count as causal
    assert result["n_causal"] == 0


# ---------------------------------------------------------------------------
# Density normalisation
# ---------------------------------------------------------------------------


def test_density_normalised_per_1000_words() -> None:
    """Density is computed as count / (words/1000), rounded to 1 decimal."""
    # Construct ~1000 words with exactly 5 numerical claims
    sentences = ["Revenue grew 10% this quarter alone." for _ in range(5)]
    filler = " ".join(["word"] * 950)
    text = " ".join(sentences) + " " + filler
    result = claim_density(text)
    assert result["n_numerical"] == 5
    # Density should be ~5 per 1000 words
    assert 4.0 <= result["numerical_per_1kw"] <= 6.0


def test_short_text_uses_floor() -> None:
    """Very short text uses 100-word floor to avoid extreme densities."""
    text = "Revenue grew 10% in the last quarter."  # ~7 words
    result = claim_density(text)
    # With 0.1 floor, density = 1 / 0.1 = 10.0 maximum (not 1/0.007 = 143)
    assert result["numerical_per_1kw"] <= 10.0


def test_word_count_via_word_boundary() -> None:
    """Word count uses \\b\\w+\\b regex, so punctuation does not inflate."""
    text = "One two three four five."
    result = claim_density(text)
    assert result["n_words"] == 5


# ---------------------------------------------------------------------------
# Sentence segmentation behaviour
# ---------------------------------------------------------------------------


def test_short_sentences_filtered() -> None:
    """Sentences shorter than 30 characters are dropped from analysis."""
    # "Yes. 10%." is too short — both fragments under 30 chars
    text = "Yes. 10%."
    result = claim_density(text)
    assert result["n_numerical"] == 0


def test_markdown_headings_skipped() -> None:
    """Markdown heading lines are not counted as sentences."""
    text = "# Header with 50% growth\n\nThe section has no other claims here at all."
    result = claim_density(text)
    # Heading is skipped, body has no numerical claim
    assert result["n_numerical"] == 0


def test_list_markers_stripped() -> None:
    """Bullet/numbered list markers are stripped before sentence analysis."""
    text = (
        "- Revenue grew 23% across all segments in the latest reporting period.\n"
        "* Costs declined 15% due to operational efficiency gains across teams.\n"
    )
    result = claim_density(text)
    assert result["n_numerical"] == 2
    assert result["n_causal"] == 1


# ---------------------------------------------------------------------------
# Combined behaviour
# ---------------------------------------------------------------------------


def test_mixed_claims_counted_independently() -> None:
    """A sentence with both number and causal marker counts in BOTH categories."""
    text = "Revenue grew 23% because operational efficiency improved across teams."
    result = claim_density(text)
    assert result["n_numerical"] == 1
    assert result["n_causal"] == 1


@pytest.mark.parametrize(
    "text,expected_numerical,expected_causal",
    [
        ("Revenue grew 10% this quarter due to strong demand from buyers.", 1, 1),
        ("Costs declined. Margin improved. Operations stabilised over time.", 0, 0),
        (
            "$143B revenue with 12% growth, driven by 25 new product launches.",
            1,
            1,
        ),
    ],
)
def test_canonical_examples(text: str, expected_numerical: int, expected_causal: int) -> None:
    """Canonical inputs produce expected counts."""
    result = claim_density(text)
    assert result["n_numerical"] == expected_numerical
    assert result["n_causal"] == expected_causal
