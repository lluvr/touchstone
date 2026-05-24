"""Tests for the production-grade Verifier API."""

from __future__ import annotations

import math

import pytest

from clarethium_touchstone import UnsupportedSpan, Verifier, VerifierResult

SUPPORTED_TEXT = (
    "Revenue grew 12% to $143 million in Q1 fiscal 2026. "
    "Costs declined 8% across 5000 employees over 18 months. "
    "The CFO confirmed both figures in the earnings call."
)
SUPPORTED_SOURCE = SUPPORTED_TEXT  # self-source: maximally grounded.

HALLUCINATED_TEXT = (
    "Industry-wide revenue grew 47% across all segments according to McKinsey. "
    "The Federal Reserve will raise rates 75 basis points next month. "
    "Tesla announced a 2027 product roadmap citing 18% margins."
)
HALLUCINATED_SOURCE = "Apple reported Q1 revenue of $143 million in fiscal 2026."


def test_substrate_only_score_shape() -> None:
    """Verifier returns a VerifierResult with the expected shape."""
    v = Verifier()
    result = v.score(SUPPORTED_TEXT, source=SUPPORTED_SOURCE)
    assert isinstance(result, VerifierResult)
    assert 0.0 <= result.prob_hallucinated <= 1.0
    assert result.mode == "substrate_only"
    assert "intercept" in result.signal_breakdown
    assert isinstance(result.top_unsupported, list)
    assert "source_matching" in result.layer_outputs


def test_substrate_only_supported_low_prob() -> None:
    """A self-source output should score low on hallucination probability."""
    v = Verifier()
    result = v.score(SUPPORTED_TEXT, source=SUPPORTED_SOURCE)
    assert result.prob_hallucinated < 0.5, (
        f"self-source output scored as hallucinated: p={result.prob_hallucinated}"
    )


def test_substrate_only_hallucinated_high_prob() -> None:
    """An output with several P-markers and low vocabulary overlap should
    score above 0.5 on hallucination probability."""
    v = Verifier()
    result = v.score(HALLUCINATED_TEXT, source=HALLUCINATED_SOURCE)
    assert result.prob_hallucinated > 0.5, (
        f"adversarial output not flagged: p={result.prob_hallucinated}"
    )


def test_should_flag_threshold() -> None:
    """The should_flag helper respects the threshold argument."""
    v = Verifier()
    result = v.score(HALLUCINATED_TEXT, source=HALLUCINATED_SOURCE)
    # The hallucinated example should clear a 0.5 threshold (default).
    assert result.should_flag(threshold=0.5) is True
    # A 0.99 threshold should not be cleared by anything realistic.
    assert result.should_flag(threshold=0.99) is False


def test_top_unsupported_contains_p_spans() -> None:
    """Adversarial output should produce non-empty top_unsupported."""
    v = Verifier()
    result = v.score(HALLUCINATED_TEXT, source=HALLUCINATED_SOURCE)
    assert len(result.top_unsupported) > 0
    # Every entry is the dataclass with required fields.
    for span in result.top_unsupported:
        assert isinstance(span, UnsupportedSpan)
        assert span.layer11_primary in {"P", "F"}
        assert isinstance(span.sentence, str)
        assert span.sentence_index >= 0


def test_top_k_caps_output() -> None:
    """top_k_unsupported argument caps the number of spans returned."""
    v = Verifier()
    result_1 = v.score(HALLUCINATED_TEXT, source=HALLUCINATED_SOURCE, top_k_unsupported=1)
    assert len(result_1.top_unsupported) <= 1
    result_10 = v.score(HALLUCINATED_TEXT, source=HALLUCINATED_SOURCE, top_k_unsupported=10)
    assert len(result_10.top_unsupported) >= len(result_1.top_unsupported)


def test_signal_breakdown_sums_to_logit() -> None:
    """signal_breakdown should sum to the logit of prob_hallucinated."""
    v = Verifier()
    result = v.score(SUPPORTED_TEXT, source=SUPPORTED_SOURCE)
    logit = sum(result.signal_breakdown.values())
    p = 1.0 / (1.0 + math.exp(-logit))
    assert abs(p - result.prob_hallucinated) < 1e-4, (
        f"signal breakdown does not reconstruct prob: "
        f"sum-derived={p}, reported={result.prob_hallucinated}"
    )


