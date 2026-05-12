"""Tests for Layer 1 structural profile (Touchstone Standard Section 5.1).

Layer 1 has three sublayers:
* 1a heading_defaultness - optional, returns None until LLM-API wired
* 1b mechanism_ratio - causal markers / (causal + buzzword) markers
* 1c assertion_ratio - fraction of register matches in ASSERTION category
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


def test_layer_1a_returns_none_when_only_topic_provided() -> None:
    """Heading defaultness is None when topic is supplied but no
    baseline_generator (the LLM injection point) is.
    """
    result = structural_profile("Some text.", topic="machine learning")
    assert result["heading_defaultness"] is None


def test_layer_1a_returns_none_when_only_generator_provided() -> None:
    """Heading defaultness is None when baseline_generator is supplied
    but no topic is.
    """
    result = structural_profile(
        "## Section\nBody content here.",
        baseline_generator=lambda _p: "## Default\nBody.",
    )
    assert result["heading_defaultness"] is None


def test_layer_1a_returns_none_when_doc_has_no_headings() -> None:
    """When the document has no level-2/3 headings, 1a has nothing to
    score and returns None.
    """
    result = structural_profile(
        "Body text without any markdown headings whatsoever today.",
        topic="topic",
        baseline_generator=lambda _p: "## Some Heading\nText.",
    )
    assert result["heading_defaultness"] is None


def test_layer_1a_returns_none_when_all_baselines_fail() -> None:
    """When every baseline_generator call returns None, 1a returns None."""
    result = structural_profile(
        "## My Heading\nBody content here today.",
        topic="topic",
        baseline_generator=lambda _p: None,
        n_baselines=3,
    )
    assert result["heading_defaultness"] is None


def test_layer_1a_tolerates_baseline_generator_exceptions() -> None:
    """Exceptions raised by the caller-supplied generator are caught
    and counted as failed calls. They must not propagate out of
    ``structural_profile`` or ``measure()``: a flaky LLM client must
    not crash an entire measurement.
    """

    def raising(_p: str) -> str | None:
        raise RuntimeError("simulated LLM rate-limit error")

    # Should not raise. All three calls fail, so 1a returns None.
    result = structural_profile(
        "## My Heading\nBody content here today.",
        topic="topic",
        baseline_generator=raising,
        n_baselines=3,
    )
    assert result["heading_defaultness"] is None
    # 1b and 1c still populate normally on text alone.
    assert isinstance(result["mechanism_ratio"], float)
    assert isinstance(result["assertion_ratio"], float)


def test_layer_1a_tolerates_partial_exceptions() -> None:
    """Mixed failure modes (raises, None returns, successful strings)
    are all handled; only successful string returns count toward
    ``n_baseline_documents``.
    """
    call_count = [0]

    def mixed(_p: str) -> str | None:
        call_count[0] += 1
        if call_count[0] == 1:
            raise ValueError("first call raised")
        if call_count[0] == 2:
            return None
        return "## Some Heading\nText body."

    result = structural_profile(
        "## My Heading\nDoc body.",
        topic="topic",
        baseline_generator=mixed,
        n_baselines=3,
    )
    hd = result["heading_defaultness"]
    assert hd is not None
    # Only the third call succeeded
    assert hd["n_baseline_documents"] == 1


def test_layer_1a_rejects_non_string_return() -> None:
    """A baseline_generator that returns a non-string (e.g. a dict or
    int) is treated as a failed call. The library does not assume any
    particular SDK shape.
    """

    def bad_return(_p: str) -> str | None:
        # Pretend the user accidentally returned the raw API response.
        return {"text": "## Heading\nBody."}  # type: ignore[return-value]

    result = structural_profile(
        "## My Heading\nDoc body.",
        topic="topic",
        baseline_generator=bad_return,
        n_baselines=2,
    )
    assert result["heading_defaultness"] is None


def test_layer_1a_full_overlap_yields_max_default_score() -> None:
    """Document heading words fully present in baseline word union →
    100% overlap → all doc headings match → score = 1.0; is_default True.
    """
    result = structural_profile(
        "## My Heading\nDoc content.",
        topic="topic",
        baseline_generator=lambda _p: "## My Heading\nBaseline body.",
        n_baselines=3,
    )
    hd = result["heading_defaultness"]
    assert hd is not None
    assert hd["jaccard_overlap"] == 1.0
    assert hd["is_default"] is True
    assert hd["n_baseline_documents"] == 3


def test_layer_1a_disjoint_yields_zero_score() -> None:
    """Doc heading words completely disjoint from baseline → 0% overlap →
    no doc headings match → score = 0.0; is_default False.
    """
    result = structural_profile(
        "## Unique Words Here\nDoc content.",
        topic="topic",
        baseline_generator=lambda _p: "## Completely Other Topic\nBody.",
    )
    hd = result["heading_defaultness"]
    assert hd is not None
    assert hd["jaccard_overlap"] == 0.0
    assert hd["is_default"] is False


def test_layer_1a_threshold_strictly_greater_than_half() -> None:
    """A heading with exactly 50% word overlap does NOT count as matching
    the baseline (threshold is strict ``> 0.5``).
    """
    # Doc heading 'Common Words' has 2 words: common, words.
    # Baseline word union: {common, heading} (1 of 2 doc words present).
    # Per-heading overlap = 0.5 → NOT > 0.5 → doesn't match → score = 0.0.
    result = structural_profile(
        "## Common Words\nDoc content.",
        topic="topic",
        baseline_generator=lambda _p: "## Common Heading\nBody.",
    )
    hd = result["heading_defaultness"]
    assert hd is not None
    assert hd["jaccard_overlap"] == 0.0


def test_layer_1a_n_baseline_documents_reflects_successes_only() -> None:
    """``n_baseline_documents`` counts only successful baseline-generator
    calls (None returns are skipped).
    """
    call_count = [0]

    def flaky(_p: str) -> str | None:
        call_count[0] += 1
        # Succeed on calls 1 and 3, fail on call 2
        if call_count[0] == 2:
            return None
        return "## Some Heading\nText."

    result = structural_profile(
        "## My Heading\nDoc.",
        topic="topic",
        baseline_generator=flaky,
        n_baselines=3,
    )
    hd = result["heading_defaultness"]
    assert hd is not None
    # 2 of 3 baseline calls succeeded
    assert hd["n_baseline_documents"] == 2


def test_layer_1a_baseline_generator_invoked_with_topic_in_prompt() -> None:
    """The default baseline prompt includes the topic verbatim."""
    received_prompts: list[str] = []

    def capturing(p: str) -> str | None:
        received_prompts.append(p)
        return "## H\nBody."

    structural_profile(
        "## My Heading\nDoc.",
        topic="quantum computing",
        baseline_generator=capturing,
        n_baselines=2,
    )
    assert len(received_prompts) == 2
    for p in received_prompts:
        assert "quantum computing" in p


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
    """'leverage the X' triggers the buzzword pattern; 'leverage <other>' does
    not. Paired with a mechanism marker so the ratio actually distinguishes
    the cases (testing buzz alone is degenerate: 0 mech / N buzz = 0.0
    regardless of whether buzz fires).
    """
    # 'because' is mech in both. Buzz only fires when leverage is followed by
    # a qualifier word from the pattern list.
    buzz_qual = "Latency drops because we leverage the existing infrastructure."
    no_buzz = "Latency drops because we leverage many tools every single day."
    # buzz_qual: 1 mech + 1 buzz = ratio 1/2 = 0.5
    assert _mechanism_ratio(buzz_qual) == 0.5
    # no_buzz: 1 mech + 0 buzz = ratio 1/1 = 1.0
    assert _mechanism_ratio(no_buzz) == 1.0


def test_robust_qualifier_counted_as_buzzword() -> None:
    """'robust framework/solution/approach/system' triggers buzz; bare 'robust'
    does not. Paired with a mech marker to distinguish the cases.
    """
    triggers = "It fails because the robust framework is hard to maintain."
    # 1 mech + 1 buzz = 0.5
    assert _mechanism_ratio(triggers) == 0.5
    no_trigger = "It fails because the model is robust to noise even at scale."
    # 1 mech + 0 buzz = 1.0 ('robust to' not in pattern list)
    assert _mechanism_ratio(no_trigger) == 1.0


def test_critically_important_counted_as_buzzword() -> None:
    """'critically important' triggers buzz; bare 'critical' does not."""
    triggers = "It fails because this is critically important to the team."
    # 1 mech + 1 buzz = 0.5
    assert _mechanism_ratio(triggers) == 0.5
    no_trigger = "It fails because this is critical work for the entire team."
    # 1 mech + 0 buzz = 1.0
    assert _mechanism_ratio(no_trigger) == 1.0


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


def test_extract_section_bodies_h1_does_not_start_section() -> None:
    """Behaviour: only ## and ### start sections; # (h1) does not."""
    text = "# Top h1 heading\nh1 body content stays orphaned and excluded.\n## Sub\nBody."
    bodies = _extract_section_bodies(text)
    # Only the ## section is captured; the h1 body is dropped as preamble
    assert len(bodies) == 1
    assert "Body." in bodies[0]
    assert "h1 body" not in bodies[0]


