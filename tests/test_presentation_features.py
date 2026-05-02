"""Tests for Layer 7 presentation features (Touchstone Standard Section 5.7).

Layer 7 returns five descriptive (non-evaluative) features describing
the SHAPE of the prose: vocabulary diversity, reading level, formatting
intensity, register stance, and rhetorical naming.
"""

from __future__ import annotations

import pytest

from clarethium_touchstone.measure import (
    _count_syllables,
    _extract_headings_simple,
    _split_sentences_simple,
    _strip_markdown,
    _tokenize_words,
    presentation_features,
)

# ---------------------------------------------------------------------------
# Output shape contract
# ---------------------------------------------------------------------------


def test_output_shape_is_well_formed() -> None:
    """All required fields present with correct types."""
    result = presentation_features("The system fails because of bugs in the code.")
    assert isinstance(result["type_token_ratio"], float)
    assert isinstance(result["fk_grade"], float)
    assert isinstance(result["formatting_density"], float)
    assert isinstance(result["assertiveness_ratio"], float)
    assert isinstance(result["named_concept_count"], int)


def test_output_keys_are_exact_set() -> None:
    """No extra fields leak from the vault implementation."""
    result = presentation_features("Some text with content.")
    assert set(result.keys()) == {
        "type_token_ratio",
        "fk_grade",
        "formatting_density",
        "assertiveness_ratio",
        "named_concept_count",
    }


def test_empty_text_uses_defaults() -> None:
    """Empty input: zero metrics, assertiveness defaults to 0.5 (neutral)."""
    result = presentation_features("")
    assert result["type_token_ratio"] == 0.0
    assert result["fk_grade"] == 0.0
    assert result["formatting_density"] == 0.0
    assert result["assertiveness_ratio"] == 0.5
    assert result["named_concept_count"] == 0


# ---------------------------------------------------------------------------
# Type-token ratio
# ---------------------------------------------------------------------------


def test_ttr_all_unique_words_yields_one() -> None:
    """All-unique tokens give TTR = 1.0."""
    result = presentation_features("alpha beta gamma delta epsilon zeta")
    assert result["type_token_ratio"] == 1.0


def test_ttr_repeated_words_yield_fraction() -> None:
    """3 unique tokens out of 5 total = 0.4."""
    result = presentation_features("the the the dog dog")
    assert result["type_token_ratio"] == 0.4


def test_ttr_case_insensitive() -> None:
    """Tokeniser lowercases, so 'The' and 'the' collapse."""
    result = presentation_features("The dog. The dog. The dog.")
    # 2 unique types (the, dog), 6 tokens → 1/3 ≈ 0.333
    assert result["type_token_ratio"] == round(2 / 6, 4)


# ---------------------------------------------------------------------------
# FK grade level
# ---------------------------------------------------------------------------


def test_fk_grade_simple_text_low() -> None:
    """Short common words yield low FK grade."""
    text = "The cat sat on the mat. The dog ran fast. We had fun today."
    result = presentation_features(text)
    assert result["fk_grade"] < 5.0


def test_fk_grade_complex_text_high() -> None:
    """Long polysyllabic words yield high FK grade."""
    text = (
        "Phenomenological epistemology necessarily presupposes transcendental "
        "subjectivity through intentional consciousness directed at "
        "intersubjective phenomena across temporally extended horizons."
    )
    result = presentation_features(text)
    assert result["fk_grade"] > 15.0


def test_fk_grade_complex_higher_than_simple() -> None:
    """FK grade ranks complex prose strictly above simple prose."""
    simple = presentation_features("The cat sat on the mat. The dog ran fast.")
    complex_t = presentation_features(
        "Phenomenological epistemology necessarily presupposes transcendental "
        "subjectivity through intentional consciousness."
    )
    assert complex_t["fk_grade"] > simple["fk_grade"]


def test_fk_grade_zero_for_empty_text() -> None:
    """Empty text yields FK grade 0.0 (not the formula's negative constant)."""
    assert presentation_features("")["fk_grade"] == 0.0


# ---------------------------------------------------------------------------
# Formatting density
# ---------------------------------------------------------------------------


def test_formatting_density_zero_for_plain_prose() -> None:
    """Pure prose with no markdown has formatting density 0.0."""
    text = "Just plain prose without any markdown markers anywhere in the text."
    result = presentation_features(text)
    assert result["formatting_density"] == 0.0


def test_formatting_density_counts_bold_runs() -> None:
    """Bold ``**...**`` runs contribute to formatting density."""
    text = "**one** **two** **three** plain words follow here in the prose body."
    result = presentation_features(text)
    # 3 bold + 0 list + 0 heading = 3 marks
    assert result["formatting_density"] > 0


def test_formatting_density_counts_list_items() -> None:
    """Bullet and numbered list markers contribute."""
    text = "- item one\n- item two\n* item three\n1. item four\nclosing prose here."
    result = presentation_features(text)
    assert result["formatting_density"] > 0


def test_formatting_density_counts_headings() -> None:
    """## and ### headings contribute (h1, h4 do not via simple extractor)."""
    text = "## Heading\nSome body content follows the heading marker.\n## Another"
    result = presentation_features(text)
    assert result["formatting_density"] > 0


def test_formatting_density_normalised_per_100_words() -> None:
    """Density is per 100 words with a 1-word floor."""
    # Long text with a single bold marker → very low density per 100 words
    text = "**bold** " + " ".join(["word"] * 200)
    result = presentation_features(text)
    # 1 bold / (200/100) = 0.5
    assert result["formatting_density"] == 0.5


# ---------------------------------------------------------------------------
# Assertiveness ratio
# ---------------------------------------------------------------------------


