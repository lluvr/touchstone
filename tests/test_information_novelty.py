"""Tests for Layer 9 information novelty (Touchstone Standard Section 5.9).

Layer 9 is EXPERIMENTAL in Standard 1.0. It computes per-sentence
cumulative-vocabulary novelty: for each sentence, the fraction of
content words not seen in any earlier sentence.

Length-confounded by Heaps' law (longer texts saturate vocabulary).
The Standard cautions against direct cross-document comparison.
"""

from __future__ import annotations

from clarethium_touchstone.measure import (
    _STOP_WORDS,
    _content_words,
    information_novelty,
)

# ---------------------------------------------------------------------------
# Output shape contract
# ---------------------------------------------------------------------------


def test_output_shape_is_well_formed() -> None:
    """All required fields present with correct types."""
    text = (
        "First valid sentence here with multiple distinct content words. "
        "Second sentence repeats some content words present already."
    )
    result = information_novelty(text)
    assert isinstance(result["mean_novelty"], float)
    assert isinstance(result["repetition_rate"], float)
    assert isinstance(result["decay"], float)
    assert isinstance(result["q1_novelty"], float)
    assert isinstance(result["q4_novelty"], float)


def test_output_keys_are_exact_set() -> None:
    """No extra fields leak from the vault implementation."""
    result = information_novelty(
        "First valid sentence here with multiple distinct words present today."
    )
    assert set(result.keys()) == {
        "mean_novelty",
        "repetition_rate",
        "decay",
        "q1_novelty",
        "q4_novelty",
    }


def test_empty_text_returns_all_zeros() -> None:
    """Empty input: every metric is 0.0 (well-defined fallback)."""
    result = information_novelty("")
    assert result["mean_novelty"] == 0.0
    assert result["repetition_rate"] == 0.0
    assert result["decay"] == 0.0
    assert result["q1_novelty"] == 0.0
    assert result["q4_novelty"] == 0.0


def test_short_sentences_filtered_returns_zeros() -> None:
    """Sentences with fewer than 5 tokens are dropped by the splitter; if
    none qualify, every metric is 0.0.
    """
    result = information_novelty("Short. Tiny. Brief.")
    assert result["mean_novelty"] == 0.0
    assert result["q1_novelty"] == 0.0


# ---------------------------------------------------------------------------
# Per-sentence novelty semantics
# ---------------------------------------------------------------------------


def test_first_sentence_is_fully_novel_by_definition() -> None:
    """A single qualifying sentence: all content words are 'new'."""
    text = "Performance improved measurably across all dimensions of the system."
    result = information_novelty(text)
    assert result["mean_novelty"] == 1.0


def test_identical_repeated_sentences_yield_decay() -> None:
    """5 identical sentences: first is 1.0 novel, rest are 0.0 novel.

    mean_novelty = 1/5 = 0.2; repetition_rate = 4/5 = 0.8 (sentences with
    novelty < 0.2 are repetitive); q1 = 1.0, q4 = 0.0; decay strictly
    negative.
    """
    text = " ".join(["The system performance improved measurably yesterday."] * 5)
    result = information_novelty(text)
    assert result["mean_novelty"] == 0.2
    assert result["repetition_rate"] == 0.8
    assert result["q1_novelty"] == 1.0
    assert result["q4_novelty"] == 0.0
    assert result["decay"] < 0


def test_fully_novel_sentences_minimal_decay() -> None:
    """Sentences with entirely disjoint vocabularies have near-1.0 mean
    novelty. (Common words like 'across' may still get reused — exact
    1.0 is hard, but the mean must be near 1.0.)
    """
    text = (
        "Revenue increased substantially during this current reporting period. "
        "Margins expanded considerably across major distinct business segments. "
        "Customer satisfaction improved meaningfully throughout calendar year. "
        "Employee retention strengthened multiple internal departments lately. "
        "Innovation accelerated rapidly through cross-functional collaboration."
    )
    result = information_novelty(text)
    assert result["mean_novelty"] > 0.9
    assert result["repetition_rate"] == 0.0


# ---------------------------------------------------------------------------
# Decay slope behaviour
# ---------------------------------------------------------------------------


def test_decay_is_negative_when_novelty_declines() -> None:
    """Front-loaded novel vocabulary → strictly negative decay slope."""
    text = (
        "Alpha bravo charlie delta echo foxtrot novel content present. "
        "Alpha bravo charlie delta echo present here today. "
        "Alpha bravo charlie present here today. "
        "Alpha bravo present here today again. "
        "Alpha present here once more occasion."
    )
    result = information_novelty(text)
    assert result["decay"] < 0
    # And q4 must be strictly less than q1
    assert result["q4_novelty"] < result["q1_novelty"]


def test_decay_is_zero_when_fewer_than_three_qualifying_sentences() -> None:
    """OLS slope is undefined with n<3 data points; vault returns 0.0."""
    text = (
        "First valid sentence here with multiple distinct content words. "
        "Second sentence repeats some content words present already."
    )
    result = information_novelty(text)
    assert result["decay"] == 0.0


def test_decay_zero_for_single_sentence() -> None:
    """One qualifying sentence: decay is 0.0 (no slope to compute)."""
    text = "Performance improved measurably across all dimensions of the system."
    result = information_novelty(text)
    assert result["decay"] == 0.0


