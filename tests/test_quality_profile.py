"""Tests for Layer 10 quality profile (Touchstone Standard Section 5.10).

Layer 10 is a composite: it aggregates fidelity-leaning layers into a
substance index and surface-leaning layers into a presentation index.
Gap = presentation - substance is the overclaiming signal.

In the current build, substance contribution comes only from Layer 4
(``source_fidelity``); Layers 5, 8, 3 are skeleton. Presentation
contributions come from Layer 7 (assertiveness, formatting_intensity,
vocabulary_diversity).

Indices are honest only when both substance AND presentation have at
least one component. Otherwise indices are 0.0 and callers must
inspect ``components_available``.
"""

from __future__ import annotations

import pytest

from clarethium_touchstone.measure import quality_profile

# Fixtures: text long enough that source_matching reaches "adequate"
# precision (≥ 10 numbers).
ADEQUATE_PRECISION_TEXT = (
    "Revenue grew 12% to $143M with 25% margins reported. "
    "Costs declined 8% across 5,000 employees over 18 months. "
    "Headcount reached 2,500 with $45,000 average compensation paid. "
    "Customer acquisition cost dropped to $1,200 from previous baseline. "
    "Retention improved 7.5% to 94.2% across all major segments globally."
)


# ---------------------------------------------------------------------------
# Output shape contract
# ---------------------------------------------------------------------------


def test_output_shape_is_well_formed() -> None:
    """All required fields present with correct types."""
    result = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    assert isinstance(result["substance_index"], float)
    assert isinstance(result["presentation_index"], float)
    assert isinstance(result["gap"], float)
    assert isinstance(result["components"], dict)
    assert isinstance(result["components_available"], list)


def test_output_keys_are_exact_set() -> None:
    """No extra fields leak."""
    result = quality_profile("Some text without enough numbers here today.")
    assert set(result.keys()) == {
        "substance_index",
        "presentation_index",
        "gap",
        "components",
        "components_available",
    }


def test_components_dict_matches_available_list() -> None:
    """``components`` keys and ``components_available`` entries are the same set."""
    result = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    assert set(result["components"].keys()) == set(result["components_available"])


# ---------------------------------------------------------------------------
# Empty / insufficient-data fallback
# ---------------------------------------------------------------------------


def test_empty_text_returns_zero_indices() -> None:
    """Empty input: all indices and gap are 0.0."""
    result = quality_profile("", source="some source content")
    assert result["substance_index"] == 0.0
    assert result["presentation_index"] == 0.0
    assert result["gap"] == 0.0


def test_no_source_falls_back_to_zero_indices() -> None:
    """Without source, no substance contributors → indices fall to 0.0.

    Presentation components are still computed (and listed in
    ``components_available``) so callers can recover them, but the
    composite indices intentionally zero out per the documented
    contract.
    """
    result = quality_profile(ADEQUATE_PRECISION_TEXT)
    assert result["substance_index"] == 0.0
    assert result["presentation_index"] == 0.0
    assert result["gap"] == 0.0
    # Presentation components still listed
    assert "assertiveness" in result["components_available"]
    assert "formatting_intensity" in result["components_available"]
    assert "vocabulary_diversity" in result["components_available"]
    assert "source_fidelity" not in result["components_available"]


def test_low_precision_excludes_substance() -> None:
    """When source_matching precision is 'low' (<10 numbers), substance
    contribution is excluded and indices fall to 0.0.
    """
    text = "The product launched yesterday with positive reception widely."
    result = quality_profile(text, source="Product mentioned briefly.")
    # Layer 4 will report n_total=0, precision="low" → substance excluded
    assert "source_fidelity" not in result["components_available"]
    assert result["substance_index"] == 0.0


# ---------------------------------------------------------------------------
# Index semantics
# ---------------------------------------------------------------------------


def test_self_source_yields_high_substance() -> None:
    """When document equals source and precision is adequate, source_fidelity
    is 1.0 (no fabrication).
    """
    result = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    assert result["components"]["source_fidelity"] == 1.0
    assert result["substance_index"] == 1.0


def test_fabricated_text_yields_zero_substance() -> None:
    """When all numbers in output are absent from source, substance = 0.0."""
    text_with_unsourced = (
        "Revenue exploded 999% to $9.99B with 247% margins reported. "
        "Costs declined 88% across 50,000 employees over 18 months. "
        "Headcount reached 25,000 with $145,000 average compensation. "
        "Customer acquisition cost dropped to $11,200 from previous baseline. "
        "Retention improved 67.5% to 994.2% across all segments globally."
    )
    src = "Revenue and costs were mentioned briefly in the source today."
    result = quality_profile(text_with_unsourced, source=src)
    assert result["substance_index"] == 0.0


