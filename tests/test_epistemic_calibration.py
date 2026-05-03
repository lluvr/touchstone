"""Tests for Layer 8 epistemic calibration (Touchstone Standard Section 5.8).

Layer 8 is EXPERIMENTAL in Standard 1.0. It's a cross-layer per-sentence
metric: for each sentence with assertion markers (broader set than Layer
1c), check whether grounding evidence exists via three independent paths:

1. Sourced number (Layer 4 logic)
2. Sourced Title Case multi-word entity
3. >50% vocabulary overlap with source (similar to Layer 6)

A sentence is GROUNDED if any ground fires; otherwise OVERCLAIMING.
"""

from __future__ import annotations

import pytest

from clarethium_touchstone.measure import (
    _calibration_precision,
    epistemic_calibration,
)

# ---------------------------------------------------------------------------
# Output shape contract
# ---------------------------------------------------------------------------


def test_output_shape_is_well_formed() -> None:
    """All required fields present with correct types."""
    text = "Revenue must always grow by 12% across the segment globally."
    result = epistemic_calibration(text, "Revenue grew 12%.")
    assert isinstance(result["calibration_score"], float)
    assert isinstance(result["overclaiming_rate"], float)
    assert isinstance(result["n_assertions"], int)
    assert isinstance(result["n_grounded"], int)
    assert result["precision"] in ("high", "adequate", "low")


def test_output_keys_are_exact_set() -> None:
    """No extra fields leak from the vault implementation."""
    result = epistemic_calibration("Some text.", "Some source.")
    assert set(result.keys()) == {
        "calibration_score",
        "overclaiming_rate",
        "n_assertions",
        "n_grounded",
        "precision",
    }


# ---------------------------------------------------------------------------
# Empty / degenerate inputs
# ---------------------------------------------------------------------------


def test_empty_text_returns_zero_low_precision() -> None:
    """Empty input: zero counts, zero rates, low precision.

    IMPORTANT: ``calibration_score = 0.0`` here means NO DATA, not
    "0% grounded". Callers must check ``n_assertions > 0`` before
    interpreting calibration_score as a meaningful ratio. The vault
    sentinel for this case was ``None``; the TypedDict requires a
    float so 0.0 is the normalised value.
    """
    result = epistemic_calibration("", "any source")
    assert result["calibration_score"] == 0.0
    assert result["overclaiming_rate"] == 0.0
    assert result["n_assertions"] == 0
    assert result["n_grounded"] == 0
    assert result["precision"] == "low"


def test_zero_assertions_distinguishable_from_zero_grounded() -> None:
    """Two different "0.0 calibration" scenarios must be distinguishable
    via ``n_assertions``: (1) no assertions found at all (no data), and
    (2) assertions found but none grounded (true overclaiming).
    """
    # Case 1: no data — no assertion markers in text
    no_data = epistemic_calibration(
        "The product launched yesterday and customers were satisfied.", "Some source."
    )
    assert no_data["n_assertions"] == 0
    assert no_data["calibration_score"] == 0.0  # but means "no data"

    # Case 2: real overclaiming — assertions present, none grounded
    overclaim = epistemic_calibration(
        "The system clearly always must definitively work without exception.",
        "Brief unrelated source content.",
    )
    assert overclaim["n_assertions"] >= 1
    assert overclaim["n_grounded"] == 0
    assert overclaim["calibration_score"] == 0.0  # means "real 0% grounded"

    # Both have calibration_score = 0.0 but n_assertions distinguishes them
    assert no_data["n_assertions"] != overclaim["n_assertions"]


def test_no_assertion_markers_returns_zero() -> None:
    """Text without assertion markers: no assertions counted."""
    text = "The product launched yesterday and customers received it well today."
    result = epistemic_calibration(text, "Brief source content here.")
    assert result["n_assertions"] == 0
    assert result["calibration_score"] == 0.0


def test_overclaiming_rate_complements_calibration() -> None:
    """overclaiming_rate + calibration_score == 1.0 (within rounding)
    when there is at least one assertion.
    """
    text = (
        "The system must always work definitively without exception. "
        "Revenue clearly grows 25% across the years globally always today."
    )
    src = "Revenue grew 25%."
    result = epistemic_calibration(text, src)
    if result["n_assertions"] > 0:
        total = result["calibration_score"] + result["overclaiming_rate"]
        assert abs(total - 1.0) < 0.005


