"""Tests for Layer 10 quality profile (Touchstone Standard Section 5.10).

Layer 10 is a composite: it aggregates fidelity-leaning layers into a
substance index and surface-leaning layers into a presentation index.
Gap = presentation - substance is the overclaiming signal.

Substance contributors (current build):
- ``source_fidelity`` from Layer 4
- ``entity_grounding`` from Layer 5
- ``epistemic_calibration`` from Layer 8
- ``temporal_stability`` from Layer 3 (when comparisons supplied)

Presentation contributors (always available from Layer 7):
- ``assertiveness``, ``formatting_intensity``, ``vocabulary_diversity``

Each index is computed independently when its side has contributors.
Gap is meaningful only when BOTH sides contributed; otherwise gap is
0.0 (callers should inspect ``components_available``).
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


def test_empty_text_substance_zero_gap_zero() -> None:
    """Empty input: substance and gap are 0.0; presentation reflects
    Layer 7's defaults on empty text (assertiveness 0.5 + zeros).
    """
    result = quality_profile("", source="some source content")
    assert result["substance_index"] == 0.0
    assert result["gap"] == 0.0
    # Presentation_index is honestly computed from Layer 7's empty-text defaults:
    # mean(assertiveness=0.5, formatting=0.0, ttr=0.0) ≈ 0.167
    assert result["presentation_index"] > 0


def test_no_source_keeps_presentation_zeros_substance_and_gap() -> None:
    """Without source, no substance contributors → substance_index and gap
    fall to 0.0, but presentation_index remains the honest mean of
    Layer 7's three contributors.
    """
    result = quality_profile(ADEQUATE_PRECISION_TEXT)
    assert result["substance_index"] == 0.0
    assert result["gap"] == 0.0
    # Presentation_index is real (mean of Layer 7's three components)
    pres_components = ["assertiveness", "formatting_intensity", "vocabulary_diversity"]
    expected = round(
        sum(result["components"][k] for k in pres_components) / len(pres_components), 3
    )
    # Allow for floating-point round-trip vs the index's own rounding
    assert abs(result["presentation_index"] - expected) <= 0.001
    assert result["presentation_index"] > 0
    # Components_available reflects what actually contributed
    assert all(k in result["components_available"] for k in pres_components)
    assert "source_fidelity" not in result["components_available"]


def test_low_precision_excludes_substance_keeps_presentation() -> None:
    """When source_matching precision is 'low' (<10 numbers), substance
    contribution is excluded; substance_index = 0.0; presentation_index
    remains real.
    """
    text = "The product launched yesterday with positive reception widely."
    result = quality_profile(text, source="Product mentioned briefly.")
    # Layer 4 will report n_total=0, precision="low" → substance excluded
    assert "source_fidelity" not in result["components_available"]
    assert result["substance_index"] == 0.0
    assert result["gap"] == 0.0
    # Presentation_index is real
    assert result["presentation_index"] > 0


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


# Text with ≥5 entities AND ≥10 numbers. Note: vault entity patterns are
# CASE-SENSITIVE - sentence-start "According to" does not trigger; only
# mid-sentence lowercase "according to" / "by" / "per" / "cited by" do.
ENTITY_RICH_TEXT = (
    "Revenue grew 12% to $143M with 25% margins for the year. "
    "Costs declined 8% across 5,000 employees over 18 months. "
    "Headcount reached 2,500 with $45,000 average compensation paid. "
    "Findings according to John Smith of OpenAI confirm 7.5% gains. "
    "The Stanford University team and IBM Research contributed. "
    "Work cited by Carol Brown showed 94% accuracy across studies."
)


def test_entity_grounding_appears_when_at_least_five_entities() -> None:
    """entity_grounding (Layer 5) contributes when source is given AND
    at least 5 entities are extracted from text.
    """
    result = quality_profile(ENTITY_RICH_TEXT, source=ENTITY_RICH_TEXT)
    assert "entity_grounding" in result["components_available"]
    # Self-source: all entities grounded → entity_grounding == 1.0
    assert result["components"]["entity_grounding"] == 1.0


def test_entity_grounding_excluded_when_fewer_than_five_entities() -> None:
    """When fewer than 5 entities extract, entity_grounding is excluded
    (vault precision threshold).
    """
    # ADEQUATE_PRECISION_TEXT has plenty of numbers but no named entities
    result = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    assert "entity_grounding" not in result["components_available"]


def test_epistemic_calibration_appears_when_at_least_five_assertions() -> None:
    """epistemic_calibration (Layer 8) contributes to substance when at
    least 5 assertion-bearing sentences are extracted (precision >= adequate).
    """
    # Build text with 5+ sentences, each with at least one assertion marker
    text = (
        "Revenue must always grow by 12% across all segments globally. "
        "Costs clearly will inevitably decline by 8% across all teams today. "
        "Headcount definitively must reach 2,500 with $45,000 average pay. "
        "Customer retention is critical and must improve by 7.5% always. "
        "Margins indisputably must increase by 25% across all major markets."
    )
    result = quality_profile(text, source=text)
    assert "epistemic_calibration" in result["components_available"]
    # Self-source: every assertion grounds via Ground 1 or Ground 3
    assert result["components"]["epistemic_calibration"] == 1.0


def test_epistemic_calibration_excluded_when_fewer_than_five_assertions() -> None:
    """When precision is 'low' (<5 assertions), epistemic_calibration is
    excluded from substance.
    """
    text = "Revenue must grow by 12%. Performance is acceptable today."
    result = quality_profile(text, source=text)
    # Only 1 assertion → precision="low" → excluded
    assert "epistemic_calibration" not in result["components_available"]


def test_layer_10_all_three_substance_components_contribute() -> None:
    """End-to-end: text with ≥10 numbers, ≥5 entities, AND ≥5 assertion-
    bearing sentences contributes ALL THREE substance components
    (source_fidelity, entity_grounding, epistemic_calibration).

    Self-source: each component scores 1.0 → substance_index = 1.0.
    """
    text = (
        "Revenue must always grow by 12% to $143M with 25% margins for the year. "
        "Costs clearly will inevitably decline by 8% across 5,000 employees today. "
        "Headcount definitively must reach 2,500 with $45,000 average pay reported. "
        "According to John Smith of OpenAI, 7.5% gains must continue indefinitely. "
        "The Stanford University team and IBM Research clearly will lead innovation. "
        "Work cited by Carol Brown showed 94% accuracy must hold across studies. "
        "Customer satisfaction reached 87.4% across multiple departments globally always."
    )
    result = quality_profile(text, source=text)
    # All three substance contributors present
    assert "source_fidelity" in result["components_available"]
    assert "entity_grounding" in result["components_available"]
    assert "epistemic_calibration" in result["components_available"]
    # Self-source: each substance component = 1.0
    assert result["components"]["source_fidelity"] == 1.0
    assert result["components"]["entity_grounding"] == 1.0
    assert result["components"]["epistemic_calibration"] == 1.0
    # Substance index is the mean of all 3 → 1.0
    assert result["substance_index"] == 1.0


def test_temporal_stability_appears_with_comparisons_and_enough_numbers() -> None:
    """temporal_stability (Layer 3) contributes when comparisons are
    supplied AND at least 10 unique numbers appear across versions.
    """
    # ADEQUATE_PRECISION_TEXT has ≥10 numbers and self-comparisons → all stable
    result = quality_profile(
        ADEQUATE_PRECISION_TEXT,
        source=ADEQUATE_PRECISION_TEXT,
        comparisons=[ADEQUATE_PRECISION_TEXT],
    )
    assert "temporal_stability" in result["components_available"]
    # Identical regenerations: every number stable → temporal_stability = 1.0
    assert result["components"]["temporal_stability"] == 1.0


def test_temporal_stability_excluded_when_no_comparisons() -> None:
    """Without comparisons, temporal_stability is not contributed."""
    result = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    assert "temporal_stability" not in result["components_available"]


def test_temporal_stability_excluded_when_too_few_numbers() -> None:
    """Even with comparisons, if fewer than 10 unique numbers appear,
    temporal_stability is excluded (vault precision threshold).
    """
    text = "Revenue grew 12%."
    result = quality_profile(text, source=text, comparisons=[text])
    # Only 1 unique number → temporal_stability excluded
    assert "temporal_stability" not in result["components_available"]


def test_temporal_stability_lowers_substance_with_unstable_regen() -> None:
    """When regenerations diverge, temporal_stability drops below 1.0,
    pulling substance_index down even when source_fidelity stays at 1.0.
    """
    base = ADEQUATE_PRECISION_TEXT
    # Comparison with all numbers changed
    diverged = (
        "Revenue grew 47% to $999M with 88% margins reported. "
        "Costs declined 33% across 9,999 employees over 47 months. "
        "Headcount reached 7,500 with $99,000 average compensation paid. "
        "Customer acquisition cost dropped to $7,700 from previous baseline. "
        "Retention improved 33.3% to 99.9% across all major segments globally."
    )
    full_self = quality_profile(base, source=base, comparisons=[base])
    diverged_r = quality_profile(base, source=base, comparisons=[diverged])
    assert full_self["substance_index"] == 1.0
    assert diverged_r["substance_index"] < 1.0
    # source_fidelity unchanged
    assert diverged_r["components"]["source_fidelity"] == 1.0
    # temporal_stability dropped
    assert diverged_r["components"]["temporal_stability"] < 0.5


def test_layer_10_partial_substance_lowers_index_proportionally() -> None:
    """When some substance components score below 1.0 but others stay at
    1.0, substance_index is the arithmetic mean (rounded).
    """
    text = (
        "Revenue must always grow by 12% to $143M with 25% margins for the year. "
        "Costs clearly will inevitably decline by 8% across 5,000 employees today. "
        "Headcount definitively must reach 2,500 with $45,000 average pay reported. "
        "According to John Smith of OpenAI, 7.5% gains must continue indefinitely. "
        "The Stanford University team and IBM Research clearly will lead innovation. "
        "Work cited by Carol Brown showed 94% accuracy must hold across studies. "
        "Customer satisfaction reached 87.4% across multiple departments globally always."
    )
    # Source has the numbers but DIFFERENT entities (test scenario)
    src = (
        "Numbers reported: 12%, $143M, 25%, 8%, 5,000, 2,500, $45,000, 7.5%, 94%, 87.4%. "
        "Plus context with assertion vocab: must always definitively grow today. "
        "Performance clearly will inevitably continue across multiple business units. "
        "The result must hold today. Indisputably the data clearly shows this. "
        "Definitively this proves the case across all major segments globally always."
    )
    result = quality_profile(text, source=src)
    # All 3 substance contributors should run (≥10 nums, ≥5 entities,
    # ≥5 assertions)
    assert "source_fidelity" in result["components_available"]
    assert "entity_grounding" in result["components_available"]
    assert "epistemic_calibration" in result["components_available"]
    # Substance index is the arithmetic mean of the 3 components
    sub_components = ("source_fidelity", "entity_grounding", "epistemic_calibration")
    expected = round(sum(result["components"][k] for k in sub_components) / len(sub_components), 3)
    assert abs(result["substance_index"] - expected) <= 0.001


def test_entity_grounding_lowers_substance_with_unsourced_entities() -> None:
    """Source missing entities: entity_grounding drops below 1.0,
    pulling substance_index down even when source_fidelity stays high.
    """
    # Source has all the NUMBERS but none of the NAMED ENTITIES
    src = (
        "Numbers: 12%, $143M, 25%, 8%, 5,000, 18, 2,500, $45,000, 7.5%, 94%. "
        "Entities mentioned: Acme Foundation reports across all sites today."
    )
    full_self = quality_profile(ENTITY_RICH_TEXT, source=ENTITY_RICH_TEXT)
    partial = quality_profile(ENTITY_RICH_TEXT, source=src)
    # Self-source has both substance components at 1.0
    assert full_self["substance_index"] == 1.0
    # Partial substance is lower because entity_grounding drops
    assert partial["substance_index"] < 1.0
    # source_fidelity still 1.0 because numbers match
    assert partial["components"]["source_fidelity"] == 1.0
    # entity_grounding should be lower (entities unsourced)
    assert partial["components"]["entity_grounding"] < 1.0


def test_components_rounded_to_three_decimals() -> None:
    """All component scores are rounded to 3 decimals (storage parity)."""
    result = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    for value in result["components"].values():
        assert value == round(value, 3)


# ---------------------------------------------------------------------------
# Reserved parameters
# ---------------------------------------------------------------------------


def test_comparisons_argument_changes_substance_when_layer_3_qualifies() -> None:
    """``comparisons`` now wires Layer 3 (temporal stability) into substance.
    With ≥10 unique numbers across versions, supplying comparisons adds
    a new component (``temporal_stability``) and changes substance_index.
    """
    r_no_comp = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    r_with_comp = quality_profile(
        ADEQUATE_PRECISION_TEXT,
        source=ADEQUATE_PRECISION_TEXT,
        comparisons=[ADEQUATE_PRECISION_TEXT],
    )
    # New component appears
    assert "temporal_stability" not in r_no_comp["components_available"]
    assert "temporal_stability" in r_with_comp["components_available"]


def test_short_comparisons_do_not_qualify_for_layer_3() -> None:
    """When comparisons are passed but the unique-number total is <10,
    Layer 3 does not contribute; output is identical to no-comparisons.
    """
    short_text = "Revenue grew 12%."
    r_no_comp = quality_profile(short_text, source=short_text)
    r_with_short_comp = quality_profile(short_text, source=short_text, comparisons=["alt", "alt2"])
    # Neither contributes temporal_stability (too few unique numbers)
    assert "temporal_stability" not in r_no_comp["components_available"]
    assert "temporal_stability" not in r_with_short_comp["components_available"]


def test_temporal_only_substance_when_no_source() -> None:
    """Without ``source`` but WITH ``comparisons``, Layer 3 is the sole
    substance contributor (Layers 4/5/8 require source).

    Self-comparison → temporal_stability = 1.0 → substance_index = 1.0
    even though source-based components are absent.
    """
    result = quality_profile(ADEQUATE_PRECISION_TEXT, comparisons=[ADEQUATE_PRECISION_TEXT])
    assert "temporal_stability" in result["components_available"]
    assert "source_fidelity" not in result["components_available"]
    assert "entity_grounding" not in result["components_available"]
    assert "epistemic_calibration" not in result["components_available"]
    assert result["components"]["temporal_stability"] == 1.0
    assert result["substance_index"] == 1.0


def test_layer_3_threshold_independent_of_layer_4_threshold() -> None:
    """Layer 3 (cross-version unique-number total ≥ 10) and Layer 4
    (text precision ≥ adequate, ≥ 10 numbers in text alone) have
    independent thresholds. A short text combined with a number-rich
    comparison can qualify for Layer 3 substance contribution while
    failing the Layer 4 precision threshold.
    """
    text_short = "Revenue grew 12%, costs declined."  # 1 number in text
    comp_long = (
        "Revenue grew 12% to $143M with 25% margins. "
        "Costs declined 8% across 5,000 employees over 18 months. "
        "Headcount reached 2,500 with $45,000 average pay. "
        "Customer cost dropped to $1,200. Retention improved 7.5% to 94.2%."
    )
    result = quality_profile(text_short, source=text_short, comparisons=[comp_long])
    # Union has ≥10 unique numbers → Layer 3 contributes
    assert "temporal_stability" in result["components_available"]
    # Text alone has 1 number → precision="low" → Layer 4 excluded
    assert "source_fidelity" not in result["components_available"]


# ---------------------------------------------------------------------------
# Index range invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,source",
    [
        (ADEQUATE_PRECISION_TEXT, ADEQUATE_PRECISION_TEXT),
        (ADEQUATE_PRECISION_TEXT, "Some unrelated source content here."),
        ("Plain prose without any numbers in the body content.", "src"),
        (ENTITY_RICH_TEXT, ENTITY_RICH_TEXT),
        (ENTITY_RICH_TEXT, "Disjoint source content with no overlap."),
    ],
)
def test_indices_in_unit_range(text: str, source: str) -> None:
    """substance_index, presentation_index always in [0.0, 1.0]."""
    result = quality_profile(text, source=source)
    assert 0.0 <= result["substance_index"] <= 1.0
    assert 0.0 <= result["presentation_index"] <= 1.0


@pytest.mark.parametrize(
    "text,source",
    [
        (ADEQUATE_PRECISION_TEXT, ADEQUATE_PRECISION_TEXT),
        (ADEQUATE_PRECISION_TEXT, "Some unrelated source content here."),
        ("Plain prose without any numbers in the body content.", "src"),
        (ENTITY_RICH_TEXT, ENTITY_RICH_TEXT),
        (ENTITY_RICH_TEXT, "Disjoint source content with no overlap."),
        ("", "any source"),
        (ADEQUATE_PRECISION_TEXT, ""),  # empty source
    ],
)
def test_gap_in_signed_unit_range(text: str, source: str) -> None:
    """gap is always in [-1.0, 1.0]: substance and presentation each
    in [0,1], so their difference is bounded by [-1, 1]. When either
    side has no contributors, gap is 0.0 (well within the range).
    """
    result = quality_profile(text, source=source)
    assert -1.0 <= result["gap"] <= 1.0


def test_gap_can_be_strongly_negative_when_substance_dominates() -> None:
    """Self-source with adequate precision: substance maxes out at 1.0;
    presentation is typically lower → gap strongly negative.
    """
    result = quality_profile(ADEQUATE_PRECISION_TEXT, source=ADEQUATE_PRECISION_TEXT)
    # Self-source numbers → source_fidelity=1.0; only substance contributor
    # → substance_index=1.0; presentation typically <= 0.6
    assert result["gap"] < -0.3


def test_gap_strongly_positive_when_substance_low_and_polished() -> None:
    """Polished output with NO sourced numbers and ≥10 numbers (so the
    precision threshold for source_fidelity is met): source_fidelity=0,
    substance_index=0, presentation can be substantial → gap > 0.
    """
    fab = (
        "## **CRITICAL** Findings\n\n"
        "Revenue **definitively** grew 999% to $9.99B with 88% margin gains. "
        "Always must always scale exponentially with 247x amplification factors. "
        "Costs declined 73% across 25,000 employees over 36 months globally. "
        "Headcount reached 50,000 with $145,000 average compensation paid. "
        "Customer acquisition dropped to $11,200 from previous baseline pricing. "
        "Retention improved 67.5% to 99.9% across all major segments today."
    )
    # Source has zero overlap with text's numbers (use only words)
    src = "Brief content unrelated to the document with completely different topics."
    result = quality_profile(fab, source=src)
    # source_fidelity = 1.0 - 1.0 = 0.0 (all numbers unsourced)
    # substance_index = 0.0 (only contributor is 0.0)
    # presentation_index > 0 (formatting + assertiveness + diversity)
    assert "source_fidelity" in result["components_available"]
    assert result["components"]["source_fidelity"] == 0.0
    assert result["substance_index"] == 0.0
    assert result["gap"] > 0.3
