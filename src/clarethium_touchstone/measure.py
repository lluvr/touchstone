"""Output measurement (Touchstone Standard Section 5).

Reference implementation of the eleven measurement layers.

This module provides:

* ``measure()`` - top-level function returning a full ``MeasureResult``
* Individual layer functions for callers needing a specific measurement

All layers operate without invoking AI models on the output, with the
exception of Layer 1a (heading defaultness) which OPTIONALLY uses an
LLM API for baseline generation.

Implementation status: progressive extraction in progress.

* Layer 1 (``structural_profile``): IMPLEMENTED (1b, 1c; 1a returns None)
* Layer 2 (``claim_density``): IMPLEMENTED
* Layer 4 (``source_matching``): IMPLEMENTED
* Layer 5 (``entity_provenance``): IMPLEMENTED (directional in v1.0)
* Layer 6 (``vocabulary_proximity``): IMPLEMENTED (directional in v1.0)
* Layer 7 (``presentation_features``): IMPLEMENTED
* Layer 9 (``information_novelty``): IMPLEMENTED (experimental in v1.0)
* Layer 10 (``quality_profile``): IMPLEMENTED (substance from L4 + L5,
  presentation from L7; temporal_stability / epistemic_calibration /
  structural_effort reserved for future layers)
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

# Layer 1b: causal-reasoning markers vs filler/buzzword markers.
_MECHANISM_PATTERNS: tuple[str, ...] = (
    r"\bbecause\b",
    r"\bcauses\b",
    r"\bleads?\s+to\b",
    r"\bresults?\s+in\b",
    r"\bdue\s+to\b",
    r"\bdriven\s+by\b",
    r"\bmediated\s+by\b",
    r"\bthrough\s+the\s+mechanism\b",
    r"\bcontributes?\s+to\b",
    r"\bstems?\s+from\b",
    r"\bconsequently\b",
    r"\btherefore\b",
    r"\bthus\b",
    r"\bcreates?\s+(?:a|an|the)\b",
    r"\bprevents?\s+(?:a|an|the|this|that)\b",
    r"\bundermines?\b",
    r"\breinforces?\b",
    r"\bexacerbates?\b",
    r"\btriggers?\b",
    r"\breduces?\s+(?:a|an|the|this|that)\b",
    r"\bincreases?\s+(?:a|an|the|this|that)\b",
    r"\bdepends?\s+on\b",
    r"\bin\s+response\s+to\b",
)

_BUZZWORD_PATTERNS: tuple[str, ...] = (
    r"\bfundamentally\b",
    r"\binherently\b",
    r"\bexponentially\b",
    r"\btransformative\b",
    r"\bparadigm\b",
    r"\bsynerg(?:y|istic)\b",
    r"\bholistically\b",
    (
        r"\bleverage\b(?=\s+(?:the|this|that|our|their|your|its|a|an|"
        r"existing|new|current|available|key|core|unique|critical|"
        r"strategic|digital|modern|data|technology|AI|cloud))"
    ),
    r"\bosmosis\b",
    r"\bseamlessly\b",
    r"\brobust\b(?=\s+(?:framework|solution|approach|system))",
    r"\bcomprehensive\b(?=\s+(?:framework|solution|approach|strategy))",
    r"\bcritical(?:ly)?\s+important\b",
    r"\bgame.?changer\b",
    r"\bpivotal\b",
)

_MECH_RE = re.compile("|".join(_MECHANISM_PATTERNS), re.IGNORECASE)
_BUZZ_RE = re.compile("|".join(_BUZZWORD_PATTERNS), re.IGNORECASE)


def _mechanism_ratio(text: str) -> float:
    """Layer 1b: causal-reasoning markers / (causal + buzzword) markers.

    Construct: ratio of mechanism language to filler/buzzword language.
    Measures reasoning STYLE, not reasoning quality. Returns 0.0 when
    no markers of either kind are present.
    """
    mech = len(_MECH_RE.findall(text))
    buzz = len(_BUZZ_RE.findall(text))
    total = mech + buzz
    if total == 0:
        return 0.0
    return round(mech / total, 4)


# Layer 1c: epistemic register patterns. Five categories.
_REGISTER_PATTERNS: dict[str, tuple[str, ...]] = {
    "ASSERTION": (
        r"\bmust\b",
        r"\balways\b",
        r"\bnever\b",
        r"\bundeniably\b",
        r"\bclearly\b",
        r"\bobviously\b",
        r"\bensures?\b",
        r"\bguarantees?\b",
        r"\brequires?\b",
        r"\bwill\s+(?:lead|result|cause|create|produce)\b",
        r"\bis\s+essential\b",
        r"\bis\s+critical\b",
        r"\bis\s+(?:the\s+)?key\b",
    ),
    "QUALIFIED": (
        r"\btends?\s+to\b",
        r"\bin\s+many\s+cases\b",
        r"\bevidence\s+suggests?\b",
        r"\boften\b",
        r"\btypically\b",
        r"\bgenerally\b",
        r"\busually\b",
        r"\bfrequently\b",
        r"\bcan\s+(?:lead|result|cause|help)\b",
        r"\bmay\s+(?:lead|result|cause|help|be|not)\b",
        r"\blikely\b",
        r"\bprobably\b",
    ),
    "CONDITIONAL": (
        r"\bwhen\s+\w+\s+(?:is|are|do|does|have|has)\b",
        r"\bif\s+(?:the|this|a|an|these|those)\b",
        r"\bdepending\s+on\b",
        r"\bassuming\b",
        r"\bin\s+(?:cases|situations|contexts)\s+where\b",
        r"\bprovided\s+that\b",
        r"\bunder\s+(?:conditions|circumstances)\b",
        r"\bwhether\b",
    ),
    "EVIDENCED": (
        r"\bstudies?\s+(?:show|indicate|suggest|find|found|demonstrate)\b",
        r"\bresearch\s+(?:show|indicate|suggest|find|found|demonstrate)s?\b",
        r"\bdata\s+(?:show|indicate|suggest|reveal)s?\b",
        r"\baccording\s+to\b",
        r"\bempirical(?:ly)?\b",
        r"\bobserved\b",
        r"\bmeasured\b",
        r"\bevidence\s+(?:from|shows?|indicates?|suggests?)\b",
    ),
    "SPECULATIVE": (
        r"\bmight\b",
        r"\bcould\s+(?:be|lead|result|have|create|potentially)\b",
        r"\bpossibly\b",
        r"\bperhaps\b",
        r"\bremains?\s+to\s+be\s+seen\b",
        r"\bit\s+is\s+(?:possible|plausible|conceivable)\b",
        r"\bspeculat(?:e|ive|ion)\b",
        r"\bhypothes(?:is|ize|etical)\b",
    ),
}

_REG_COMPILED: dict[str, re.Pattern[str]] = {
    register: re.compile("|".join(patterns), re.IGNORECASE)
    for register, patterns in _REGISTER_PATTERNS.items()
}

# Below this match count, the assertion ratio is unreliable.
_MIN_RELIABLE_REGISTER_MATCHES = 10


def _extract_section_bodies(text: str) -> list[str]:
    """Return the body text under each ``##`` / ``###`` heading.

    Excludes the headings themselves. Returns an empty list when the
    text contains no level-2/3 markdown headings.
    """
    sections: list[str] = []
    current_heading: str | None = None
    current_body: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            if current_heading is not None:
                sections.append("\n".join(current_body).strip())
            current_heading = stripped
            current_body = []
        elif current_heading is not None:
            current_body.append(line)
    if current_heading is not None:
        sections.append("\n".join(current_body).strip())
    return sections


def _assertion_ratio(text: str) -> tuple[float, Literal["adequate", "low"]]:
    """Layer 1c: assertion register fraction of total epistemic-register matches.

    Counts five register categories: ASSERTION, QUALIFIED, CONDITIONAL,
    EVIDENCED, SPECULATIVE. Returns the fraction of matches in the
    ASSERTION category, plus a precision indicator ("adequate" if the
    total match count meets the reliability threshold of 10, otherwise
    "low").

    Operates on section bodies when level-2/3 headings are present
    (preferred mode, validated). Falls back to full text otherwise.
    Returns (0.0, "low") when no register markers are found.
    """
    section_bodies = _extract_section_bodies(text)
    body_text = "\n".join(section_bodies) if section_bodies else text

    counts = {
        register: len(compiled.findall(body_text)) for register, compiled in _REG_COMPILED.items()
    }
    total = sum(counts.values())

    if total == 0:
        return 0.0, "low"

    ratio = counts["ASSERTION"] / total
    precision: Literal["adequate", "low"] = (
        "adequate" if total >= _MIN_RELIABLE_REGISTER_MATCHES else "low"
    )
    return round(ratio, 4), precision


def structural_profile(text: str, *, topic: str | None = None) -> StructuralProfile:
    """Layer 1: structural profile (1a heading defaultness, 1b mechanism
    ratio, 1c assertion ratio).

    Layer 1a (``heading_defaultness``) requires both a ``topic`` argument
    and an LLM-API integration to generate baseline documents. The
    integration is not yet wired in this build, so 1a always returns
    ``None`` even when a topic is supplied. 1b and 1c run on any text.

    Args:
        text: The output to measure.
        topic: Optional topic string for 1a baseline generation
            (currently inert; reserved for the LLM-API integration).

    Returns:
        A ``StructuralProfile`` with ``heading_defaultness`` (None until
        1a is wired), ``mechanism_ratio``, ``assertion_ratio``, and
        ``assertion_precision``.
    """
    del topic  # Reserved for Layer 1a; not used until LLM API is wired.
    ratio, precision = _assertion_ratio(text)
    return {
        "heading_defaultness": None,
        "mechanism_ratio": _mechanism_ratio(text),
        "assertion_ratio": ratio,
        "assertion_precision": precision,
    }


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

# Entities are deduplicated as (type, value) pairs so the same string
# captured under two different patterns counts as two entries.


def _extract_entities(text: str) -> list[dict[str, str]]:
    """Extract named entities via five regex patterns.

    Patterns (vault-faithful):

    1. Person names following a triggering prefix (``'s ``, ``according
       to``, ``by ``, comma, em-dash, period). Bare "FirstName LastName"
       without a prefix does NOT match. Common nouns ("source",
       "extends", "mechanism", "falsifier", "section") that look like
       names are filtered out.
    2. Organisations: Title Case word(s) followed by an org suffix
       (Labs, Corp, Inc, Foundation, University, Institute, Survey,
       Report, Association, Group, Research).
    3. Attributions: ``according to``, ``per``, ``cited by``,
       ``reported by`` followed by a Title Case name.
    4. Parenthetical citations: ``(Author, YYYY)`` form.
    5. CamelCase organisation names (e.g., ``OpenAI``, ``GitHub``).

    Headings (``# ...``) and table rows (``|...|``) are stripped before
    extraction to avoid false matches in chrome.

    Returns a list of dicts with ``type``, ``value``, and ``context``
    keys.
    """
    body = re.sub(r"^#{1,6}\s+.*$", "", text, flags=re.MULTILINE)
    body = re.sub(r"\|[^\n]+\|", "", body)

    entities: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _push(entity_type: str, value: str, start: int, end: int) -> None:
        key = (entity_type, value)
        if key in seen:
            return
        seen.add(key)
        ctx_start = max(0, start - 20)
        ctx_end = min(len(body), end + 30)
        entities.append(
            {
                "type": entity_type,
                "value": value,
                "context": body[ctx_start:ctx_end].strip(),
            }
        )

    # Pattern 1: Person names with triggering prefix. The prefix list
    # avoids falsely catching mid-sentence Title Case noun phrases.
    person_pattern = (
        r"(?:(?:['s]\s+)|(?:according to\s+)|(?:by\s+)|(?:,\s+)"
        r"|(?:—\s*)|(?:\.\s+))"
        r"([A-Z][a-z]{2,15}\s+(?:[A-Z]\.?\s+)?[A-Z][a-z]{2,15})"
    )
    person_blocklist = ("source", "extends", "mechanism", "falsifier", "section")
    for m in re.finditer(person_pattern, body):
        name = m.group(1).strip()
        name_lower = name.lower()
        if any(w in name_lower for w in person_blocklist):
            continue
        _push("PERSON", name, m.start(), m.end())

    # Pattern 2: Organisations with explicit suffix.
    org_pattern = (
        r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*"
        r"(?:\s+(?:Labs|Corp|Inc|Foundation|University|Institute"
        r"|Survey|Report|Association|Group|Research)))"
    )
    for m in re.finditer(org_pattern, body):
        _push("ORG", m.group(1).strip(), m.start(), m.end())

    # Pattern 3: Attributions.
    attribution_pattern = (
        r"(?:according to|per|cited by|reported by)\s+"
        r"([A-Z][a-zA-Z]+(?:[\s/][A-Z]?[a-zA-Z]+){0,4})"
    )
    attribution_blocklist = ("source", "the", "this", "one")
    for m in re.finditer(attribution_pattern, body):
        name = m.group(1).strip()
        if name.lower() in attribution_blocklist:
            continue
        _push("ATTRIBUTED", name, m.start(), m.end())

    # Pattern 4: Parenthetical citations.
    citation_pattern = r"\(([A-Z][a-zA-Z/]+(?:\s+[A-Z]?[a-zA-Z]+)*)[,\s]+(\d{4})\)"
    for m in re.finditer(citation_pattern, body):
        cite = f"{m.group(1)} {m.group(2)}"
        if "source" in cite.lower():
            continue
        _push("CITATION", cite, m.start(), m.end())

    # Pattern 5: CamelCase organisation names.
    camel_pattern = r"(?<!\w)([A-Z][a-z]+[A-Z][a-zA-Z]+)(?!\w)"
    for m in re.finditer(camel_pattern, body):
        # Note: the keyed type is ORG (vault uses ORG_CAMEL only as the
        # internal dedup key; the public type is ORG).
        name = m.group(1)
        key = ("ORG_CAMEL", name)
        if key in seen:
            continue
        seen.add(key)
        ctx_start = max(0, m.start() - 20)
        ctx_end = min(len(body), m.end() + 30)
        entities.append(
            {
                "type": "ORG",
                "value": name,
                "context": body[ctx_start:ctx_end].strip(),
            }
        )

    return entities


def _entity_in_source(entity: dict[str, str], source_text: str) -> bool:
    """Check whether ``entity['value']`` appears in source.

    Two-pass match (vault-faithful):

    1. Whole-string lowercase substring search (``cat`` matches
       ``catalog``, mirroring Layer 6's generosity).
    2. Word-by-word fallback: all content words (>3 chars, not stop
       words) of the entity value must each be present in source.
    """
    val = entity["value"]
    source_lower = source_text.lower()
    if val.lower() in source_lower:
        return True
    words = [w for w in val.split() if len(w) > 3 and w.lower() not in _STOP_WORDS]
    return bool(words) and all(w.lower() in source_lower for w in words)


def entity_provenance(text: str, source: str) -> EntityProvenance:
    """Layer 5 (DIRECTIONAL in v1.0): named-entity provenance.

    Extracts named entities (persons, organisations, attributions,
    citations) from ``text`` via five regex patterns and reports the
    fraction not found in ``source``.

    English-centric patterns; non-English names with non-ASCII
    characters often miss. Substring matching against source is
    generous (vault-faithful) — see ``_entity_in_source``.

    Output:

    * ``entity_unsourced_rate`` — fraction of extracted entities not
      found in source. ``0.0`` when no entities extract.
    * ``n_entities`` — total entities extracted (deduplicated).
    * ``n_unsourced`` — number not found in source.
    * ``unsourced_entities`` — list of entity values not in source
      (strings only; type/context dropped from public output).
    """
    entities = _extract_entities(text)
    not_in_source = [e for e in entities if not _entity_in_source(e, source)]

    total = len(entities)
    unsourced_rate = len(not_in_source) / total if total > 0 else 0.0

    return {
        "entity_unsourced_rate": round(unsourced_rate, 3),
        "n_entities": total,
        "n_unsourced": len(not_in_source),
        "unsourced_entities": [e["value"] for e in not_in_source],
    }


# -- Layer 6: Vocabulary proximity ----------------------------------------


def vocabulary_proximity(text: str, source: str) -> VocabularyProximity:
    """Layer 6 (DIRECTIONAL in v1.0): per-sentence content-word overlap
    with source.

    For each qualifying sentence in ``text``, computes the fraction of
    content words present (as substrings) in the lowercased source.
    Returns the mean across sentences and the raw per-sentence scores.

    Construct: how much of the generated vocabulary comes from source
    material? High = close paraphrase or summary; low = novel
    vocabulary, which can be original analysis (desirable) or
    fabricated content (undesirable). Layer 6 alone cannot
    distinguish; consult Layers 4-5 for fabrication detection.

    Vault behaviour preserved: word-in-source check is a substring
    match (``w in source_lower``), so a content word ``cat`` is
    considered present if the source contains ``catalog``. This is
    generous and intentional — surfaces lexical overlap without
    requiring exact tokenisation parity.

    Output:

    * ``mean_proximity`` — mean across qualifying sentences. 0.0 when
      no sentence qualifies.
    * ``per_sentence_proximity`` — raw per-sentence scores (rounded to
      3 decimals for storage parity with the mean).
    """
    sentences = _split_sentences_simple(text)
    source_lower = source.lower()

    scores: list[float] = []
    for sent in sentences:
        sent_words = _content_words(sent)
        if not sent_words:
            continue
        grounded = sum(1 for w in sent_words if w in source_lower)
        scores.append(grounded / len(sent_words))

    if not scores:
        return {"mean_proximity": 0.0, "per_sentence_proximity": []}

    mean_proximity = sum(scores) / len(scores)
    return {
        "mean_proximity": round(mean_proximity, 3),
        "per_sentence_proximity": [round(s, 3) for s in scores],
    }


# -- Layer 7: Presentation features ---------------------------------------

# Hedging language (low confidence registers).
_HEDGE_RE = re.compile(
    r"\b(?:perhaps|maybe|possibly|might|could|seems?|appears?|"
    r"suggest(?:s|ed|ing)?|indicate(?:s|d)?|tend(?:s|ed)?|"
    r"somewhat|relatively|generally|often|usually|typically|"
    r"in some cases|to some extent|it (?:is|seems) (?:possible|likely))\b",
    re.IGNORECASE,
)

# Assertive language (high confidence registers). Distinct from Layer 1c
# REGISTER_PATTERNS["ASSERTION"]; this set is wider and includes
# rhetorical-named-cause patterns ("the key issue", "the root mechanism").
_ASSERT_RE = re.compile(
    r"\b(?:always|never|must|requires?|demands?|guarantees?|ensures?|"
    r"proves?|demonstrates?|establishes?|confirms?|definitively|"
    r"inevitably|invariably|necessarily|fundamentally|critically|"
    r"the (?:key|core|essential|primary|fundamental|root|central) "
    r"(?:issue|problem|cause|reason|driver|mechanism|factor))\b",
    re.IGNORECASE,
)

# Named-concept patterns: "Title Case Word(s) + <Concept Noun>"
# (e.g., "Sunk Cost Fallacy", "Streetlight Effect", "Dunning-Kruger Effect").
_NAMING_RE = re.compile(
    r"(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s*"
    r"(?:Effect|Trap|Paradox|Principle|Syndrome|Pattern|Loop|Cycle|"
    r"Model|Framework|Law|Rule|Fallacy|Bias|Gap|Problem|Phenomenon|"
    r"Spiral|Ceiling|Floor|Threshold))"
)


def _count_syllables(word: str) -> int:
    """Approximate syllable count for Flesch-Kincaid grade level.

    Standard heuristic: count vowel transitions, drop a trailing silent
    'e' (unless it would zero the count). Words of three letters or
    fewer count as one syllable. Returns at least 1 for any non-empty
    alphabetic word.
    """
    word = word.lower().strip()
    if len(word) <= 3:
        return 1
    count = 0
    prev_vowel = False
    for char in word:
        is_vowel = char in "aeiouy"
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def _strip_markdown(text: str) -> str:
    """Strip markdown markers (headings, bold, italic, code, link syntax).

    Used as the cleaning pass for tokenisation and sentence splitting in
    Layer 7. Heading markers and emphasis are removed; link text is
    preserved while URL targets are dropped.
    """
    text = re.sub(r"#{1,6}\s+", "", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def _tokenize_words(text: str) -> list[str]:
    """Lowercased alphabetic words (with internal apostrophes).

    Strips markdown first, then extracts ``[a-zA-Z']+`` runs. Numerical
    tokens are excluded by design — Layer 7 measures language registers
    and lexical diversity, not numerical content.
    """
    return re.findall(r"[a-zA-Z']+", _strip_markdown(text).lower())


def _split_sentences_simple(text: str) -> list[str]:
    """Split markdown into sentences for register / FK analysis.

    Drops table rows (``|...|``), heading markers, emphasis, and link
    syntax. Keeps sentences with at least 5 tokens that don't mention
    "word count".
    """
    clean = re.sub(r"#{1,6}\s+", "", text)
    clean = re.sub(r"\|[^\n]+\|", "", clean)
    clean = re.sub(r"\*+", "", clean)
    clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    return [
        s.strip()
        for s in sentences
        if len(s.strip().split()) >= 5 and "word count" not in s.lower()
    ]


def _extract_headings_simple(text: str) -> list[str]:
    """Return ## and ### heading text (cleaned of markdown markers)."""
    headings: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("## ") or line.startswith("### "):
            h = re.sub(r"^#+\s*", "", line).strip()
            h = re.sub(r"\*+", "", h).strip()
            if h:
                headings.append(h)
    return headings


def presentation_features(text: str) -> PresentationFeatures:
    """Layer 7: surface presentation characteristics.

    Returns five descriptive features. None of them are evaluative on
    their own; they describe the SHAPE of the prose (vocabulary
    diversity, reading level, formatting intensity, register stance,
    rhetorical naming) and are inputs to Layer 10's substance vs
    presentation gap.

    Components:

    * ``type_token_ratio`` — unique words / total words. Higher = more
      lexical diversity.
    * ``fk_grade`` — Flesch-Kincaid grade level (US schooling years).
      0.0 for empty input.
    * ``formatting_density`` — (bold runs + list items + headings) per
      100 words. High values indicate heavy markdown formatting.
    * ``assertiveness_ratio`` — assertive markers / (assertive +
      hedging markers). 0.5 default when neither register fires.
    * ``named_concept_count`` — count of "Title Case <Concept Noun>"
      patterns (e.g., "Sunk Cost Fallacy"). Proxy for rhetorical
      authority signalling.
    """
    words = _tokenize_words(text)
    sents = _split_sentences_simple(text)
    headings = _extract_headings_simple(text)

    n_words = len(words)
    ttr = len(set(words)) / n_words if n_words > 0 else 0.0

    n_sents = max(len(sents), 1)
    syllable_counts = [_count_syllables(w) for w in words if w.isalpha()]
    total_syllables = sum(syllable_counts)
    if n_words > 0:
        fk_grade = 0.39 * (n_words / n_sents) + 11.8 * (total_syllables / n_words) - 15.59
    else:
        fk_grade = 0.0

    n_bold = len(re.findall(r"\*\*[^*]+\*\*", text))
    n_list_items = len(re.findall(r"^[-*•]\s+", text, re.MULTILINE))
    n_list_items += len(re.findall(r"^\d+\.\s+", text, re.MULTILINE))
    formatting_density = (n_bold + n_list_items + len(headings)) / max(n_words / 100, 1)

    n_hedges = len(_HEDGE_RE.findall(text))
    n_asserts = len(_ASSERT_RE.findall(text))
    total_register = n_asserts + n_hedges
    assertiveness = n_asserts / total_register if total_register > 0 else 0.5

    named_concepts = _NAMING_RE.findall(text)

    return {
        "type_token_ratio": round(ttr, 4),
        "fk_grade": round(fk_grade, 1),
        "formatting_density": round(formatting_density, 2),
        "assertiveness_ratio": round(assertiveness, 4),
        "named_concept_count": len(named_concepts),
    }


# -- Layer 8: Epistemic calibration ---------------------------------------


def epistemic_calibration(text: str, source: str) -> EpistemicCalibration:
    """Layer 8 (experimental): grounded assertions / total assertions."""
    raise NotImplementedError


# -- Layer 9: Information novelty -----------------------------------------

# Stop words shared across the lexical layers (currently Layer 9; Layer 6
# will reuse when extracted). Removing high-frequency function words keeps
# the novelty signal focused on content vocabulary.
_STOP_WORDS: frozenset[str] = frozenset(
    # split-string form is intentionally more readable than a flat list
    # literal of ~100 short tokens; runs once at module load.
    """
    a an the and or but if in on at to for of with by from as is are was were
    be been being have has had do does did will would shall should can could
    may might must need not no nor so yet also just only even still already
    than then that this these those it its he she they them their his her we
    our you your i me my which what when where who whom how why all each
    every any some most more less much many few several both either neither
    into onto upon about above below between through during before after
    since until while however therefore moreover furthermore although because
    versus via per etc vs often very quite rather too such like
    """.split()  # noqa: SIM905
)


def _content_words(text: str) -> list[str]:
    """Return lowercase content words (3+ alphabetic chars, no stop words).

    Used by Layer 9 (cumulative-vocabulary novelty). Numerals are
    excluded by the ``[a-z]`` character class; the 3-char floor drops
    most function words that escape the stop list.
    """
    words = re.findall(r"[a-z]{3,}", text.lower())
    return [w for w in words if w not in _STOP_WORDS]


def information_novelty(text: str) -> InformationNovelty:
    """Layer 9 (EXPERIMENTAL in v1.0): per-sentence lexical novelty.

    For each sentence, computes the fraction of content words not seen
    in any earlier sentence. Tracks repetition patterns and the OLS
    slope of novelty over sentence position (decay).

    Length-confounded by Heaps' law: longer texts naturally exhibit
    lower mean novelty as the cumulative vocabulary saturates. The
    Standard (Section 5.9) marks this layer experimental and warns
    against direct cross-document comparison without length controls.

    Output:

    * ``mean_novelty`` — mean per-sentence novelty (0 to 1)
    * ``repetition_rate`` — fraction of sentences with novelty < 0.2
    * ``decay`` — OLS slope of novelty over sentence position. Negative
      decay is natural; steep negative + high repetition = padding.
    * ``q1_novelty`` — mean novelty of the first quarter of sentences
    * ``q4_novelty`` — mean novelty of the last quarter of sentences

    All fields are 0.0 for input with no qualifying sentences.
    """
    sentences = _split_sentences_simple(text)

    cumulative_vocab: set[str] = set()
    novelty_scores: list[float] = []

    for sent in sentences:
        words = _content_words(sent)
        if not words:
            continue
        novel = [w for w in words if w not in cumulative_vocab]
        novelty = len(novel) / len(words)
        novelty_scores.append(novelty)
        cumulative_vocab.update(words)

    n = len(novelty_scores)
    if n == 0:
        return {
            "mean_novelty": 0.0,
            "repetition_rate": 0.0,
            "decay": 0.0,
            "q1_novelty": 0.0,
            "q4_novelty": 0.0,
        }

    mean_nov = sum(novelty_scores) / n

    # Repetition rate: sentences with strictly less than 20% novel content
    repetitive = sum(1 for s in novelty_scores if s < 0.2)
    repetition_rate = repetitive / n

    # OLS slope of novelty vs sentence index. Requires at least 3 points;
    # for n in {1, 2} the slope is undefined / unstable, returned as 0.0.
    decay_slope = 0.0
    if n > 2:
        x_mean = (n - 1) / 2
        cov_xy = sum((i - x_mean) * (y - mean_nov) for i, y in enumerate(novelty_scores))
        var_x = sum((i - x_mean) ** 2 for i in range(n))
        if var_x > 0:
            decay_slope = cov_xy / var_x

    # Quartile sizes use a 1-sentence floor so q1/q4 are always defined.
    q_size = max(n // 4, 1)
    q1 = sum(novelty_scores[:q_size]) / q_size
    q4 = sum(novelty_scores[-q_size:]) / q_size

    return {
        "mean_novelty": round(mean_nov, 3),
        "repetition_rate": round(repetition_rate, 3),
        "decay": round(decay_slope, 4),
        "q1_novelty": round(q1, 3),
        "q4_novelty": round(q4, 3),
    }


# -- Layer 10: Quality profile --------------------------------------------


def quality_profile(
    text: str,
    *,
    source: str | None = None,
    comparisons: list[str] | None = None,  # noqa: ARG001 (reserved for L3)
) -> QualityProfile:
    """Layer 10 (EXPERIMENTAL in v1.0): composite substance vs presentation
    index plus gap.

    Aggregates fidelity-leaning layers into a substance index and surface-
    leaning layers into a presentation index. The gap (presentation -
    substance) is the overclaiming signal: positive gap means polished
    surface exceeds verifiable substance.

    Substance components (when wired):

    * ``source_fidelity`` = 1 - source_matching.unsourced_rate (Layer 4),
      contributed only when ``source`` is provided and the source-matching
      precision is not ``low``.
    * ``entity_grounding`` = 1 - entity_provenance.entity_unsourced_rate
      (Layer 5), contributed when ``source`` is provided and at least 5
      entities were extracted (precision threshold).
    * (temporal_stability, epistemic_calibration reserved for Layers 3, 8
      once those are extracted)

    Presentation components (always available):

    * ``assertiveness`` — Layer 7 assertiveness_ratio
    * ``formatting_intensity`` — Layer 7 formatting_density / 3, capped at 1.0
    * ``vocabulary_diversity`` — Layer 7 type_token_ratio
    * (structural_effort from Layer 1a heading_defaultness reserved
      until the LLM-API integration is wired)

    Each index is computed independently when its side has at least one
    contributor; ``gap`` is meaningful only when BOTH sides contributed
    (otherwise ``gap`` is ``0.0``). Callers should inspect
    ``components_available`` to know which contributors ran. When neither
    side has contributors (e.g. empty text without source), all three
    values are ``0.0``.

    Validation (vault notes): four studies showed strong d effects.
    (1) source present vs absent: d=-5.78, N=24.
    (2) faithful vs embellished on xAI: d=-5.43, N=12.
    (3) faithful vs embellished on Gemini: d=-2.28, N=12.
    (4) 4-dose Gemini gradient: monotonic, endpoint d=-2.13, N=24.
    Cross-generator and dose-response evidence support construct validity.
    Composite metrics inherit component limitations.

    Args:
        text: The output to evaluate.
        source: Source material; required for substance contribution
            from Layer 4.
        comparisons: Reserved for Layer 3 (temporal instability).
            Currently inert.

    Returns:
        A ``QualityProfile`` dict with substance / presentation indices,
        gap, the contributing component scores, and the list of
        contributors.
    """
    substance: dict[str, float] = {}
    presentation: dict[str, float] = {}

    # Substance: source fidelity (Layer 4) when source is provided and
    # precision is at least "adequate". "low" precision is excluded
    # because few-number outputs produce unstable rates.
    if source is not None:
        sm = source_matching(text, source)
        if sm["precision"] != "low":
            substance["source_fidelity"] = 1.0 - sm["unsourced_rate"]

        # Entity grounding (Layer 5) when at least 5 entities extracted.
        # The vault's "low" precision threshold for entities is total < 5.
        ep = entity_provenance(text, source)
        if ep["n_entities"] >= 5:
            substance["entity_grounding"] = 1.0 - ep["entity_unsourced_rate"]

    # Presentation: surface signals from Layer 7. These are always
    # computable from text alone.
    pf = presentation_features(text)
    presentation["assertiveness"] = pf["assertiveness_ratio"]
    presentation["formatting_intensity"] = min(pf["formatting_density"] / 3, 1.0)
    presentation["vocabulary_diversity"] = pf["type_token_ratio"]

    # Compose components dict (one entry per contributor, rounded for
    # storage parity with the indices).
    components: dict[str, float] = {
        k: round(v, 3) for k, v in {**substance, **presentation}.items()
    }
    components_available = list(substance.keys()) + list(presentation.keys())

    # Indices: each side computed independently when it has contributors;
    # gap is meaningful only when BOTH sides have contributors.
    sub_idx = sum(substance.values()) / len(substance) if substance else 0.0
    pres_idx = sum(presentation.values()) / len(presentation) if presentation else 0.0
    gap = (pres_idx - sub_idx) if (substance and presentation) else 0.0

    return {
        "substance_index": round(sub_idx, 3),
        "presentation_index": round(pres_idx, 3),
        "gap": round(gap, 3),
        "components": components,
        "components_available": components_available,
    }


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
