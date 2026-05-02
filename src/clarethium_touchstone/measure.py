"""Output measurement (Touchstone Standard Section 5).

Reference implementation of the eleven measurement layers.

This module provides:

* ``measure()`` - top-level function returning a full ``MeasureResult``
* Individual layer functions for callers needing a specific measurement

All layers operate without invoking AI models on the output, with the
exception of Layer 1a (heading defaultness) which OPTIONALLY uses an
LLM API for baseline generation.

Implementation status: progressive extraction in progress.

* Layer 2 (``claim_density``): IMPLEMENTED
* Layer 4 (``source_matching``): IMPLEMENTED
* All other layers: skeleton, raises ``NotImplementedError``

See Appendix C of the Standard for layer-by-layer status.
"""

from __future__ import annotations

import re
from typing import Literal

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
    UnsourcedNumber,
    VocabularyProximity,
)

# ---------------------------------------------------------------------------
# Internal helpers shared across measurement layers
# ---------------------------------------------------------------------------

# Numbers within this range are treated as years rather than data values.
# Sourced from the operator's research vault; do not adjust without a
# Standard update per Section 10.
_YEAR_RANGE = (1990, 2035)


def _is_year(val: str) -> bool:
    """Return True when ``val`` parses as an integer in the year range."""
    try:
        n = int(val)
    except ValueError:
        return False
    return _YEAR_RANGE[0] <= n <= _YEAR_RANGE[1]


def _is_word_count(num: dict[str, str], text: str) -> bool:
    """Return True when ``num`` appears in a word-count context.

    Word-count callouts (e.g. "Total words: 1,247") are not data-bearing
    numerical claims and must be filtered out before source matching.
    """
    for m in re.finditer(re.escape(num["raw"]), text):
        start = max(0, m.start() - 60)
        context = text[start : m.end() + 20].lower()
        if "word count" in context or "total words" in context:
            return True
    return False


def _add_commas(val: str) -> str | None:
    """Insert thousands separators into a plain integer string.

    ``"2000"`` becomes ``"2,000"``. Returns ``None`` for short integers
    or non-integer strings (decimals are handled separately).
    """
    if "." in val or len(val) <= 3:
        return None
    try:
        return f"{int(val):,}"
    except ValueError:
        return None


# Regex patterns for digit-formatted numerical claims, in priority order.
# Higher-priority patterns claim character ranges first, preventing decimal
# and integer patterns from extracting sub-tokens of already-captured
# percentages or dollar amounts (e.g. "2.58%" must not yield phantom "2.5").
_NUMBER_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(\d+(?:\.\d+)?)\s*%", "percentage"),
    (r"\$(\d+(?:\.\d+)?(?:,\d{3})*)", "dollar"),
    (
        r"\$(\d+(?:\.\d+)?(?:,\d{3})*)\s*[-–]\s*\$?(\d+(?:\.\d+)?(?:,\d{3})*)\s*"
        r"([MBKmillion|billion|thousand]*)",
        "dollar_range",
    ),
    (r"(\d+(?:\.\d+)?)[xX]\b", "multiplier"),
    (r"(?<!\$)(?<!\d)(\d+\.\d+)(?!%)", "decimal"),
    (
        r"(?<!\$)(?<!\d)(?<!\.)(\d{1,3}(?:,\d{3})+)(?!\.\d)(?!%)(?!\d)",
        "integer_comma",
    ),
    (r"(?<!\$)(?<!\d)(?<!\.)(\d+)\s*[MBK]\b", "integer_suffix"),
    (
        r"(?<!\$)(?<!\d)(?<!\.)(\d{2,6})(?!\.\d)(?!%)(?!\d)(?!,\d{3})",
        "integer",
    ),
)


def _extract_numbers_for_matching(text: str) -> list[dict[str, str]]:
    """Extract digit-formatted numbers from ``text`` with type and context.

    Returns a list of dicts with keys ``value`` (canonical string form),
    ``raw`` (the matched substring), ``context`` (50-character window
    around the match), and ``type`` (one of ``percentage``, ``dollar``,
    ``multiplier``, ``decimal``, ``integer``).
    """
    numbers: list[dict[str, str]] = []
    seen: set[tuple[str, str, int]] = set()
    claimed_ranges: list[tuple[int, int]] = []

    for pattern, num_type in _NUMBER_PATTERNS:
        for m in re.finditer(pattern, text):
            match_start, match_end = m.start(), m.end()
            if any(cs <= match_start < ce or cs < match_end <= ce for cs, ce in claimed_ranges):
                continue

            val = m.group(1) if m.lastindex else m.group(0)
            if num_type in ("dollar", "integer_comma", "dollar_range"):
                val = val.replace(",", "")

            effective_type = num_type
            if num_type in ("integer_comma", "integer_suffix"):
                effective_type = "integer"
            elif num_type == "dollar_range":
                effective_type = "dollar"

            key = (val, effective_type, m.start())
            if key in seen:
                continue
            seen.add(key)
            claimed_ranges.append((match_start, match_end))

            ctx_start = max(0, m.start() - 50)
            ctx_end = min(len(text), m.end() + 50)
            context = re.sub(r"\s+", " ", text[ctx_start:ctx_end].strip())
            numbers.append(
                {
                    "value": val,
                    "raw": m.group(0),
                    "context": context,
                    "type": effective_type,
                }
            )
    return numbers


