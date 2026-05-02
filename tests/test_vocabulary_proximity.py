"""Tests for Layer 6 vocabulary proximity (Touchstone Standard Section 5.6).

Layer 6 measures per-sentence content-word overlap with source text.
Marked DIRECTIONAL in v1.0 (Standard Section 5.6) — surfaces lexical
overlap but cannot distinguish original analysis from fabrication.

Note: ``w in source_lower`` uses Python substring matching, so a
content word ``cat`` is considered present if source contains
``catalog``. Vault behaviour preserved.
"""

from __future__ import annotations

from clarethium_touchstone.measure import vocabulary_proximity

# ---------------------------------------------------------------------------
# Output shape contract
# ---------------------------------------------------------------------------


def test_output_shape_is_well_formed() -> None:
    """All required fields present with correct types."""
    result = vocabulary_proximity(
        "Performance improved across all systems present here today.",
        "Performance improved.",
    )
    assert isinstance(result["mean_proximity"], float)
    assert isinstance(result["per_sentence_proximity"], list)
    assert all(isinstance(s, float) for s in result["per_sentence_proximity"])


def test_output_keys_are_exact_set() -> None:
    """No extra fields leak from the vault implementation."""
    result = vocabulary_proximity(
        "Performance improved across all systems present here today.",
        "Performance improved.",
    )
    assert set(result.keys()) == {"mean_proximity", "per_sentence_proximity"}


def test_empty_doc_returns_zero_mean_empty_list() -> None:
    """Empty document: mean is 0.0, per-sentence list is empty."""
    result = vocabulary_proximity("", "Source has revenue customers growth too.")
    assert result["mean_proximity"] == 0.0
    assert result["per_sentence_proximity"] == []


def test_no_qualifying_sentences_returns_zero() -> None:
    """All sentences too short (< 5 words): well-defined zero."""
    result = vocabulary_proximity("Short. Tiny.", "Source content with multiple distinct words.")
    assert result["mean_proximity"] == 0.0
    assert result["per_sentence_proximity"] == []


# ---------------------------------------------------------------------------
# Boundary cases for proximity
# ---------------------------------------------------------------------------


def test_doc_identical_to_source_yields_one() -> None:
    """When document equals source, every content word is present in source.

    All per-sentence scores must be 1.0 and mean_proximity == 1.0.
    """
    text = (
        "Performance improved measurably across all dimensions of the system. "
        "Customers returned consistently to the platform across all regions."
    )
    result = vocabulary_proximity(text, text)
    assert result["mean_proximity"] == 1.0
    assert all(s == 1.0 for s in result["per_sentence_proximity"])


def test_disjoint_vocabularies_yield_zero() -> None:
    """Document with vocabulary entirely disjoint from source: mean = 0.0."""
    src = "Apple banana cherry date elderberry fig grape kiwi lemon mango nut."
    text = "Wolves bears tigers lions panthers cheetahs leopards across territories."
    result = vocabulary_proximity(text, src)
    assert result["mean_proximity"] == 0.0


def test_empty_source_marks_all_low_proximity() -> None:
    """Empty source: no content words can match → all zeros."""
    text = "Performance improved measurably across all dimensions of the system."
    result = vocabulary_proximity(text, "")
    assert result["mean_proximity"] == 0.0
    assert result["per_sentence_proximity"] == [0.0]


# ---------------------------------------------------------------------------
# Vault-fidelity: substring matching is generous
# ---------------------------------------------------------------------------


def test_substring_match_is_generous() -> None:
    """Vault behaviour: ``w in source_lower`` is a Python substring check.

    A content word ``cat`` is considered grounded if source contains
    ``catalog`` because the substring ``cat`` exists inside ``catalog``.
    Pinned because this affects interpretation of the score.
    """
    src = "The catalog contained important data."
    # Content words (≥3 chars, no stop words) from output:
    # ['cat', 'appears', 'within', 'documents']
    # 'cat' substring of 'catalog' → True
    # 'appears' not in src → False
    # 'within' not in src → False
    # 'documents' not in src → False
    # Score: 1/4 = 0.25
    text = "The cat appears within the documents."
    result = vocabulary_proximity(text, src)
    assert result["per_sentence_proximity"] == [0.25]
    assert result["mean_proximity"] == 0.25