def test_fabricated_yields_positive_gap_overclaiming() -> None:
    """Fabricated text + presentation polish → gap > 0 (overclaiming signal)."""
    text = (
        "Revenue exploded 999% to $9.99B with 247% margins reported. "
        "Costs declined 88% across 50,000 employees over 18 months. "
        "Headcount reached 25,000 with $145,000 average compensation. "
        "Customer acquisition cost dropped to $11,200 from previous baseline. "
        "Retention improved 67.5% to 994.2% across all segments globally."
    )
    src = "Revenue and costs were mentioned briefly in the source today."
    result = quality_profile(text, source=src)
    # substance=0, presentation>0, gap>0
    assert result["gap"] > 0


def test_faithful_yields_negative_or_zero_gap() -> None:
    """Faithful (self-source) text → presentation typically less than
    substance (which is 1.0) → gap is negative or zero.
    """
    result = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    # substance=1.0, presentation<=1.0 → gap = pres - sub <= 0
    assert result["gap"] <= 0


def test_discrimination_faithful_vs_fabricated_gap() -> None:
    """Adversarial discrimination: same presentation, different substance →
    fabricated gap strictly exceeds faithful gap.
    """
    fabricated = (
        "Revenue exploded 999% to $9.99B with 247% margins reported. "
        "Costs declined 88% across 50,000 employees over 18 months. "
        "Headcount reached 25,000 with $145,000 average compensation. "
        "Customer acquisition cost dropped to $11,200 from previous baseline. "
        "Retention improved 67.5% to 994.2% across all segments globally."
    )
    src = "Revenue and costs were mentioned briefly in the source today."

    faithful_r = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    fab_r = quality_profile(fabricated, source=src)

    assert fab_r["gap"] > faithful_r["gap"]
    assert fab_r["substance_index"] < faithful_r["substance_index"]


# ---------------------------------------------------------------------------
# Gap arithmetic
# ---------------------------------------------------------------------------


def test_gap_equals_presentation_minus_substance() -> None:
    """Gap = presentation_index - substance_index (within rounding)."""
    result = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    expected = round(result["presentation_index"] - result["substance_index"], 3)
    assert result["gap"] == expected


# ---------------------------------------------------------------------------
# Component-level invariants
# ---------------------------------------------------------------------------


def test_presentation_always_includes_three_components() -> None:
    """Layer 7 always contributes three components regardless of source."""
    for src in (None, "any source"):
        result = quality_profile("Any text content here for analysis purposes.", source=src)
        for key in ("assertiveness", "formatting_intensity", "vocabulary_diversity"):
            assert key in result["components_available"]


def test_source_fidelity_appears_only_with_adequate_precision_and_source() -> None:
    """source_fidelity in components only when source given AND precision >= adequate."""
    # No source: absent
    r1 = quality_profile(ADEQUATE_PRECISION_TEXT)
    assert "source_fidelity" not in r1["components_available"]
    # Source + low precision: absent
    r2 = quality_profile("No numbers here today friend at all.", source="src")
    assert "source_fidelity" not in r2["components_available"]
    # Source + adequate precision: present
    r3 = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    assert "source_fidelity" in r3["components_available"]


def test_components_rounded_to_three_decimals() -> None:
    """All component scores are rounded to 3 decimals (storage parity)."""
    result = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    for value in result["components"].values():
        assert value == round(value, 3)


# ---------------------------------------------------------------------------
# Reserved parameters
# ---------------------------------------------------------------------------


def test_comparisons_argument_accepted_but_unused() -> None:
    """``comparisons`` is reserved for Layer 3; accepting it must not change output."""
    r1 = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    r2 = quality_profile(
        ADEQUATE_PRECISION_TEXT,
        source=ADEQUATE_PRECISION_TEXT,
        comparisons=["alt version 1", "alt version 2"],
    )
    assert r1 == r2


# ---------------------------------------------------------------------------
# Index range invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,source",
    [
        (ADEQUATE_PRECISION_TEXT, ADEQUATE_PRECISION_TEXT),
        (ADEQUATE_PRECISION_TEXT, "Some unrelated source content here."),
        ("Plain prose without any numbers in the body content.", "src"),
    ],
)
def test_indices_in_unit_range(text: str, source: str) -> None:
    """substance_index, presentation_index always in [0.0, 1.0]."""
    result = quality_profile(text, source=source)
    assert 0.0 <= result["substance_index"] <= 1.0
    assert 0.0 <= result["presentation_index"] <= 1.0