# ---------------------------------------------------------------------------
# Ground 1: sourced number
# ---------------------------------------------------------------------------


def test_ground_1_sourced_number_grounds_assertion() -> None:
    """Sentence with assertion + sourced number → grounded."""
    text = "Revenue must always grow by 12% across the segment globally."
    src = "Revenue grew by 12% as expected this period."
    result = epistemic_calibration(text, src)
    assert result["n_assertions"] == 1
    assert result["n_grounded"] == 1
    assert result["calibration_score"] == 1.0


def test_ground_1_unsourced_number_does_not_ground() -> None:
    """Number in sentence NOT in source: ground 1 fails. (Other grounds
    may still fire, but with disjoint vocabulary they won't.)
    """
    text = "Revenue must always grow by 47% across xyzzy segments globally."
    src = "Brief unrelated source content with no overlap whatsoever."
    result = epistemic_calibration(text, src)
    assert result["n_assertions"] == 1
    assert result["n_grounded"] == 0


# ---------------------------------------------------------------------------
# Ground 2: sourced Title Case entity
# ---------------------------------------------------------------------------


def test_ground_2_sourced_title_case_entity_grounds() -> None:
    """Title Case multi-word phrase present in source grounds the sentence."""
    text = "Stanford University must always lead innovation across the field."
    src = "Stanford University leads research initiatives globally today."
    result = epistemic_calibration(text, src)
    assert result["n_grounded"] == 1


def test_ground_2_requires_multi_word_capitalised() -> None:
    """Single Title Case word does NOT trigger ground 2 (pattern requires
    ``[A-Z][a-z]+(?:\\s+[A-Z][a-z]+)+`` — at least two Title Case words).
    """
    # Single Title Case word in source: NOT enough for ground 2
    text = "Performance must always improve through xyzzy methods absolutely."
    src = "Performance is mentioned here."
    result = epistemic_calibration(text, src)
    # 'Performance' is single word; pattern requires 2+ Title Case words
    # 'xyzzy' won't ground via vocab either (low overlap)
    # So this should NOT be grounded
    assert result["n_grounded"] == 0


# ---------------------------------------------------------------------------
# Ground 3: vocabulary overlap > 50%
# ---------------------------------------------------------------------------


def test_ground_3_high_vocab_overlap_grounds() -> None:
    """Sentence with >50% content-word overlap with source is grounded."""
    text = "Performance always must improve significantly across all systems."
    src = "Performance improved significantly across all systems globally."
    result = epistemic_calibration(text, src)
    assert result["n_grounded"] == 1


def test_ground_3_uses_substring_match_vault_faithful() -> None:
    """Vault behaviour: Ground 3 vocab check is ``w in source_lower``
    (Python substring), so a content word ``cat`` is considered
    grounded when source contains ``catalog``. Same generosity as
    Layer 6 vocabulary_proximity. Pinned because it can inflate
    grounding scores on short content words.
    """
    # Sentence has 5 content words. If 3+ are substrings of source words
    # (>0.5 threshold), Ground 3 fires.
    text = "Performance must always improve catalog methods comprehensively today."
    # source has 'catalog' (matches 'catalog'), 'methods' (matches 'methods'),
    # 'comprehensively' (matches), 'today' (matches) — 4 of 5 content words
    # match substrings → vocab_score > 0.5 → grounded
    src = "The catalog covered methods comprehensively across all teams today."
    result = epistemic_calibration(text, src)
    assert result["n_grounded"] == 1
    assert result["calibration_score"] == 1.0


def test_ground_3_threshold_strictly_greater_than_half() -> None:
    """Vault threshold is ``> 0.5`` (strictly greater than half), not ≥.

    A sentence with exactly 50% overlap (2 of 4 content words in source)
    does NOT ground via vocab. Other grounds also fail in this test
    (no numbers; no multi-word Title Case in text), so the assertion is
    flagged as overclaiming.
    """
    # Sentence has 4 content words after stop-word filtering:
    # "Always: improve performance via xyzzy." → ['always', 'improve',
    # 'performance', 'xyzzy'] (via filtered as stop word).
    # Source contains 'performance' and 'improve' but not 'always' or
    # 'xyzzy' → exactly 2/4 = 0.5 (not > 0.5).
    text = "Always: improve performance via xyzzy."
    src = "Performance improve."
    result = epistemic_calibration(text, src)
    # 'always' is the assertion marker
    assert result["n_assertions"] == 1
    # Ground 1: no numbers → fails
    # Ground 2: 'Always:' is single Title Case (no multi-word phrase) → fails
    # Ground 3: 0.5 ratio is NOT > 0.5 → fails
    assert result["n_grounded"] == 0
    assert result["calibration_score"] == 0.0


