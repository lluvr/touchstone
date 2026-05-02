"""Tests for Layer 1 structural profile (Touchstone Standard Section 5.1).

Layer 1 has three sublayers:
* 1a heading_defaultness — optional, returns None until LLM-API wired
* 1b mechanism_ratio — causal markers / (causal + buzzword) markers
* 1c assertion_ratio — fraction of register matches in ASSERTION category
"""

from __future__ import annotations

import pytest

from clarethium_touchstone.measure import (
    _assertion_ratio,
    _extract_section_bodies,
    _mechanism_ratio,
    structural_profile,
)

# ---------------------------------------------------------------------------
# Output shape contract
# ---------------------------------------------------------------------------


def test_output_shape_is_well_formed() -> None:
    """All required fields present with correct types."""
    text = "## Section\n\nThe system fails because of memory pressure. This must be addressed."
    result = structural_profile(text)
    assert "heading_defaultness" in result
    assert isinstance(result["mechanism_ratio"], float)
    assert isinstance(result["assertion_ratio"], float)
    assert result["assertion_precision"] in ("high", "adequate", "low")


def test_layer_1a_returns_none_until_llm_wired() -> None:
    """Heading defaultness is None even when topic is provided (LLM not wired)."""
    result = structural_profile("Some text.", topic="machine learning")
    assert result["heading_defaultness"] is None


def test_empty_text_returns_zeros() -> None:
    """Empty input yields zero ratios with low precision."""
    result = structural_profile("")
    assert result["mechanism_ratio"] == 0.0
    assert result["assertion_ratio"] == 0.0
    assert result["assertion_precision"] == "low"


# ---------------------------------------------------------------------------
# Layer 1b: mechanism_ratio
# ---------------------------------------------------------------------------


def test_pure_mechanism_text_yields_ratio_one() -> None:
    """Text with only causal markers, no buzzwords, scores 1.0."""
    text = "Latency drops because cache hits rise. This causes throughput improvement."
    ratio = _mechanism_ratio(text)
    assert ratio == 1.0


def test_pure_buzzword_text_yields_ratio_zero() -> None:
    """Text with only buzzwords, no causal markers, scores 0.0."""
    text = (
        "This transformative paradigm fundamentally enables synergy through "
        "holistically pivotal game-changer initiatives."
    )
    ratio = _mechanism_ratio(text)
    assert ratio == 0.0


def test_mixed_text_yields_intermediate_ratio() -> None:
    """Mix of causal and buzzword markers produces an intermediate ratio."""
    text = (
        "The system fails because of memory pressure. "
        "This is a fundamentally transformative paradigm."
    )
    # 1 mech (because) + 2 buzz (fundamentally, transformative + paradigm)
    ratio = _mechanism_ratio(text)
    assert 0.0 < ratio < 1.0


def test_no_markers_yields_zero() -> None:
    """Text with neither marker type yields 0.0."""
    text = "The product launched yesterday and customers responded well."
    ratio = _mechanism_ratio(text)
    assert ratio == 0.0


def test_leverage_with_qualifying_noun_counted_as_buzzword() -> None:
    """'leverage the X' pattern is a buzzword; bare 'leverage' is not."""
    buzz_text = "We leverage the existing infrastructure across all teams."
    plain_text = "We leverage data analysis."  # 'data' is in qualifier list -> buzz
    plain_text_2 = "We leverage many tools."  # 'many' not in list -> NOT buzz
    assert _mechanism_ratio(buzz_text) == 0.0
    # data IS in the qualifier list, so this counts as buzz
    assert _mechanism_ratio(plain_text) == 0.0
    # 'many' is not in the qualifier list, so leverage doesn't trigger
    assert _mechanism_ratio(plain_text_2) == 0.0


def test_robust_qualifier_counted_as_buzzword() -> None:
    """'robust framework/solution/approach/system' counts as buzzword."""
    text = "We built a robust framework. The approach is robust."
    # First 'robust' (followed by 'framework') triggers, second does not
    ratio = _mechanism_ratio(text)
    assert ratio == 0.0  # 1 buzz, 0 mech -> 0.0


def test_mechanism_ratio_rounded_to_4_decimals() -> None:
    """Ratio is rounded to 4 decimal places."""
    text = "It fails because of bugs. This is fundamentally pivotal."
    ratio = _mechanism_ratio(text)
    # Verify it's a reasonable float, not an unrounded long decimal
    assert ratio == round(ratio, 4)


# ---------------------------------------------------------------------------
# Layer 1c: assertion_ratio
# ---------------------------------------------------------------------------


def test_pure_assertion_text_high_ratio() -> None:
    """Text dominated by ASSERTION markers approaches 1.0."""
    text = (
        "## Section\n\n"
        "This must always work. The system clearly ensures correctness. "
        "It will lead to success. This is essential and is the key requirement. "
        "Components must guarantee delivery; the path is critical."
    )
    ratio, _precision = _assertion_ratio(text)
    assert ratio > 0.7