def _filter_numbers(numbers: list[dict[str, str]], text: str) -> list[dict[str, str]]:
    """Drop year-like values and word-count callouts from a number list."""
    return [n for n in numbers if not _is_year(n["value"]) and not _is_word_count(n, text)]


def _number_in_source(num: dict[str, str], source_text: str) -> bool:
    """Return True if ``num`` can be located in ``source_text`` via string match.

    Type-aware: percentages require a trailing ``%``, dollar amounts a
    leading ``$``, multipliers a trailing ``x`` or ``X``. Comma-formatted
    variants are checked alongside raw values.
    """
    val = num["value"]
    ntype = num["type"]

    if ntype == "percentage":
        if re.search(re.escape(val) + r"\s*%", source_text):
            return True
        if "." in val:
            int_val = val.split(".")[0]
            if re.search(re.escape(int_val) + r"\s*%", source_text):
                return True
        return False

    if ntype == "dollar":
        if re.search(r"\$" + re.escape(val), source_text):
            return True
        comma_val = _add_commas(val)
        return bool(comma_val and re.search(r"\$" + re.escape(comma_val), source_text))

    if ntype == "multiplier":
        return bool(re.search(re.escape(val) + r"[xX]", source_text))

    # integer, decimal: try raw, then comma-formatted variant
    if re.search(r"(?<!\d)" + re.escape(val) + r"(?!\d)", source_text):
        return True
    comma_val = _add_commas(val)
    return bool(comma_val and re.search(r"(?<!\d)" + re.escape(comma_val) + r"(?!\d)", source_text))


def _precision_for(total: int) -> Literal["low", "adequate", "good"]:
    """Map total number count to a precision indicator."""
    if total < 10:
        return "low"
    if total < 30:
        return "adequate"
    return "good"


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

# Numerical claim patterns. Recall ~97% on digit-formatted numbers across
# three document types per the operator's research vault. Misses numbers
# expressed as words (e.g. "twenty percent") and relative claims.
_NUMERICAL_CLAIM_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        r"(?:~|approximately |about |roughly |nearly |over |under )?"
        r"(\d+(?:\.\d+)?)\s*%",
        "percentage",
    ),
    (r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*%", "pct_range"),
    (
        r"\$\s*(\d+(?:[.,]\d+)*)\s*(M|B|K|million|billion|thousand|mn|bn)?",
        "dollar",
    ),
    (r"(\d+(?:\.\d+)?)\s*[x×](?:\s|$|,)", "multiplier"),
    (r"(\d+(?:\.\d+)?)\s*-?\s*fold", "multiplier"),
    (
        r"(\d+(?:,\d{3})*)\s+(?:companies|firms|teams|organizations|employees|"
        r"engineers|developers|users|customers|tools|platforms|products|projects|"
        r"systems|failures|incidents|outages|services|applications|repositories|"
        r"modules|microservices|endpoints|APIs?|databases?|clusters?|regions?)",
        "entity_count",
    ),
    (
        r"(\d+(?:\.\d+)?)\s*[-–]?\s*(?:\d+(?:\.\d+)?\s*)?"
        r"(?:days?|weeks?|months?|years?|hours?|minutes?|quarters?|sprints?)",
        "duration",
    ),
)

# Causal language markers. Counted per sentence (a sentence with three
# markers contributes one causal claim, not three).
_CAUSAL_MARKERS: tuple[str, ...] = (
    r"\bbecause\b",
    r"\bsince\b(?!\s+\d)",
    r"\bdue to\b",
    r"\bowing to\b",
    r"\bas a result of\b",
    r"\bcaused? by\b",
    r"\bdriven by\b",
    r"\bleads? to\b",
    r"\bresults? in\b",
    r"\bcauses?\b",
    r"\bproduces?\b",
    r"\bgenerates?\b",
    r"\btriggers?\b",
    r"\bconsequently\b",
    r"\btherefore\b",
    r"\bthus\b",
    r"\bhence\b",
    r"\bthe (?:primary|main|key|root|fundamental|core|underlying|central) "
    r"(?:cause|reason|driver|factor|mechanism|force)\b",
    r"\b(?:directly|indirectly) (?:causes?|leads? to|results? in|drives?)\b",
    r"\bis responsible for\b",
    r"\baccounts? for\b",
    r"\benables?\b",
    r"\bprevents?\b",
    r"\binhibits?\b",
    r"\bfacilitates?\b",
    r"\bexacerbates?\b",
    r"\bcompounds?\b(?:\s+the)",
    r"\bamplifies?\b",
    r"\breinforces?\b",
    r"\bundermines?\b",
    r"\berodes?\b",
)