def test_assertiveness_neutral_when_no_register_markers() -> None:
    """Default 0.5 when neither hedges nor asserts fire."""
    text = "The product launched yesterday and customers received it well."
    result = presentation_features(text)
    assert result["assertiveness_ratio"] == 0.5


def test_assertiveness_high_when_only_asserts() -> None:
    """Pure assertive language gives ratio 1.0."""
    text = "Always must always must always. Definitively guarantees ensures proves."
    result = presentation_features(text)
    assert result["assertiveness_ratio"] == 1.0


def test_assertiveness_low_when_only_hedges() -> None:
    """Pure hedging language gives ratio 0.0."""
    text = "Perhaps might possibly maybe seems suggest indicate appears tend to."
    result = presentation_features(text)
    assert result["assertiveness_ratio"] == 0.0


def test_assertiveness_mid_when_balanced() -> None:
    """Balanced hedge/assert mix gives intermediate ratio."""
    # 3 asserts (always, must, definitively), 3 hedges (might, possibly, perhaps)
    text = "Performance always must definitively scale. It might possibly perhaps fail."
    result = presentation_features(text)
    # 3/(3+3) = 0.5
    assert result["assertiveness_ratio"] == 0.5


# ---------------------------------------------------------------------------
# Named concept count
# ---------------------------------------------------------------------------


def test_named_concept_two_title_words_plus_concept_noun() -> None:
    """Pattern requires 2+ Title Case words before the concept noun."""
    # 'Sunk Cost Fallacy' = 2 Title Case + Fallacy → match
    text = "The Sunk Cost Fallacy biases every long-running decision."
    # Note 'The' counts as a Title Case word too (sentence-start capital)
    result = presentation_features(text)
    assert result["named_concept_count"] == 1


def test_named_concept_single_title_word_not_matched() -> None:
    """Single Title Case word + concept noun does NOT match (vault behaviour)."""
    # 'Streetlight Effect' alone in mid-sentence: only 'Streetlight' before 'Effect'
    text = "Light cones bias us through streetlight Effect biases everywhere."
    # 'streetlight' is lowercase; even if Title Case alone it wouldn't match
    # without a second Title Case word before Effect
    result = presentation_features(text)
    assert result["named_concept_count"] == 0


def test_named_concept_sentence_start_the_inflates_match() -> None:
    """Vault behaviour: 'The X Concept' matches because 'The' counts as a
    Title Case word ('The' + 'X' = 2+ Title Case before the concept noun).
    Pinned because this affects external interpretation of the count.
    """
    text = "The Productivity Paradox persists. The Sunk Cost Fallacy compounds errors over time."
    result = presentation_features(text)
    # Both 'The Productivity Paradox' and 'The Sunk Cost Fallacy' match
    assert result["named_concept_count"] == 2


def test_named_concept_count_zero_for_plain_prose() -> None:
    """No matches in prose without Title Case + concept-noun patterns."""
    text = "the system failed yesterday because of a power outage in the data center."
    result = presentation_features(text)
    assert result["named_concept_count"] == 0


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "word,expected",
    [
        ("cat", 1),
        ("dog", 1),
        ("the", 1),  # 3-letter rule: 1
        ("hello", 2),
        ("counting", 2),
        ("understanding", 4),
        ("encyclopedia", 5),
        ("a", 1),  # short: 1
        ("", 1),  # max(1, ...) floor
    ],
)
def test_count_syllables(word: str, expected: int) -> None:
    """Syllable counter returns expected counts on canonical inputs."""
    assert _count_syllables(word) == expected


def test_strip_markdown_removes_emphasis_and_link_targets() -> None:
    """Markdown stripper preserves text and link labels, drops syntax."""
    result = _strip_markdown("**bold** *italic* `code` [label](url) # heading")
    assert "**" not in result
    assert "(url)" not in result
    assert "[" not in result
    assert "label" in result
    assert "bold" in result


def test_tokenize_words_excludes_digits() -> None:
    """Tokeniser keeps only ``[a-zA-Z']+`` runs (no numeric tokens)."""
    text = "Revenue grew 23% to $100M in 2024 across all markets."
    words = _tokenize_words(text)
    assert "23" not in words
    assert "100" not in words
    assert "2024" not in words
    assert "revenue" in words
    assert "markets" in words


def test_tokenize_words_lowercases() -> None:
    """All tokens are lowercased."""
    words = _tokenize_words("The QUICK brown Fox.")
    assert words == ["the", "quick", "brown", "fox"]


def test_split_sentences_simple_filters_short() -> None:
    """Sentences with fewer than 5 tokens are dropped."""
    text = "Short. This sentence has well over five tokens easily here."
    sents = _split_sentences_simple(text)
    assert len(sents) == 1
    assert "Short." not in sents


def test_split_sentences_simple_filters_word_count_lines() -> None:
    """Lines containing 'word count' are dropped from sentence list."""
    text = "First valid sentence with enough tokens here. Word count: 1247 words."
    sents = _split_sentences_simple(text)
    assert all("word count" not in s.lower() for s in sents)


def test_extract_headings_simple_returns_h2_and_h3_only() -> None:
    """Only ## and ### are extracted (h1 and h4+ skipped)."""
    text = "# h1\n## h2 first\n### h3 sub\n#### h4 deeper\n## h2 second"
    headings = _extract_headings_simple(text)
    assert headings == ["h2 first", "h3 sub", "h2 second"]


def test_extract_headings_simple_strips_emphasis() -> None:
    """Markdown emphasis markers in heading text are stripped."""
    text = "## **Bold heading** with emphasis"
    headings = _extract_headings_simple(text)
    assert headings == ["Bold heading with emphasis"]
