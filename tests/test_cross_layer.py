"""Cross-layer consistency tests.

Multiple layers share text-processing helpers (``_split_sentences_simple``,
``_content_words``, ``_tokenize_words``, ``_STOP_WORDS``). These tests
verify that:

* Layers using the same helper see consistent output for identical inputs
* Behaviour at API boundaries (Unicode, all-stop-words, edge characters)
  is documented and pinned
"""

from __future__ import annotations

from clarethium_touchstone.measure import (
    _content_words,
    _split_sentences_simple,
    _tokenize_words,
    information_novelty,
    presentation_features,
    vocabulary_proximity,
)

# ---------------------------------------------------------------------------
# Cross-layer sentence count parity
# ---------------------------------------------------------------------------


def test_layer_6_per_sentence_count_matches_simple_splitter() -> None:
    """Layer 6 produces one score per qualifying sentence as defined by
    the shared splitter.
    """
    text = (
        "## Section\n"
        "First sentence has many words present here today globally.\n"
        "Second sentence also has multiple distinct content words available.\n"
        "Third sentence repeats some content from earlier sentences entirely."
    )
    expected_n = len(_split_sentences_simple(text))
    result = vocabulary_proximity(text, "src")
    assert len(result["per_sentence_proximity"]) == expected_n


def test_layers_6_and_9_use_same_qualifying_sentence_definition() -> None:
    """Layers 6 and 9 both filter to ≥5-token sentences; both should drop
    short fragments equally.
    """
    text_with_short = (
        "Brief. Tiny. "
        "First valid sentence has many distinct content words present here. "
        "Second valid sentence also has multiple distinct content words. "
        "Third valid sentence completes the demonstration of input length."
    )
    # Layer 6 sees 3 qualifying sentences (the 3 "valid" ones)
    r6 = vocabulary_proximity(text_with_short, "src")
    assert len(r6["per_sentence_proximity"]) == 3
    # Layer 9 also sees 3 sentences. We can verify indirectly: with 3
    # fully-novel sentences, mean_novelty must be > 0.5.
    r9 = information_novelty(text_with_short)
    assert r9["mean_novelty"] > 0.5


# ---------------------------------------------------------------------------
# Unicode handling (vault behaviour, pinned)
# ---------------------------------------------------------------------------


def test_tokenize_drops_non_ascii_characters() -> None:
    """Vault behaviour: ``[a-zA-Z']+`` only matches ASCII letters.

    Non-ASCII characters split words: ``café`` → ``caf``; ``naïve`` →
    ``na`` + ``ve``; ``Zürich`` → ``z`` + ``rich``. Pinned because this
    affects token counts on internationalised text.
    """
    words = _tokenize_words("Café was opened. Zürich offices failed.")
    assert "caf" in words  # café truncated
    assert "café" not in words  # no native unicode letters
    assert "rich" in words  # Zürich split
    assert "z" in words  # the Z survives the split


def test_content_words_drops_non_ascii_characters() -> None:
    """``_content_words`` uses ``[a-z]{3,}`` so non-ASCII letters split
    tokens and short fragments fall below the 3-char floor.
    """
    words = _content_words("Café was opened. Naïve approach failed.")
    # 'caf' is 3+ chars, kept; 'na' (from naïve) is 2 chars, dropped
    assert "caf" in words
    assert "na" not in words


# ---------------------------------------------------------------------------
# Empty / degenerate inputs across layers
# ---------------------------------------------------------------------------


def test_empty_text_safe_across_all_layers() -> None:
    """Every implemented layer must handle empty text without raising."""
    presentation_features("")
    information_novelty("")
    vocabulary_proximity("", "")
    # If any of these raised, the test would fail before reaching here.


def test_all_stop_words_text_yields_empty_qualifying_set() -> None:
    """A document made entirely of stop words yields no content words and
    therefore an empty per-sentence list in Layer 6.
    """
    # 5+ tokens to pass length filter, but all are stop words
    stop_only = "the and the and the and the and the."
    result = vocabulary_proximity(stop_only, "any source content here today.")
    # Layer 6 skips sentences with no content words
    assert result["per_sentence_proximity"] == []
    assert result["mean_proximity"] == 0.0


# ---------------------------------------------------------------------------
# Layer 7's _tokenize_words vs Layer 9's _content_words
# ---------------------------------------------------------------------------


def test_tokenize_words_keeps_stop_words_content_words_drops_them() -> None:
    """Layer 7's tokeniser keeps stop words (used for TTR diversity);
    Layer 9's content-word extractor drops them (used for novelty).
    Different goals, different filters.
    """
    text = "the cat sat on the mat the mat the mat."
    tokens = _tokenize_words(text)  # for TTR
    contents = _content_words(text)  # for novelty
    # Tokens include 'the', 'on'
    assert "the" in tokens
    assert "on" in tokens
    # Content words drop stop words
    assert "the" not in contents
    assert "on" not in contents
    # 'cat', 'mat', 'sat' keep in content words ('on' is 2 chars anyway)
    assert "cat" in contents
    assert "mat" in contents


# ---------------------------------------------------------------------------
# Layer 7 helpers used internally by Layer 6/9
# ---------------------------------------------------------------------------


def test_split_sentences_simple_strips_markdown_consistently() -> None:
    """Markdown stripping in the simple splitter affects all consuming
    layers identically.
    """
    text = (
        "## Heading\n\n"
        "**bold sentence** with content five tokens minimum here today. "
        "*italic sentence* with content five tokens minimum here today."
    )
    sents = _split_sentences_simple(text)
    # Heading stripped; both sentences kept (5+ tokens after marker strip)
    assert len(sents) == 2
    # No markdown markers leak
    assert all("**" not in s for s in sents)
    assert all("##" not in s for s in sents)


# ---------------------------------------------------------------------------
# Layer 1c vs Layer 8: assertion vocabulary divergence
# ---------------------------------------------------------------------------


def test_layer_8_calibration_set_strictly_extends_layer_1c() -> None:
    """Layer 8 uses a broader assertion set than Layer 1c. Phrases like
    ``indisputably``, ``conclusively``, ``definitively``, ``inevitably``,
    ``it is clear that``, ``no doubt``, ``demonstrates that`` are matched
    by Layer 8 but NOT by Layer 1c (vault preserves Layer 1c's narrower
    set to keep its validated reference distributions stable).
    """
    from clarethium_touchstone.measure import (
        _CALIBRATION_ASSERTION_RE,
        _REG_COMPILED,
    )

    layer_8_only_phrases = [
        "Indisputably this is correct.",
        "Conclusively the result holds.",
        "Definitively the approach works.",
        "Inevitably this must succeed.",
        "It is clear that this works.",
        "There is no doubt about this result.",
        "This demonstrates that approach works.",
    ]
    layer_1c_assertion_re = _REG_COMPILED["ASSERTION"]
    for phrase in layer_8_only_phrases:
        # Layer 8 catches the phrase
        assert _CALIBRATION_ASSERTION_RE.findall(phrase), f"Layer 8 should match: {phrase!r}"
        # Layer 1c's narrower set may still catch SOME phrases (e.g., "must"
        # is in both), but the targeted lexical items above shouldn't fire.
        # Verify by checking that the targeted word itself isn't matched
        # by Layer 1c.
        targeted_word = phrase.split()[0].rstrip(",.").lower()
        layer_1c_matches = layer_1c_assertion_re.findall(targeted_word)
        assert not layer_1c_matches, (
            f"Layer 1c should NOT match {targeted_word!r} (it's a Layer 8-only marker)"
        )