def test_extract_section_bodies_h4_does_not_start_section() -> None:
    """Behaviour: #### (h4) does not start a new section.

    h4 lines fall through and accumulate into the current ## or ### body.
    """
    text = "## Top\nA body.\n#### Sub h4\nAfter h4."
    bodies = _extract_section_bodies(text)
    assert len(bodies) == 1
    # h4 line and content after it stays in the parent ## body
    assert "After h4." in bodies[0]


def test_extract_section_bodies_preamble_dropped() -> None:
    """Behaviour: text before the first ## heading is excluded entirely."""
    text = "Preamble paragraph never captured.\n\n## Section\nSection body kept."
    bodies = _extract_section_bodies(text)
    assert len(bodies) == 1
    assert "Preamble" not in bodies[0]
    assert "Section body kept." in bodies[0]


def test_assertion_ratio_with_mixed_h2_h3_sections() -> None:
    """Mixed ## and ### sections all contribute to the body text under
    analysis. Assertion markers in any section count.
    """
    text = (
        "## Top\nA system must always work reliably across the production fleet.\n"
        "### Sub\nThe approach tends to succeed in most documented cases here.\n"
        "## Other\nResults probably appear within the expected window of operation."
    )
    ratio, _precision = _assertion_ratio(text)
    # 'must', 'always' = 2 ASSERTION; 'tends to', 'probably' = 2 QUALIFIED
    # No EVIDENCED markers (avoided 'observed'), no SPECULATIVE
    # ratio = 2 / 4 = 0.5
    assert ratio == 0.5


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
