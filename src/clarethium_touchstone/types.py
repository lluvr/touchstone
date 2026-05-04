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


class _UnsourcedNumberBase(TypedDict):
    """Required fields for UnsourcedNumber (always populated)."""

    value: str
    type: str
    context: str


class UnsourcedNumber(_UnsourcedNumberBase, total=False):
    """A digit-formatted number from the output not found in the source.

    Required fields (always populated): ``value``, ``type``, ``context``.

    Optional ``currency`` field populated for ``dollar``-type numbers,
    holding the matched currency symbol (one of ``$ € £ ¥ ₹``).
    Absent on non-currency types.

    The base/extension split (3.10-compatible alternative to
    ``NotRequired``) keeps the required fields enforced by type checkers
    while allowing currency to be conditionally present.
    """

    currency: str


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


DerivationRegime = Literal["diagnostic", "transition", "saturated"]


class ScopeAssessment(TypedDict):
    """Layer 11 derivation-checker scope classification.

    The derivation checker (``_gfp_is_derivable``) saturates as the
    source's unique-number count grows. At N≥10 source numbers, false-
    positive rate approaches 100%. The scope_assessment field tells
    consumers which P-signal to trust on a given source.

    Boundaries (vault-validated, methodology-doc-aligned):
    - ``diagnostic``: source_num_count < 5 — primary unsourced_numbers
      signal is reliable
    - ``transition``: 5 ≤ source_num_count < 10 — derivation-checker FPR
      is 50–97%; cross-reference Layer 4 source_matching
    - ``saturated``: source_num_count ≥ 10 — primary signal is
      effectively disabled; P falls back to entity / year secondary
      signals; trust Layer 4 for numerical fabrication
    """

    source_num_count: int
    derivation_regime: DerivationRegime
    primary_signal_diagnostic: bool
    cross_reference_layer_4_for_numbers: bool
    note_developer: str
    note_user_facing: str


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
    scope_assessment: ScopeAssessment


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


# Standard Section 6 (Specification Compliance) types and the
# ``CombinedProfile`` are reserved for a future release. They were
# present in pre-v0.1 stubs but are removed until alignment is properly
# implemented (a band-aid TypedDict ahead of implementation calcifies
# decisions that should be made once code exists). See ``CHANGELOG.md``
# entry for v0.1 scope.
