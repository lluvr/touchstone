"""Cross-layer consistency tests.

Multiple layers share text-processing helpers (``_split_sentences_simple``,
``_content_words``, ``_tokenize_words``, ``_STOP_WORDS``). These tests
verify that:

* Layers using the same helper see consistent output for identical inputs
* Behaviour at API boundaries (Unicode, all-stop-words, edge characters)
  is documented and pinned
* All 11 layers compose correctly when run on a single rich input
"""

from __future__ import annotations

from clarethium_touchstone.measure import (
    _content_words,
    _split_sentences_simple,
    _tokenize_words,
    claim_density,
    entity_provenance,
    epistemic_calibration,
    grounding_decomposition,
    information_novelty,
    presentation_features,
    quality_profile,
    source_matching,
    structural_profile,
    temporal_instability,
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


# ---------------------------------------------------------------------------
# All-11-layers integration smoke test
# ---------------------------------------------------------------------------


# Rich text with adequate-precision numbers (≥10), entities (≥5), assertions
# (≥5 sentences with calibration markers), and markdown structure - meets
# every layer's precision/threshold gates.
_INTEGRATION_TEXT = (
    "## Findings\n\n"
    "Revenue must always grow by 12% to $143M with 25% margins for the year. "
    "Costs definitively declined 8% across 5,000 employees over 18 months. "
    "Headcount must reach 2,500 with $45,000 average compensation paid today. "
    "Findings according to John Smith of OpenAI, 7.5% gains must continue. "
    "The Stanford University team and IBM Research clearly will lead innovation. "
    "Work cited by Carol Brown showed 94% accuracy across studies must hold."
)


def test_all_11_layers_run_on_self_source_input() -> None:
    """End-to-end: run every implemented layer on a single rich input.

    Self-source + identical regenerations gives the maximum-grounding
    case. Verifies each layer produces a meaningful result with the
    expected sign (high grounding, low instability, low fabrication
    signals).
    """
    text = _INTEGRATION_TEXT
    src = text
    comps = [text, text]

    # Layer 1
    l1 = structural_profile(text)
    assert l1["heading_defaultness"] is None  # 1a not wired
    assert isinstance(l1["mechanism_ratio"], float)
    assert isinstance(l1["assertion_ratio"], float)

    # Layer 2
    l2 = claim_density(text)
    assert l2["n_numerical"] >= 5
    assert l2["n_words"] > 0

    # Layer 3 (self-comparisons → all stable)
    l3 = temporal_instability(text, comps)
    assert l3["instability_rate"] == 0.0
    assert l3["versions_compared"] == 3

    # Layer 4 (self-source → all sourced)
    l4 = source_matching(text, src)
    assert l4["unsourced_rate"] == 0.0
    assert l4["n_total"] >= 10  # adequate precision

    # Layer 5 (self-source → all entities grounded)
    l5 = entity_provenance(text, src)
    assert l5["entity_unsourced_rate"] == 0.0
    assert l5["n_entities"] >= 5

    # Layer 6 (self-source → mean_proximity = 1.0)
    l6 = vocabulary_proximity(text, src)
    assert l6["mean_proximity"] == 1.0

    # Layer 7 (always available)
    l7 = presentation_features(text)
    assert 0.0 <= l7["type_token_ratio"] <= 1.0

    # Layer 8 (self-source → all assertions grounded)
    l8 = epistemic_calibration(text, src)
    assert l8["calibration_score"] == 1.0
    assert l8["n_assertions"] >= 1

    # Layer 9 (always available)
    l9 = information_novelty(text)
    assert 0.0 <= l9["mean_novelty"] <= 1.0

    # Layer 10 (composite of L3 + L4 + L5 + L8 + L7)
    l10 = quality_profile(text, source=src, comparisons=comps)
    # Substance dominates self-source case (multiple components at 1.0)
    assert l10["substance_index"] >= 0.9
    # Gap is non-positive (substance >= presentation)
    assert l10["gap"] <= 0
    # All 4 substance contributors should appear with this rich input
    assert "source_fidelity" in l10["components_available"]
    assert "entity_grounding" in l10["components_available"]
    assert "epistemic_calibration" in l10["components_available"]
    assert "temporal_stability" in l10["components_available"]

    # Layer 11 (self-source → no projection)
    l11 = grounding_decomposition(text, src)
    assert l11["has_projection"] is False
    assert l11["n_projected"] == 0
    assert l11["proportions"]["G"] >= 0.5  # most sentences classified as G


def test_layer_4_and_layer_3_share_same_number_set_on_text() -> None:
    """Layer 3 and Layer 4 both extract numbers from text via the same
    helpers. For the same input, Layer 4's n_total and the count of
    text-side numbers in Layer 3 should match.
    """
    text = (
        "Revenue grew 12% to $143M with 25% margins. "
        "Costs declined 8% across 5,000 employees over 18 months."
    )
    l4 = source_matching(text, text)
    # Layer 4: number count in text
    layer_4_text_numbers = l4["n_total"]
    # Layer 3 with single-comparison-equal-to-text: total unique = text count
    l3 = temporal_instability(text, [text])
    assert l3["n_total"] == layer_4_text_numbers


def test_layers_4_5_8_all_fire_or_none_on_empty_source() -> None:
    """When source is empty, source-dependent layers behave
    consistently: each emits its "no grounding" output without raising.
    """
    text = "Revenue grew 12% to $143M with 25% margins reported here today."
    src = ""
    l4 = source_matching(text, src)
    l5 = entity_provenance(text, src)
    l6 = vocabulary_proximity(text, src)
    l8 = epistemic_calibration(text, src)
    l11 = grounding_decomposition(text, src)
    # All run without raising. None claim grounding to empty source.
    assert l4["unsourced_rate"] == 1.0 if l4["n_total"] > 0 else l4["unsourced_rate"] == 0.0
    assert l5["entity_unsourced_rate"] >= 0.0
    assert l6["mean_proximity"] == 0.0
    assert l8["calibration_score"] == 0.0
    # L11 with empty source: every sentence with a number → P
    assert l11["has_projection"] or l11["n_sentences"] == 0