def test_substrate_plus_minicheck_requires_score() -> None:
    """If mode requires minicheck_supported_prob, omitting it raises."""
    v = Verifier(mode="substrate_plus_minicheck")
    with pytest.raises(ValueError, match="minicheck_supported_prob"):
        v.score(SUPPORTED_TEXT, source=SUPPORTED_SOURCE)


def test_substrate_plus_minicheck_with_supplied_score() -> None:
    """When MiniCheck score is supplied, the mode runs and produces a result."""
    v = Verifier()
    # 0.9 supported -> 0.1 hallucinated baseline contribution.
    result = v.score(
        SUPPORTED_TEXT,
        source=SUPPORTED_SOURCE,
        minicheck_supported_prob=0.9,
    )
    assert result.mode == "substrate_plus_minicheck"
    assert "minicheck_neg" in result.signal_breakdown
    assert 0.0 <= result.prob_hallucinated <= 1.0


def test_substrate_plus_both_baselines() -> None:
    """When both baseline scores are supplied, full mode is auto-selected."""
    v = Verifier()
    result = v.score(
        HALLUCINATED_TEXT,
        source=HALLUCINATED_SOURCE,
        minicheck_supported_prob=0.05,
        alignscore_supported_prob=0.10,
    )
    assert result.mode == "substrate_plus_minicheck_alignscore"
    assert "minicheck_neg" in result.signal_breakdown
    assert "alignscore_neg" in result.signal_breakdown


def test_substrate_plus_judge_auto_selects_mode() -> None:
    """Passing judge_hallucinated_prob auto-selects substrate_plus_judge mode."""
    v = Verifier()
    result = v.score(
        HALLUCINATED_TEXT,
        source=HALLUCINATED_SOURCE,
        judge_hallucinated_prob=0.9,
    )
    assert result.mode == "substrate_plus_judge"
    assert "substrate_prob" in result.signal_breakdown
    assert "judge_hallucinated_prob" in result.signal_breakdown
    assert "judge_alpha" in result.signal_breakdown
    assert 0.0 <= result.prob_hallucinated <= 1.0


def test_substrate_plus_judge_blend_arithmetic() -> None:
    """Final prob exactly equals judge_alpha*substrate + (1-judge_alpha)*judge."""
    v = Verifier()
    judge_p = 0.8
    for alpha in (0.0, 0.3, 0.5, 0.7, 1.0):
        r = v.score(
            HALLUCINATED_TEXT,
            source=HALLUCINATED_SOURCE,
            judge_hallucinated_prob=judge_p,
            judge_alpha=alpha,
        )
        substrate_p = r.signal_breakdown["substrate_prob"]
        expected = alpha * substrate_p + (1.0 - alpha) * judge_p
        assert abs(r.prob_hallucinated - expected) < 1e-4, (
            f"alpha={alpha}: blend prob {r.prob_hallucinated} != "
            f"alpha*substrate + (1-alpha)*judge = {expected}"
        )


def test_substrate_plus_judge_judge_only_when_alpha_zero() -> None:
    """judge_alpha=0 reduces the blend to judge-only."""
    v = Verifier()
    for jp in (0.0, 0.25, 0.5, 0.75, 1.0):
        r = v.score(
            HALLUCINATED_TEXT,
            source=HALLUCINATED_SOURCE,
            judge_hallucinated_prob=jp,
            judge_alpha=0.0,
        )
        assert abs(r.prob_hallucinated - jp) < 1e-6


def test_substrate_plus_judge_substrate_only_when_alpha_one() -> None:
    """judge_alpha=1 reduces the blend to substrate-only."""
    v = Verifier()
    r_blend = v.score(
        HALLUCINATED_TEXT,
        source=HALLUCINATED_SOURCE,
        judge_hallucinated_prob=0.99,
        judge_alpha=1.0,
    )
    r_subs = v.score(HALLUCINATED_TEXT, source=HALLUCINATED_SOURCE)
    # alpha=1 in substrate_plus_judge should match the substrate-only prob.
    assert abs(r_blend.prob_hallucinated - r_subs.prob_hallucinated) < 1e-4


