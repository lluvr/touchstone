"""Type definitions for Touchstone return values.

These TypedDicts mirror the Standard's specified output formats. They
are part of the public API contract; changes require Standard version
bumps per Section 10 of the Standard.
"""

from __future__ import annotations

from typing import Literal, TypedDict

# -- Output measurement (Standard Section 5) -------------------------------


class HeadingDefaultness(TypedDict, total=False):
    """Layer 1a output (optional; requires LLM API).

    Returns ``None`` when topic or LLM API not provided.
    """

    jaccard_overlap: float
    is_default: bool
    n_baseline_documents: int


class StructuralProfile(TypedDict):
    """Layer 1 (composite of 1a, 1b, 1c)."""

    heading_defaultness: HeadingDefaultness | None
    mechanism_ratio: float
    assertion_ratio: float
    assertion_precision: Literal["high", "adequate", "low"]


class ClaimDensity(TypedDict):
    """Layer 2."""

    numerical_per_1kw: float
    causal_per_1kw: float
    n_numerical: int
    n_causal: int
    n_words: int


class TemporalInstability(TypedDict):
    """Layer 3.

    Note: ``fabrication_rate`` alias for ``instability_rate`` is
    deprecated and will be removed in v2.0.
    """

    instability_rate: float
    n_unstable: int
    n_total: int
    versions_compared: int


class UnsourcedNumber(TypedDict):
    """A digit-formatted number from the output not found in the source.

    Contains the literal value, the recognised type (percentage, dollar,
    multiplier, integer, decimal), and a short context window from the
    output to aid debugging and review.
    """

    value: str
    type: str
    context: str


class SourceMatching(TypedDict):
    """Layer 4 (source fidelity / number provenance).

    ``unsourced_rate`` is the headline metric: fraction of digit-formatted
    numbers in the output that are not found in the source via exact string
    search. ``precision`` indicates the reliability of the rate given the
    total number count (``low`` < 10, ``adequate`` < 30, ``good`` >= 30).
    """

    unsourced_rate: float
    n_in_source: int
    n_unsourced: int
    n_total: int
    precision: Literal["low", "adequate", "good"]
    unsourced_details: list[UnsourcedNumber]


class EntityProvenance(TypedDict):
    """Layer 5."""

    entity_unsourced_rate: float
    n_entities: int
    n_unsourced: int
    unsourced_entities: list[str]


class VocabularyProximity(TypedDict):
    """Layer 6."""

    mean_proximity: float
    per_sentence_proximity: list[float]


class PresentationFeatures(TypedDict):
    """Layer 7."""

    type_token_ratio: float
    fk_grade: float
    formatting_density: float
    assertiveness_ratio: float
    named_concept_count: int


class EpistemicCalibration(TypedDict):
    """Layer 8 (experimental in v1.0)."""

    calibration_score: float
    overclaiming_rate: float
    n_assertions: int
    n_grounded: int
    precision: Literal["high", "adequate", "low"]


class InformationNovelty(TypedDict):
    """Layer 9 (experimental in v1.0).

    Note: lexical novelty only; length-confounded by Heaps' law.
    """

    mean_novelty: float
    repetition_rate: float
    decay: float
    q1_novelty: float
    q4_novelty: float


class QualityProfile(TypedDict):
    """Layer 10 (composite)."""

    substance_index: float
    presentation_index: float
    gap: float
    components: dict[str, float]
    components_available: list[str]


GFPCategory = Literal["G", "F", "P"]


class GFPProportions(TypedDict):
    G: float
    F: float
    P: float


class GFPSentence(TypedDict, total=False):
    sentence: str
    primary: GFPCategory
    grounding_score: float
    p_markers: list[str]


class GroundingDecomposition(TypedDict):
    """Layer 11 (G/F/P decomposition).

    REQUIRED when source material is provided per Standard Section 5.11.
    """

    proportions: GFPProportions
    sentence_classifications: list[GFPSentence]
    p_detection_mode: Literal["conservative", "liberal"]
    n_sentences: int
    n_grounded: int
    n_framed: int
    n_projected: int
    has_projection: bool
    recommendation: str | None


class MeasureResult(TypedDict, total=False):
    """Top-level measure() output.

    Layers without source material return ``None`` for the layer key.
    """

    structural_profile: StructuralProfile
    claim_density: ClaimDensity
    temporal_instability: TemporalInstability | None
    source_matching: SourceMatching | None
    entity_provenance: EntityProvenance | None
    vocabulary_proximity: VocabularyProximity | None
    presentation_features: PresentationFeatures
    epistemic_calibration: EpistemicCalibration | None
    information_novelty: InformationNovelty
    quality_profile: QualityProfile
    grounding_decomposition: GroundingDecomposition | None
    standard_version: str
    library_version: str


# -- Specification compliance (Standard Section 6) -------------------------


RequirementType = Literal[
    "TOPIC",
    "IMPERATIVE",
    "CONSTRAINT",
    "FORMAT",
    "STRUCTURAL_LABEL",
    "QUALITY_CRITERION",
    "META_INSTRUCTION",
    "BEHAVIORAL",
]


CoverageStatus = Literal["ADDRESSED", "PARTIAL", "MISSING", "UNVERIFIABLE"]


class Requirement(TypedDict):
    text: str
    type: RequirementType
    extraction_method: str


class CoverageEntry(TypedDict, total=False):
    requirement: Requirement
    status: CoverageStatus
    score: float
    matched_section: str | None
    semantic_upgraded: bool
    substance_warning: bool


class DriftSection(TypedDict):
    section_text: str
    section_index: int
    keyword_overlap_with_spec: float
    semantic_similarity: float | None


class AlignSummary(TypedDict):
    coverage_rate: float
    concrete_coverage_rate: float
    structural_compliance_rate: float
    n_unverifiable: int
    n_total: int
    n_addressed: int
    n_partial: int
    n_missing: int
    n_output_words: int
    n_total_sections: int
    n_drifted_sections: int


class AlignResult(TypedDict, total=False):
    """Top-level align() output."""

    requirements: list[Requirement]
    coverage: list[CoverageEntry]
    drift: list[DriftSection]
    emphasis_correlation: float
    summary: AlignSummary
    semantic_used: bool
    standard_version: str
    library_version: str


# -- Combined profile ------------------------------------------------------


class CombinedProfile(TypedDict, total=False):
    """profile() output combining measure and align."""

    quality: MeasureResult
    alignment: AlignResult
    combined_summary: dict[str, float]
    standard_version: str
    library_version: str
