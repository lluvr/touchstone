"""Production-grade calibrated Verifier on top of the Touchstone substrate.

The :class:`Verifier` provides the single ``score(text, source)`` API
that production adopters actually need: a calibrated probability that
the output is hallucinated, with span-level localization and an
explicit signal breakdown. It is built on top of :func:`measure` and
is intentionally thin — the heavy lifting is in the substrate layers
that :func:`measure` already exposes.

Three operating modes, listed in order of increasing accuracy and
increasing per-call latency:

* **Substrate-only** (default; no extra dependencies, sub-100 ms on
  5 KB documents). Default-calibrated AUC ≈ 0.67-0.76 on three external
  summarization corpora — research-tier signal strength; suitable for
  drift detection and regression testing alongside other tooling, not
  for sole-source audit decisions.
* **Substrate + caller-supplied baseline score** (e.g., MiniCheck or
  AlignScore; the caller invokes the model and passes its supported-
  probability). AUC ≈ 0.76-0.86 across the same corpora.
* **Substrate + two baseline scores** (MiniCheck + AlignScore both
  supplied by the caller). AUC ≈ 0.77-0.86.

The honest empirical bound is documented in ``docs/methodology.md``
and in the §Empirical validation section of the README. Adopters
SHOULD recalibrate the coefficients on their own held-out data if
their input distribution differs materially from English news
summarization; the :meth:`Verifier.with_calibration` constructor
accepts a custom coefficient dict in the same shape as the embedded
default.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

from clarethium_touchstone._calibration import DEFAULT_CALIBRATION_2026_05_17
from clarethium_touchstone.measure import measure
from clarethium_touchstone.types import MeasureResult

# Public API uses a discriminated mode literal so a caller can pick
# between substrate-only and external-augmented modes deterministically.
VerifierMode = Literal[
    "substrate_only",
    "substrate_plus_minicheck",
    "substrate_plus_minicheck_alignscore",
]


@dataclass(frozen=True)
class UnsupportedSpan:
    """A single output span identified as likely unsupported by the source."""

    sentence: str
    """The sentence text, trimmed of leading/trailing whitespace."""

    sentence_index: int
    """Zero-indexed position in the order :func:`measure` segments the output."""

    layer11_primary: str
    """The Layer 11 G/F/P classification for this sentence (``"G"``, ``"F"``, or ``"P"``)."""

    p_markers: list[str] = field(default_factory=list)
    """If the sentence was classified as P, the list of triggering markers
    (``"unsourced_numbers"``, ``"external_entities"``, ``"unsourced_years"``).
    Empty when the sentence is G or F."""

    grounding_score: float | None = None
    """The Layer 11 grounding score in [0, 1] when the sentence was classified
    as G or F; ``None`` for P-classified sentences (which use marker logic
    rather than the score)."""


@dataclass(frozen=True)
class VerifierResult:
    """Calibrated verification output for a single (text, source) pair.

    Adopters should treat :attr:`prob_hallucinated` as the primary
    decision signal and :attr:`signal_breakdown` as the explanation.
    :attr:`top_unsupported` provides span-level localization sourced
    from Layer 11's per-sentence classifications.
    """

    prob_hallucinated: float
    """Calibrated probability in [0, 1] that the output is hallucinated."""

    mode: VerifierMode
    """Which calibration mode produced this score."""

    signal_breakdown: dict[str, float]
    """Per-feature contribution to the calibrated probability. Keys match
    the calibration coefficient names; values are the (coefficient * feature)
    terms, summed with the intercept to recover the logit of
    ``prob_hallucinated``."""

    top_unsupported: list[UnsupportedSpan]
    """Sentences ranked by likelihood of being unsupported, with Layer 11
    classification details. P-classified sentences come first; F-classified
    sentences with low grounding scores come next; G-classified sentences
    are excluded. Length is capped by the ``top_k`` argument to :meth:`score`."""

    layer_outputs: MeasureResult
    """The raw :class:`MeasureResult` returned by :func:`measure` for this
    pair, included so adopters can drill into any specific layer if needed
    without re-running the measurement."""

    def should_flag(self, threshold: float = 0.5) -> bool:
        """Convenience method: True iff :attr:`prob_hallucinated` exceeds the threshold."""
        return self.prob_hallucinated >= threshold


_FEATURE_NAMES = [
    "l6_inv",
    "l4_unsourced",
    "l4_n_total_norm",
    "l11_p",
    "l5_entity_unsourced",
    "l5_n_entities_norm",
]


def _extract_substrate_features(measure_result: MeasureResult) -> dict[str, float]:
    """Pull the six substrate features out of a :func:`measure` result.

    Returns a dict keyed by feature name; values are normalized to [0, 1]
    so the calibration coefficients are scale-invariant. Requires that the
    measure result was produced with ``source`` provided; the source-
    dependent layers (4, 5, 6, 11) must be present and non-None.
    """
    sm = measure_result["source_matching"]
    ep = measure_result["entity_provenance"]
    vp = measure_result["vocabulary_proximity"]
    gd = measure_result["grounding_decomposition"]
    if sm is None or ep is None or vp is None or gd is None:
        raise ValueError(
            "Verifier requires a measure() result with source provided; "
            "source_matching, entity_provenance, vocabulary_proximity, and "
            "grounding_decomposition must all be present."
        )

    mean_prox = vp["mean_proximity"] if vp["mean_proximity"] is not None else 1.0
    n_total = sm["n_total"]
    n_entities = ep["n_entities"]

    return {
        "l6_inv": 1.0 - mean_prox,
        "l4_unsourced": sm["unsourced_rate"] if n_total > 0 else 0.0,
        "l4_n_total_norm": min(n_total / 10.0, 1.0),
        "l11_p": gd["proportions"]["P"],
        "l5_entity_unsourced": ep["entity_unsourced_rate"] if n_entities >= 5 else 0.0,
        "l5_n_entities_norm": min(n_entities / 10.0, 1.0),
    }


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def _identify_unsupported_spans(measure_result: MeasureResult, top_k: int) -> list[UnsupportedSpan]:
    """Rank output sentences by likelihood of being unsupported.

    P-classified sentences are ranked first (most likely unsupported); then
    F-classified sentences ordered by ascending grounding_score. G-classified
    sentences are excluded. Up to ``top_k`` spans are returned.
    """
    gd = measure_result["grounding_decomposition"]
    if gd is None:
        return []
    sentences = gd["sentence_classifications"]

    p_spans: list[UnsupportedSpan] = []
    f_spans: list[UnsupportedSpan] = []
    for i, s in enumerate(sentences):
        sent = s.get("sentence", "").strip()
        primary = s.get("primary", "")
        if primary == "P":
            p_spans.append(
                UnsupportedSpan(
                    sentence=sent,
                    sentence_index=i,
                    layer11_primary="P",
                    p_markers=list(s.get("p_markers", [])),
                    grounding_score=None,
                )
            )
        elif primary == "F":
            gs = s.get("grounding_score")
            f_spans.append(
                UnsupportedSpan(
                    sentence=sent,
                    sentence_index=i,
                    layer11_primary="F",
                    p_markers=[],
                    grounding_score=float(gs) if gs is not None else None,
                )
            )

    # F-spans: lowest grounding_score first (most-suspect F first).
    f_spans.sort(key=lambda s: s.grounding_score if s.grounding_score is not None else 1.0)

    return (p_spans + f_spans)[:top_k]


class Verifier:
    """Calibrated production verifier for (output, source) pairs.

    Usage::

        from clarethium_touchstone import Verifier

        v = Verifier()  # substrate-only
        result = v.score(text=output, source=document)
        if result.should_flag(threshold=0.5):
            print(f"Flagged (p={result.prob_hallucinated:.2f})")
            for span in result.top_unsupported:
                print(f"  - {span.layer11_primary}: {span.sentence!r}")

    For the substrate-plus-baseline modes the caller invokes the baseline
    model themselves and passes its supported-probability score::

        result = v.score(
            text=output,
            source=document,
            minicheck_supported_prob=mc_prob,
            alignscore_supported_prob=as_prob,
        )

    The verifier accepts either or both baseline scores when in the
    appropriate mode; the mode is auto-selected from which baselines
    are provided.
    """

    def __init__(
        self,
        *,
        calibration: dict[str, Any] | None = None,
        mode: VerifierMode | None = None,
    ) -> None:
        """Construct a verifier.

        Args:
            calibration: Optional custom calibration dict in the same shape
                as :data:`DEFAULT_CALIBRATION_2026_05_17`. Adopters with
                their own held-out training data should re-fit and supply
                their own coefficients here. Defaults to the embedded
                default trained on RAGTruth Summary.
            mode: Optional explicit mode selector. If omitted, the mode is
                inferred at :meth:`score` time from which baseline scores
                are provided.
        """
        self._calibration: dict[str, Any] = calibration or DEFAULT_CALIBRATION_2026_05_17
        self._explicit_mode: VerifierMode | None = mode

    def score(
        self,
        text: str,
        *,
        source: str,
        minicheck_supported_prob: float | None = None,
        alignscore_supported_prob: float | None = None,
        top_k_unsupported: int = 3,
    ) -> VerifierResult:
        """Score a single (output, source) pair.

        Args:
            text: The AI-generated output to verify.
            source: The grounding source the output should be supported by.
            minicheck_supported_prob: Optional MiniCheck supported-probability
                in [0, 1] (caller invokes MiniCheck themselves). Higher means
                more supported.
            alignscore_supported_prob: Optional AlignScore supported-probability
                in [0, 1] (caller invokes AlignScore themselves). Higher means
                more supported.
            top_k_unsupported: Maximum number of unsupported spans to return.

        Returns:
            A :class:`VerifierResult` with the calibrated probability, mode,
            signal breakdown, top unsupported spans, and the raw measure()
            output for drill-down.
        """
        # Auto-select mode from supplied baselines, unless explicitly set.
        if self._explicit_mode is not None:
            mode = self._explicit_mode
        elif minicheck_supported_prob is not None and alignscore_supported_prob is not None:
            mode = "substrate_plus_minicheck_alignscore"
        elif minicheck_supported_prob is not None:
            mode = "substrate_plus_minicheck"
        else:
            mode = "substrate_only"

        # Compute substrate features via measure().
        measure_result = measure(text, source=source)
        substrate = _extract_substrate_features(measure_result)

        # Build the feature vector matching the mode's calibration shape.
        calib = self._calibration[mode]
        coefs = calib["coef"]
        intercept = float(calib["intercept"])

        features: dict[str, float] = dict(substrate)
        if "minicheck_neg" in coefs:
            if minicheck_supported_prob is None:
                raise ValueError(
                    f"mode={mode!r} requires minicheck_supported_prob; pass it to score()."
                )
            features["minicheck_neg"] = 1.0 - float(minicheck_supported_prob)
        if "alignscore_neg" in coefs:
            if alignscore_supported_prob is None:
                raise ValueError(
                    f"mode={mode!r} requires alignscore_supported_prob; pass it to score()."
                )
            features["alignscore_neg"] = 1.0 - float(alignscore_supported_prob)

        # Compute logit and signal breakdown.
        logit = intercept
        breakdown: dict[str, float] = {"intercept": intercept}
        for name, coef in coefs.items():
            contrib = float(coef) * features[name]
            logit += contrib
            breakdown[name] = round(contrib, 6)
        prob = _sigmoid(logit)

        # Per-sentence localization from Layer 11 classifications.
        unsupported = _identify_unsupported_spans(measure_result, top_k_unsupported)

        return VerifierResult(
            prob_hallucinated=round(prob, 6),
            mode=mode,
            signal_breakdown=breakdown,
            top_unsupported=unsupported,
            layer_outputs=measure_result,
        )

    @classmethod
    def with_calibration(cls, calibration: dict[str, Any]) -> Verifier:
        """Construct a verifier with a custom calibration dict.

        Adopters who have re-trained the logistic regression on their own
        held-out data pass the resulting coefficient dict (in the same shape
        as :data:`DEFAULT_CALIBRATION_2026_05_17`) here.
        """
        return cls(calibration=calibration)


__all__ = [
    "UnsupportedSpan",
    "Verifier",
    "VerifierMode",
    "VerifierResult",
]