# ---------------------------------------------------------------------------
# Expanded calibration assertion patterns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "It is clear that this must work always.",
        "There is no doubt about the result here today.",
        "Without question this is correct everywhere here.",
        "This proves that the approach always works correctly.",
        "Indisputably this is the right path forward.",
        "Conclusively this must always work today.",
        "Definitively this is correct in this case.",
        "Inevitably this must work in production always.",
        "The system certainly will work always today.",
        "This demonstrates that the approach always works.",
    ],
)
def test_expanded_calibration_patterns_detected(phrase: str) -> None:
    """The expanded calibration set catches v1.3-only phrases."""
    result = epistemic_calibration(phrase, "")
    assert result["n_assertions"] >= 1


# ---------------------------------------------------------------------------
# Precision thresholds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "low"),
        (1, "low"),
        (4, "low"),
        (5, "adequate"),
        (14, "adequate"),
        (15, "high"),
        (30, "high"),
    ],
)
def test_precision_thresholds(n: int, expected: str) -> None:
    """Precision: <5 → low, <15 → adequate, ≥15 → high (vault's 'good'
    renamed for TypedDict consistency).
    """
    assert _calibration_precision(n) == expected


# ---------------------------------------------------------------------------
# Mixed-grounding adversarial discrimination
# ---------------------------------------------------------------------------


def test_well_grounded_text_high_calibration() -> None:
    """Output where every assertion has matching evidence in source: high
    calibration, low overclaiming.
    """
    text = (
        "Revenue must always grow by 12% across all segments. "
        "Stanford University must lead innovation in this domain. "
        "Margins clearly will increase by 25% across markets globally."
    )
    src = "Revenue grew 12%. Margins increased by 25%. Stanford University led innovation."
    result = epistemic_calibration(text, src)
    assert result["n_grounded"] == result["n_assertions"]
    assert result["calibration_score"] == 1.0


def test_overclaiming_text_low_calibration() -> None:
    """Output with assertions but no source overlap: low calibration."""
    text = (
        "The system clearly always must definitively work without exception. "
        "Inevitably this proves that everything works conclusively today. "
        "Indisputably the result is undeniably certain across all dimensions."
    )
    src = "Brief unrelated source content here today."
    result = epistemic_calibration(text, src)
    assert result["n_assertions"] >= 3
    assert result["n_grounded"] == 0
    assert result["calibration_score"] == 0.0
    assert result["overclaiming_rate"] == 1.0


def test_calibration_discriminates_grounded_from_overclaiming() -> None:
    """Adversarial: same assertion frequency, different source fidelity →
    higher calibration for grounded text.
    """
    grounded_text = (
        "Revenue must always grow by 12%. "
        "Stanford University must lead. "
        "Margins clearly will increase by 25%."
    )
    overclaiming_text = (
        "Revenue must always grow by 47%. "
        "Berkeley Institute must lead. "
        "Margins clearly will increase by 88%."
    )
    src = "Revenue grew 12%. Margins increased 25%. Stanford University led."

    grounded_r = epistemic_calibration(grounded_text, src)
    over_r = epistemic_calibration(overclaiming_text, src)
    assert grounded_r["calibration_score"] > over_r["calibration_score"]


# ---------------------------------------------------------------------------
# Multiple-marker sentence counts as ONE assertion
# ---------------------------------------------------------------------------


def test_multiple_markers_in_sentence_count_as_one() -> None:
    """Each sentence is counted once regardless of how many assertion
    markers it contains.
    """
    # Sentence has 'must', 'always', 'clearly', 'definitively' — 4 markers
    text = "It must always clearly work definitively in production today."
    result = epistemic_calibration(text, "")
    # One sentence → one assertion (not four)
    assert result["n_assertions"] == 1