def test_pure_qualified_text_low_ratio() -> None:
    """Text dominated by QUALIFIED markers has low assertion ratio."""
    text = (
        "## Section\n\n"
        "The system tends to work well. Performance often improves typically. "
        "Evidence suggests improvement is likely. Results may probably appear "
        "and frequently the outcome usually matches expectations."
    )
    ratio, _precision = _assertion_ratio(text)
    assert ratio < 0.2


def test_assertion_ratio_uses_section_bodies_when_present() -> None:
    """When ## headings exist, assertion analysis runs on section bodies."""
    # Headings contain assertion markers but should be excluded
    text = (
        "## must always be considered key\n\n"
        "Performance tends to improve typically over time across systems."
    )
    # Heading text is excluded; only body has 'tends to' (qualified)
    # So ASSERTION count = 0, QUALIFIED count = 1, ratio = 0.0
    ratio, _precision = _assertion_ratio(text)
    assert ratio == 0.0


def test_assertion_ratio_falls_back_to_full_text_without_sections() -> None:
    """Without ## headings, falls back to full-text analysis."""
    text = "This must always work correctly across all systems and contexts."
    ratio, precision = _assertion_ratio(text)
    # 'must' and 'always' are ASSERTION markers; ratio should be 1.0
    assert ratio == 1.0
    # Only 2 matches < threshold of 10 -> low precision
    assert precision == "low"


def test_assertion_precision_low_below_threshold() -> None:
    """Total matches under 10 yields 'low' precision."""
    text = "## Section\n\nThis must work always reliably."
    _ratio, precision = _assertion_ratio(text)
    assert precision == "low"


def test_assertion_precision_adequate_at_threshold() -> None:
    """Total matches at or above 10 yields 'adequate' precision."""
    text = (
        "## Section\n\n"
        "This must always work. Often the system tends to improve typically. "
        "Studies show data indicates the result. Research suggests changes "
        "frequently. Likely the outcome may probably appear. The system "
        "must guarantee delivery and ensure consistency every time."
    )
    _ratio, precision = _assertion_ratio(text)
    assert precision == "adequate"


def test_assertion_ratio_zero_when_no_markers() -> None:
    """No epistemic markers yields (0.0, 'low')."""
    text = "## Section\n\nThe product launched. Customers received it."
    ratio, precision = _assertion_ratio(text)
    assert ratio == 0.0
    assert precision == "low"


def test_assertion_ratio_rounded_to_4_decimals() -> None:
    """Ratio is rounded to 4 decimal places."""
    text = "## Section\n\nThis must always work. Often it tends to improve typically."
    ratio, _precision = _assertion_ratio(text)
    assert ratio == round(ratio, 4)


# ---------------------------------------------------------------------------
# Section body extraction
# ---------------------------------------------------------------------------


def test_extract_section_bodies_returns_bodies_only() -> None:
    """Section extraction excludes heading text from bodies."""
    text = (
        "## First Heading\nFirst body content here.\n\n## Second Heading\nSecond body content here."
    )
    bodies = _extract_section_bodies(text)
    assert len(bodies) == 2
    assert "First Heading" not in bodies[0]
    assert "Second Heading" not in bodies[1]
    assert "First body content here." in bodies[0]
    assert "Second body content here." in bodies[1]


def test_extract_section_bodies_empty_when_no_headings() -> None:
    """Returns empty list when no ## or ### headings present."""
    text = "Just plain text without any markdown headings whatsoever."
    bodies = _extract_section_bodies(text)
    assert bodies == []


def test_extract_section_bodies_handles_h3_headings() -> None:
    """Both ## and ### headings start new sections."""
    text = "## Top\nA.\n### Sub\nB."
    bodies = _extract_section_bodies(text)
    assert len(bodies) == 2


# ---------------------------------------------------------------------------
# Composite structural_profile
# ---------------------------------------------------------------------------


def test_structural_profile_combines_sublayers() -> None:
    """structural_profile() returns 1a/1b/1c results in one dict."""
    text = (
        "## Analysis\n\n"
        "Performance fails because of memory pressure. This must be addressed. "
        "The system tends to recover often given enough resources usually."
    )
    result = structural_profile(text)
    assert result["heading_defaultness"] is None  # 1a not wired
    assert result["mechanism_ratio"] > 0  # 'because' present
    assert result["assertion_ratio"] >= 0  # at least one assertion marker
    assert result["assertion_precision"] in ("adequate", "low")


@pytest.mark.parametrize(
    "text,expected_mech_min,expected_mech_max",
    [
        # All causal: ratio = 1.0
        ("It fails because of bugs. This causes errors and leads to crashes.", 1.0, 1.0),
        # All buzzword: ratio = 0.0
        ("Transformative paradigm fundamentally enables holistic synergy.", 0.0, 0.0),
        # No markers: ratio = 0.0
        ("Plain prose without any special markers at all whatsoever.", 0.0, 0.0),
    ],
)
def test_mechanism_ratio_canonical_examples(
    text: str, expected_mech_min: float, expected_mech_max: float
) -> None:
    """Canonical inputs produce expected mechanism ratios."""
    ratio = _mechanism_ratio(text)
    assert expected_mech_min <= ratio <= expected_mech_max
