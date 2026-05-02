"""Output measurement (Touchstone Standard Section 5).

Reference implementation of the eleven measurement layers.

This module provides:

* ``measure()`` - top-level function returning a full ``MeasureResult``
* Individual layer functions for callers needing a specific measurement

All layers operate without invoking AI models on the output, with the
exception of Layer 1a (heading defaultness) which OPTIONALLY uses an
LLM API for baseline generation.

Implementation status: skeleton. Layer functions raise ``NotImplementedError``
until extracted from the operator's research vault. See Appendix C of the
Standard for the layer-by-layer status.
"""

from __future__ import annotations

from clarethium_touchstone._version import __standard_version__, __version__
from clarethium_touchstone.types import (
    ClaimDensity,
    EntityProvenance,
    EpistemicCalibration,
    GroundingDecomposition,
    InformationNovelty,
    MeasureResult,
    PresentationFeatures,
    QualityProfile,
    SourceMatching,
    StructuralProfile,
    TemporalInstability,
    VocabularyProximity,
)


def measure(
    text: str,
    *,
    source: str | None = None,
    comparisons: list[str] | None = None,
    topic: str | None = None,
    p_detection_mode: str = "conservative",
) -> MeasureResult:
    """Run all applicable measurement layers on ``text``.

    Layers 1b, 1c, 2, 7, 9, 10 run on any text. Layers 4, 5, 6, 8, 11
    require ``source``. Layer 3 requires ``comparisons``. Layer 1a
    (heading defaultness) is optional and requires ``topic`` plus an
    LLM API.

    Args:
        text: The output to measure.
        source: Optional source material the output may reference.
        comparisons: Optional alternative versions of the output for
            temporal instability measurement.
        topic: Optional topic string for Layer 1a baseline generation.
        p_detection_mode: ``conservative`` (default) or ``liberal``
            for Layer 11 P-marker detection.

    Returns:
        A ``MeasureResult`` with one key per applicable layer plus
        version metadata.

    Raises:
        NotImplementedError: Library extraction in progress; see
            ``CHANGELOG.md`` for release status.
    """
    raise NotImplementedError(
        "Library extraction in progress. The Touchstone Standard 1.0 is "
        "the canonical reference; see STANDARDS/touchstone-1.0.md."
    )


# -- Layer 1: Structural profile ------------------------------------------


def structural_profile(text: str, *, topic: str | None = None) -> StructuralProfile:
    """Layer 1: heading defaultness (1a, optional), mechanism ratio (1b),
    assertion ratio (1c)."""
    raise NotImplementedError


# -- Layer 2: Claim density -----------------------------------------------


def claim_density(text: str) -> ClaimDensity:
    """Layer 2: numerical and causal claim counts per 1000 words."""
    raise NotImplementedError


# -- Layer 3: Temporal instability ----------------------------------------


def temporal_instability(text: str, comparisons: list[str]) -> TemporalInstability:
    """Layer 3: instability rate of digit-formatted numbers across versions."""
    raise NotImplementedError


# Deprecated alias, removed in v2.0
fabrication_rate = temporal_instability


# -- Layer 4: Source matching ---------------------------------------------


def source_matching(text: str, source: str) -> SourceMatching:
    """Layer 4: unsourced rate of digit-formatted numbers."""
    raise NotImplementedError


# -- Layer 5: Entity provenance -------------------------------------------


def entity_provenance(text: str, source: str) -> EntityProvenance:
    """Layer 5: unsourced rate of named entities."""
    raise NotImplementedError


# -- Layer 6: Vocabulary proximity ----------------------------------------


def vocabulary_proximity(text: str, source: str) -> VocabularyProximity:
    """Layer 6: per-sentence content word overlap with source."""
    raise NotImplementedError


# -- Layer 7: Presentation features ---------------------------------------


def presentation_features(text: str) -> PresentationFeatures:
    """Layer 7: TTR, FK grade, formatting density, assertiveness, named
    concept count."""
    raise NotImplementedError


# -- Layer 8: Epistemic calibration ---------------------------------------


def epistemic_calibration(text: str, source: str) -> EpistemicCalibration:
    """Layer 8 (experimental): grounded assertions / total assertions."""
    raise NotImplementedError


# -- Layer 9: Information novelty -----------------------------------------


def information_novelty(text: str) -> InformationNovelty:
    """Layer 9 (experimental): per-sentence lexical novelty."""
    raise NotImplementedError


# -- Layer 10: Quality profile --------------------------------------------


def quality_profile(
    text: str,
    *,
    source: str | None = None,
    comparisons: list[str] | None = None,
) -> QualityProfile:
    """Layer 10: composite substance vs presentation index plus gap.

    Validated across four studies (cross-condition, cross-generator,
    dose-response gradient). See Standard Section 7.4 for threshold
    interpretation.
    """
    raise NotImplementedError


# -- Layer 11: Grounding decomposition (G/F/P) ----------------------------


def grounding_decomposition(
    text: str,
    source: str,
    *,
    p_detection_mode: str = "conservative",
) -> GroundingDecomposition:
    """Layer 11: per-sentence Grounded / Framed / Projected classification.

    REQUIRED per Standard Section 5.11 when source material is provided.
    Reports document-level proportions and per-sentence classifications.

    Args:
        text: The output to classify.
        source: The source material against which grounding is measured.
        p_detection_mode: ``conservative`` (default) or ``liberal``.
            Conservative is required for conformance.

    Returns:
        A ``GroundingDecomposition`` with proportions, per-sentence
        classifications, projection presence flag, and recommendation
        string when projection is detected.
    """
    raise NotImplementedError


# -- Re-exports for the public API ----------------------------------------

__all__ = [
    "measure",
    "structural_profile",
    "claim_density",
    "temporal_instability",
    "fabrication_rate",  # deprecated alias
    "source_matching",
    "entity_provenance",
    "vocabulary_proximity",
    "presentation_features",
    "epistemic_calibration",
    "information_novelty",
    "quality_profile",
    "grounding_decomposition",
]


# Library and Standard version metadata
LIBRARY_VERSION = __version__
STANDARD_VERSION = __standard_version__