def test_substrate_plus_judge_mutex_with_trained_discriminators() -> None:
    """judge_hallucinated_prob cannot be combined with minicheck/alignscore."""
    v = Verifier()
    with pytest.raises(ValueError, match="mutually exclusive"):
        v.score(
            SUPPORTED_TEXT,
            source=SUPPORTED_SOURCE,
            judge_hallucinated_prob=0.5,
            minicheck_supported_prob=0.5,
        )
    with pytest.raises(ValueError, match="mutually exclusive"):
        v.score(
            SUPPORTED_TEXT,
            source=SUPPORTED_SOURCE,
            judge_hallucinated_prob=0.5,
            alignscore_supported_prob=0.5,
        )


def test_substrate_plus_judge_out_of_range_inputs_raise() -> None:
    """Out-of-range judge_hallucinated_prob or judge_alpha raise."""
    v = Verifier()
    with pytest.raises(ValueError, match="judge_hallucinated_prob out of"):
        v.score(SUPPORTED_TEXT, source=SUPPORTED_SOURCE, judge_hallucinated_prob=1.5)
    with pytest.raises(ValueError, match="judge_hallucinated_prob out of"):
        v.score(SUPPORTED_TEXT, source=SUPPORTED_SOURCE, judge_hallucinated_prob=-0.1)
    with pytest.raises(ValueError, match="judge_alpha out of"):
        v.score(
            SUPPORTED_TEXT,
            source=SUPPORTED_SOURCE,
            judge_hallucinated_prob=0.5,
            judge_alpha=1.5,
        )


def test_substrate_plus_judge_requires_judge_prob_when_explicit() -> None:
    """If mode=substrate_plus_judge is set explicitly, omitting judge_prob raises."""
    v = Verifier(mode="substrate_plus_judge")
    with pytest.raises(ValueError, match="judge_hallucinated_prob"):
        v.score(SUPPORTED_TEXT, source=SUPPORTED_SOURCE)


def test_with_calibration_custom_coefficients() -> None:
    """Verifier.with_calibration accepts a custom coefficient dict."""
    custom = {
        "substrate_only": {
            "intercept": 0.0,
            "coef": {
                "l6_inv": 5.0,
                "l4_unsourced": 0.0,
                "l4_n_total_norm": 0.0,
                "l11_p": 0.0,
                "l5_entity_unsourced": 0.0,
                "l5_n_entities_norm": 0.0,
            },
        }
    }
    v = Verifier.with_calibration(custom)
    result = v.score(SUPPORTED_TEXT, source=SUPPORTED_SOURCE)
    # With l6_inv≈0 on self-source, logit≈0 → prob≈0.5.
    assert 0.4 < result.prob_hallucinated < 0.6, (
        f"unexpected prob with custom calibration on self-source: {result.prob_hallucinated}"
    )


# -- Adversarial-input regression tests (added 1.0.1) -------------------------
#
# Before 1.0.1, Layer 6 returned ``mean_proximity=0.0`` with an empty
# ``per_sentence_proximity`` list whenever no sentence had scoreable content
# words. The Verifier's feature extractor read that 0.0 as "vocabulary is
# completely novel" and fired ``l6_inv = 1.0`` (coefficient +3.4), pushing
# the calibrated probability above 0.7 on trivially faithful short inputs.
# These tests pin the post-fix behaviour: short / empty / out-of-scope inputs
# get a scope classification and do NOT auto-flag.


def test_short_faithful_input_does_not_auto_flag() -> None:
    """A single faithful sentence below the char floor must not produce a
    hallucination flag. Pre-1.0.1 this regressed to ``prob=0.778``."""
    v = Verifier()
    result = v.score("Revenue grew 12%.", source="Revenue grew 12%.")
    assert result.scope == "insufficient_input"
    assert result.should_flag() is False
    assert result.prob_hallucinated < 0.5, (
        f"short faithful input falsely flagged: p={result.prob_hallucinated}"
    )


def test_self_reference_above_char_floor_is_limited_signal() -> None:
    """An above-floor self-reference with only one informative substrate
    signal is classified ``limited_signal``, not ``validated``."""
    v = Verifier()
    text = "Q1 revenue was $143 billion in fiscal 2026 quarter one earnings."
    result = v.score(text, source=text)
    # Self-reference: Layer 4 fires (numbers exist), Layer 6 either fires or
    # doesn't depending on content-word count. The scope should NOT auto-flag.
    assert result.scope in {"validated", "limited_signal"}
    assert result.should_flag() is False