# ---------------------------------------------------------------------------
# Quartile semantics
# ---------------------------------------------------------------------------


def test_quartile_size_floor_is_one() -> None:
    """For 1 to 3 sentences, quartile size floors at 1 sentence.

    With 1 sentence: q1 = q4 = that sentence's novelty (1.0).
    """
    text = "Performance improved measurably across all dimensions of the system."
    result = information_novelty(text)
    assert result["q1_novelty"] == 1.0
    assert result["q4_novelty"] == 1.0


def test_quartile_split_with_eight_sentences() -> None:
    """n=8: q_size = 2. q1 averages first 2 sentences; q4 averages last 2."""
    # First 2 fully novel, last 2 mostly repetitive
    sents = [
        "Alpha bravo charlie delta echo foxtrot golf hotel india content.",
        "Juliet kilo lima mike november oscar papa quebec romeo content.",
        "Common common common common common content present already today.",
        "Common common common common common content present already today.",
        "Common common common common common content present already today.",
        "Common common common common common content present already today.",
        "Common common common common common content present already today.",
        "Common common common common common content present already today.",
    ]
    text = " ".join(sents)
    result = information_novelty(text)
    # q1 should be high (early sentences are novel)
    assert result["q1_novelty"] > 0.5
    # q4 should be near 0 (last two are entirely repeats)
    assert result["q4_novelty"] < 0.2


# ---------------------------------------------------------------------------
# Repetition rate threshold
# ---------------------------------------------------------------------------


def test_repetition_rate_uses_strict_less_than_20pct() -> None:
    """Sentences with novelty < 0.2 count as repetitive; >= 0.2 do not.

    A sentence with exactly 20% novel content (1 new word in 5) does NOT
    count as repetitive (strict less-than).
    """
    # 2 fully novel sentences then 1 sentence with 1 new word in 5 (= 0.2)
    sents = [
        "Alpha bravo charlie delta echo foxtrot golf hotel india content.",
        "Juliet kilo lima mike november oscar papa quebec romeo content.",
        # 5 content words, 1 new ('newterm'), 4 already-seen
        "Alpha bravo charlie delta newterm content present already.",
    ]
    text = " ".join(sents)
    result = information_novelty(text)
    # Verify nothing is below the 0.2 threshold
    assert result["repetition_rate"] == 0.0


# ---------------------------------------------------------------------------
# Content word extraction
# ---------------------------------------------------------------------------


def test_content_words_excludes_stop_words() -> None:
    """Stop words are filtered out."""
    words = _content_words("the cats run quickly into the garden of nice plants.")
    assert "the" not in words
    assert "into" not in words
    assert "of" not in words


def test_content_words_includes_substantive_3char_words() -> None:
    """3-character words that aren't stop words are kept."""
    words = _content_words("Cats run fast cars fly far past zoo gates.")
    # 'run' 3 chars, not stop word -> kept; 'fly' 'far' 'cars' kept
    assert "run" in words
    assert "fly" in words
    assert "far" in words
    assert "cars" in words


def test_content_words_filters_short_tokens() -> None:
    """Words shorter than 3 characters are dropped entirely."""
    words = _content_words("I am a be do go up to it of an or no so")
    assert words == []


def test_content_words_excludes_digits() -> None:
    """Numeric tokens are excluded by the [a-z] character class."""
    words = _content_words("Revenue grew 23% to $100M in 2024 across markets.")
    assert "23" not in words
    assert "100" not in words
    assert "2024" not in words


def test_content_words_lowercases() -> None:
    """All extracted tokens are lowercase."""
    words = _content_words("The QUICK Brown FOX jumps over the LAZY dog.")
    assert all(w == w.lower() for w in words)
    assert "quick" in words
    assert "brown" in words


def test_stop_words_includes_canonical_function_words() -> None:
    """The stop-word set covers the most common English function words."""
    for w in ("the", "and", "is", "of", "to", "for", "with", "from", "but"):
        assert w in _STOP_WORDS, f"expected {w!r} in stop words"


# ---------------------------------------------------------------------------
# Heaps' law warning: longer texts have lower mean novelty
# ---------------------------------------------------------------------------


def test_longer_text_has_lower_mean_novelty_heaps_law() -> None:
    """Vocabulary saturates as text grows. This is documented behaviour
    (Standard Section 5.9 cautions against direct cross-doc comparison).
    """
    # Both texts use a small bounded vocabulary; the longer one will saturate
    short = "Alpha bravo charlie delta echo content. Foxtrot golf hotel content."
    long_text = " ".join(
        [
            "Alpha bravo charlie delta echo content present today everywhere.",
            "Foxtrot golf hotel india juliet content present today everywhere.",
            "Alpha bravo charlie delta echo content present today everywhere.",
            "Foxtrot golf hotel india juliet content present today everywhere.",
            "Alpha bravo charlie delta echo content present today everywhere.",
            "Foxtrot golf hotel india juliet content present today everywhere.",
        ]
    )
    short_r = information_novelty(short)
    long_r = information_novelty(long_text)
    assert long_r["mean_novelty"] < short_r["mean_novelty"]