_CAUSAL_COMBINED = "|".join(_CAUSAL_MARKERS)


def _split_sentences(text: str) -> list[tuple[str, str, int]]:
    """Split markdown into ``(heading, sentence, paragraph_index)`` tuples.

    Strips list markers, splits on sentence boundaries, drops sentences
    shorter than 30 characters. Heading state is carried forward across
    paragraphs until a new heading line is encountered.
    """
    results: list[tuple[str, str, int]] = []
    current_heading = ""
    para_idx = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            current_heading = re.sub(r"^#+\s*", "", stripped)
            continue
        cleaned = re.sub(r"^[-*•]\s+", "", stripped)
        cleaned = re.sub(r"^\d+\.\s+", "", cleaned)
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", cleaned)
        for sent in parts:
            sent = sent.strip()
            if len(sent) > 30:
                results.append((current_heading, sent, para_idx))
        para_idx += 1
    return results


def _count_numerical_claim_sentences(text: str) -> int:
    """Count sentences containing at least one digit-formatted number."""
    n = 0
    for _heading, sent, _pos in _split_sentences(text):
        for pattern, _num_type in _NUMERICAL_CLAIM_PATTERNS:
            if re.search(pattern, sent, re.IGNORECASE):
                n += 1
                break
    return n


def _count_causal_claim_sentences(text: str) -> int:
    """Count sentences containing at least one causal-language marker."""
    n = 0
    for _heading, sent, _pos in _split_sentences(text):
        if re.search(_CAUSAL_COMBINED, sent, re.IGNORECASE):
            n += 1
    return n


def claim_density(text: str) -> ClaimDensity:
    """Layer 2: numerical and causal claim counts per 1000 words.

    Counts sentences (not raw markers) so a sentence with multiple
    markers contributes a single claim. Word count uses simple ``\\w+``
    tokenisation. Density is per 1000 words with a floor of 0.1k to
    avoid division by zero on very short inputs.
    """
    n_words = len(re.findall(r"\b\w+\b", text))
    n_numerical = _count_numerical_claim_sentences(text)
    n_causal = _count_causal_claim_sentences(text)

    k_words = max(n_words / 1000, 0.1)
    return {
        "numerical_per_1kw": round(n_numerical / k_words, 1),
        "causal_per_1kw": round(n_causal / k_words, 1),
        "n_numerical": n_numerical,
        "n_causal": n_causal,
        "n_words": n_words,
    }


# -- Layer 3: Temporal instability ----------------------------------------


def temporal_instability(text: str, comparisons: list[str]) -> TemporalInstability:
    """Layer 3: instability rate of digit-formatted numbers across versions."""
    raise NotImplementedError


# Deprecated alias, removed in v2.0
fabrication_rate = temporal_instability


# -- Layer 4: Source matching ---------------------------------------------


def source_matching(text: str, source: str) -> SourceMatching:
    """Layer 4: source fidelity for digit-formatted numbers.

    Extracts digit-formatted numerical claims (percentages, dollar amounts,
    multipliers, decimals, integers) from ``text`` and verifies each via
    type-aware string search against ``source``. Reports the unsourced
    rate, in/out counts, precision indicator, and per-claim details for
    every number not found in the source.

    Note: Layer 4 measures source fidelity (presence of emitted numbers in
    source material), not fabrication directly. A correctly derived number
    (e.g. gross profit computed from sourced components) is flagged as
    unsourced because the literal string is not in the source. See
    Standard Section 5.4 and the methodology paper for the construct
    honesty discussion.

    Args:
        text: The output to verify.
        source: Source material the output may reference.

    Returns:
        A ``SourceMatching`` dict with ``unsourced_rate``, ``n_in_source``,
        ``n_unsourced``, ``n_total``, ``precision``, and a list of
        ``unsourced_details`` describing each claim not found in source.

    Validated: 0/309 false positives across 5 self-source files
    (document=source). 97.1% recall on digit-formatted numbers across
    70 manually annotated claims (3 documents, 6 categories).
    """
    numbers = _filter_numbers(_extract_numbers_for_matching(text), text)

    in_source: list[dict[str, str]] = []
    not_in_source: list[dict[str, str]] = []

    for num in numbers:
        if _number_in_source(num, source):
            in_source.append(num)
        else:
            not_in_source.append(num)

    total = len(in_source) + len(not_in_source)
    unsourced_rate = len(not_in_source) / total if total > 0 else 0.0

    unsourced_details: list[UnsourcedNumber] = [
        {"value": n["value"], "type": n["type"], "context": n["context"]} for n in not_in_source
    ]

    return {
        "unsourced_rate": round(unsourced_rate, 3),
        "n_in_source": len(in_source),
        "n_unsourced": len(not_in_source),
        "n_total": total,
        "precision": _precision_for(total),
        "unsourced_details": unsourced_details,
    }


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