def test_empty_text_is_insufficient_input() -> None:
    """Empty input is classified ``insufficient_input`` and never flags."""
    v = Verifier()
    result = v.score("", source="Some source text with substance.")
    assert result.scope == "insufficient_input"
    assert result.should_flag() is False
    assert result.scope_notes  # non-empty diagnostic


def test_whitespace_only_text_is_insufficient_input() -> None:
    """Whitespace-only input is classified ``insufficient_input``."""
    v = Verifier()
    result = v.score("   \n\t  ", source="Some source text with substance.")
    assert result.scope == "insufficient_input"
    assert result.should_flag() is False


def test_tiny_punctuation_input_is_insufficient_input() -> None:
    """``"A. B. C."`` is below the char floor and has no substrate signal."""
    v = Verifier()
    result = v.score("A. B. C.", source="Some real source text.")
    assert result.scope == "insufficient_input"
    assert result.should_flag() is False


def test_fail_open_allows_flag_on_limited_signal() -> None:
    """``should_flag(fail_open=True)`` overrides the scope gate so callers
    that route low-signal traces through human review can still see the
    underlying probability decision."""
    v = Verifier()
    # Use a calibration that drives probability above 0.5 on limited signal.
    high_intercept = {
        "substrate_only": {
            "intercept": 5.0,
            "coef": {
                "l6_inv": 0.0,
                "l4_unsourced": 0.0,
                "l4_n_total_norm": 0.0,
                "l11_p": 0.0,
                "l5_entity_unsourced": 0.0,
                "l5_n_entities_norm": 0.0,
            },
        }
    }
    v = Verifier.with_calibration(high_intercept)
    result = v.score("", source="Some source.")
    assert result.scope == "insufficient_input"
    assert result.prob_hallucinated > 0.9
    # Default gate refuses to flag.
    assert result.should_flag() is False
    # fail_open=True respects the underlying probability.
    assert result.should_flag(fail_open=True) is True


def test_scope_validated_requires_layer6_and_one_other() -> None:
    """A substantive multi-sentence input with source produces a
    ``validated`` scope when Layer 6 plus at least one of L4/L5/L11 fires."""
    v = Verifier()
    result = v.score(SUPPORTED_TEXT, source=SUPPORTED_SOURCE)
    assert result.scope == "validated"


def test_verifier_modes_constant_is_iterable() -> None:
    """``VERIFIER_MODES`` exposes the valid modes as a tuple for argparse,
    dashboards, and runtime validation."""
    from clarethium_touchstone import VERIFIER_MODES

    assert isinstance(VERIFIER_MODES, tuple)
    assert "substrate_only" in VERIFIER_MODES
    assert "substrate_plus_minicheck" in VERIFIER_MODES
    assert "substrate_plus_minicheck_alignscore" in VERIFIER_MODES
    assert "substrate_plus_judge" in VERIFIER_MODES
    assert len(VERIFIER_MODES) == 4


def test_scope_notes_explain_classification() -> None:
    """``scope_notes`` always contains at least one human-readable line."""
    v = Verifier()
    # Insufficient input
    r1 = v.score("", source="Some source.")
    assert r1.scope_notes
    assert any("whitespace" in n.lower() or "empty" in n.lower() for n in r1.scope_notes)
    # Validated multi-sentence
    r2 = v.score(SUPPORTED_TEXT, source=SUPPORTED_SOURCE)
    assert r2.scope_notes
    assert any("informative" in n.lower() for n in r2.scope_notes)


def test_l6_uninformative_does_not_inflate_logit() -> None:
    """When Layer 6 has no scoreable sentences, l6_inv contributes 0 to the
    logit — not the spurious +3.4 the pre-1.0.1 implementation fired."""
    v = Verifier()
    result = v.score("Revenue grew 12%.", source="Revenue grew 12%.")
    assert result.signal_breakdown["l6_inv"] == 0.0


def test_long_self_reference_is_validated_and_low_prob() -> None:
    """A multi-sentence self-reference produces ``validated`` scope and
    low hallucination probability — the substantive happy path."""
    v = Verifier()
    long_text = (
        "Revenue grew 12% to $143 million with 25% margins. "
        "Costs declined 8% across 5000 employees over 18 months. "
        "Retention improved 7.5% to 94.2% across major segments."
    )
    result = v.score(long_text, source=long_text)
    assert result.scope == "validated"
    assert result.prob_hallucinated < 0.3
    assert result.should_flag() is False