def test_empty_source_multi_sentence_all_zero() -> None:
    """Empty source with multiple qualifying sentences: each yields 0.0."""
    text = (
        "First valid sentence with multiple content words present here today. "
        "Second valid sentence has many more distinct content words available. "
        "Third valid sentence completes the demonstration of multi-sentence input."
    )
    result = vocabulary_proximity(text, "")
    assert result["per_sentence_proximity"] == [0.0, 0.0, 0.0]
    assert result["mean_proximity"] == 0.0


def test_case_insensitive_matching() -> None:
    """Source is lowercased before matching; doc tokens are also lowercased."""
    text = "Revenue rose substantially across departments multiple periods."
    src = "REVENUE ROSE SUBSTANTIALLY ACROSS DEPARTMENTS MULTIPLE PERIODS."
    result = vocabulary_proximity(text, src)
    assert result["mean_proximity"] == 1.0


# ---------------------------------------------------------------------------
# Per-sentence behaviour
# ---------------------------------------------------------------------------


def test_per_sentence_list_length_matches_qualifying_sentences() -> None:
    """One score per qualifying (≥5 word) sentence."""
    text = (
        "Revenue rose significantly throughout the year. "
        "Margins improved across all sections of the business. "
        "Customers returned consistently to the platform throughout."
    )
    result = vocabulary_proximity(text, "Revenue rose.")
    assert len(result["per_sentence_proximity"]) == 3


def test_short_sentences_excluded_from_scoring() -> None:
    """Sentences with fewer than 5 tokens are dropped before scoring."""
    text = "Brief. This longer sentence has more than five tokens easily here today."
    result = vocabulary_proximity(text, "Source text matching some words.")
    # Only one qualifying sentence → only one per-sentence score
    assert len(result["per_sentence_proximity"]) == 1


def test_mean_is_arithmetic_mean_of_per_sentence_scores() -> None:
    """mean_proximity = mean(per_sentence_proximity), rounded to 3 decimals."""
    src = "Revenue rose."
    text = (
        "Revenue rose significantly throughout this calendar year. "
        "Margins improved across all sections of the business."
    )
    result = vocabulary_proximity(text, src)
    expected = round(
        sum(result["per_sentence_proximity"]) / len(result["per_sentence_proximity"]),
        3,
    )
    assert result["mean_proximity"] == expected


# ---------------------------------------------------------------------------
# Faithful vs unfaithful contrast
# ---------------------------------------------------------------------------


def test_faithful_paraphrase_higher_proximity_than_fabrication() -> None:
    """Adversarial discrimination: faithful paraphrase outranks
    invented content from the same source.
    """
    src = (
        "Revenue increased substantially across all reporting segments. "
        "Customer retention improved meaningfully in fiscal year metrics. "
        "Margins expanded considerably across major business units."
    )
    faithful = (
        "Revenue increased substantially across reporting segments today. "
        "Customer retention improved meaningfully across fiscal metrics. "
        "Margins expanded considerably across major business units."
    )
    fabricated = (
        "Carbon emissions plummeted dramatically across factories yesterday. "
        "Wildlife populations rebounded across protected forest sanctuaries. "
        "Solar capacity tripled rapidly across emerging markets globally."
    )
    faithful_r = vocabulary_proximity(faithful, src)
    fab_r = vocabulary_proximity(fabricated, src)
    assert faithful_r["mean_proximity"] > fab_r["mean_proximity"]
    # Faithful should be near 1.0; fabricated near 0.0
    assert faithful_r["mean_proximity"] > 0.8
    assert fab_r["mean_proximity"] < 0.3


# ---------------------------------------------------------------------------
# Rounding contract
# ---------------------------------------------------------------------------


def test_per_sentence_scores_rounded_to_three_decimals() -> None:
    """Each per-sentence score rounded to 3 decimal places (storage parity
    with the headline mean).
    """
    src = "Apple banana cherry date elderberry fig grape kiwi mango nut."
    text = (
        "Apple banana cherry date elderberry fig grape kiwi mango together. "
        "Carbon emissions plummeted across factories everywhere globally yesterday."
    )
    result = vocabulary_proximity(text, src)
    for s in result["per_sentence_proximity"]:
        assert s == round(s, 3)
