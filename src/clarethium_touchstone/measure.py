"""Output measurement (Touchstone Standard Section 5).

Reference implementation of the eleven measurement layers.

This module provides:

* ``measure()`` - top-level function returning a full ``MeasureResult``
* Individual layer functions for callers needing a specific measurement

All layers operate without invoking AI models on the output, with the
exception of Layer 1a (heading defaultness) which OPTIONALLY uses an
LLM API for baseline generation.

Implementation status: progressive extraction in progress.

* Layer 1 (``structural_profile``): IMPLEMENTED (1b, 1c always; 1a runs
  when both ``topic`` and a ``baseline_generator`` callable are provided)
* Layer 2 (``claim_density``): IMPLEMENTED
* Layer 3 (``temporal_instability``): IMPLEMENTED
* Layer 4 (``source_matching``): IMPLEMENTED
* Layer 5 (``entity_provenance``): IMPLEMENTED (directional in v1.0)
* Layer 6 (``vocabulary_proximity``): IMPLEMENTED (directional in v1.0)
* Layer 7 (``presentation_features``): IMPLEMENTED
* Layer 8 (``epistemic_calibration``): IMPLEMENTED (experimental in v1.0)
* Layer 9 (``information_novelty``): IMPLEMENTED (experimental in v1.0)
* Layer 10 (``quality_profile``): IMPLEMENTED (substance from L3 + L4 + L5 +
  L8, presentation from L7; structural_effort reserved for L1a once the
  LLM-API integration is wired)
* Layer 11 (``grounding_decomposition``): IMPLEMENTED (experimental in v1.0)

See Appendix C of the Standard for layer-by-layer status.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal, cast

from clarethium_touchstone._version import __standard_version__, __version__
from clarethium_touchstone.types import (
    ClaimDensity,
    EntityProvenance,
    EpistemicCalibration,
    GFPProportions,
    GFPSentence,
    GroundingDecomposition,
    HeadingDefaultness,
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
# Public type aliases
# ---------------------------------------------------------------------------

BaselineGenerator = Callable[[str], str | None]
"""Callable that generates a baseline document given a prompt.

Layer 1a (heading defaultness) requires an LLM to produce baseline
documents on the same topic. Touchstone is vendor-neutral: callers
supply their own callable. The generator returns the model's output
text or ``None`` on failure (rate limit, timeout, etc.).
"""

# Number of baseline documents to generate for Layer 1a (vault default).
_DEFAULT_N_BASELINES = 3

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
    baseline_generator: BaselineGenerator | None = None,
    n_baselines: int = _DEFAULT_N_BASELINES,
    p_detection_mode: str = "conservative",
) -> MeasureResult:
    """Run all applicable measurement layers on ``text``.

    Layers 1b, 1c, 2, 7, 9, 10 run on any text. Layers 4, 5, 6, 8, 11
    require ``source``. Layer 3 requires ``comparisons``. Layer 1a
    (heading defaultness) requires both ``topic`` AND
    ``baseline_generator`` (a vendor-neutral callable that invokes
    an LLM to produce baseline documents).

    Args:
        text: The output to measure.
        source: Optional source material the output may reference.
            When None, layers 4, 5, 6, 8, 11 are not run and their
            keys carry None in the result.
        comparisons: Optional alternative versions of the output for
            temporal instability measurement. When None or empty,
            ``temporal_instability`` carries None.
        topic: Optional topic string for Layer 1a baseline generation.
            Required for 1a (paired with ``baseline_generator``).
        baseline_generator: Optional callable
            ``(prompt: str) -> str | None`` that runs the LLM. When
            both this and ``topic`` are provided, 1a runs.
        n_baselines: Number of baseline documents to request for 1a.
        p_detection_mode: ``conservative`` (default) for Layer 11 P-marker
            detection. Standard conformance requires conservative mode.

    Returns:
        A ``MeasureResult`` with one key per applicable layer plus
        ``standard_version`` and ``library_version``. Layers that
        weren't run carry ``None``. Quality profile (Layer 10) is
        always included; it composes whatever substance components
        their preconditions allow.
    """
    result: MeasureResult = {
        "structural_profile": structural_profile(
            text,
            topic=topic,
            baseline_generator=baseline_generator,
            n_baselines=n_baselines,
        ),
        "claim_density": claim_density(text),
        "presentation_features": presentation_features(text),
        "information_novelty": information_novelty(text),
        "quality_profile": quality_profile(text, source=source, comparisons=comparisons),
        "temporal_instability": (temporal_instability(text, comparisons) if comparisons else None),
        "source_matching": source_matching(text, source) if source is not None else None,
        "entity_provenance": entity_provenance(text, source) if source is not None else None,
        "vocabulary_proximity": (
            vocabulary_proximity(text, source) if source is not None else None
        ),
        "epistemic_calibration": (
            epistemic_calibration(text, source) if source is not None else None
        ),
        "grounding_decomposition": (
            grounding_decomposition(text, source, p_detection_mode=p_detection_mode)
            if source is not None
            else None
        ),
        "standard_version": __standard_version__,
        "library_version": __version__,
    }
    return result


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


# Threshold above which the heading set is considered "default" — the
# fraction of the document's headings whose tokens overlap a corpus of
# baseline LLM-generated headings on the same topic. Vault-faithful
# (gate_0 exploratory threshold = 0.40).
_HEADING_DEFAULTNESS_THRESHOLD = 0.40

# Word-overlap threshold per heading: a heading "matches the baseline"
# when more than this fraction of its tokens are present in the
# baseline-heading word union.
_HEADING_WORD_OVERLAP_THRESHOLD = 0.5

# Default LLM prompt for baseline generation. Vault-faithful.
_BASELINE_PROMPT_TEMPLATE = (
    "Write a thorough analysis of: {topic}\n\nWrite 600-800 words with 5-7 sections (## headings)."
)


def _heading_words(heading: str) -> set[str]:
    """Tokenise a heading into a lowercase word set, dropping numbering
    and emphasis (vault-faithful: ``re.sub(r'[\\*\\d\\.\\s]+', ' ', h)``).
    """
    cleaned = re.sub(r"[\*\d\.\s]+", " ", heading).lower()
    return set(cleaned.split())


def _compute_heading_defaultness(
    text: str,
    topic: str,
    baseline_generator: BaselineGenerator,
    n_baselines: int,
) -> HeadingDefaultness | None:
    """Layer 1a: heading-baseline Jaccard-style overlap.

    For each heading in ``text``, compute the fraction of tokens
    appearing in the union of words from baseline headings (LLM-
    generated outputs on the same topic). A heading "matches the
    baseline" when overlap > 0.5. The returned score is the fraction
    of doc headings that match — higher = more default.

    NON-DETERMINISTIC: the generator is typically called at temperature
    > 0 to surface diverse defaults. Repeated calls produce different
    baselines and different scores.

    Returns ``None`` when:
    - The document has no level-2/3 headings to score
    - All baseline-generation calls fail (return None)
    """
    doc_headings = _extract_headings_simple(text)
    if not doc_headings:
        return None

    prompt = _BASELINE_PROMPT_TEMPLATE.format(topic=topic)
    baseline_word_union: set[str] = set()
    n_baselines_succeeded = 0
    for _ in range(n_baselines):
        baseline_text = baseline_generator(prompt)
        if baseline_text is None:
            continue
        n_baselines_succeeded += 1
        for h in _extract_headings_simple(baseline_text):
            baseline_word_union.update(_heading_words(h))

    if n_baselines_succeeded == 0:
        return None

    matches = 0
    for h in doc_headings:
        hw = _heading_words(h)
        if not hw:
            continue
        overlap = len(hw & baseline_word_union) / len(hw)
        if overlap > _HEADING_WORD_OVERLAP_THRESHOLD:
            matches += 1

    score = round(matches / len(doc_headings), 4)
    return {
        "jaccard_overlap": score,
        "is_default": score > _HEADING_DEFAULTNESS_THRESHOLD,
        "n_baseline_documents": n_baselines_succeeded,
    }


def structural_profile(
    text: str,
    *,
    topic: str | None = None,
    baseline_generator: BaselineGenerator | None = None,
    n_baselines: int = _DEFAULT_N_BASELINES,
) -> StructuralProfile:
    """Layer 1: structural profile (1a heading defaultness, 1b mechanism
    ratio, 1c assertion ratio).

    Layer 1a (``heading_defaultness``) is OPTIONAL and requires both a
    ``topic`` argument AND a ``baseline_generator`` callable that
    invokes an LLM to produce baseline documents on the same topic.
    Touchstone is vendor-neutral: supply your own client. When either
    is missing, 1a returns None. 1b and 1c run on any text.

    Args:
        text: The output to measure.
        topic: Optional topic string for 1a baseline generation. Required
            for 1a to run.
        baseline_generator: Optional callable
            ``(prompt: str) -> str | None`` that runs the LLM and returns
            the generated text (or None on failure). Required for 1a.
        n_baselines: Number of baseline documents to request (default 3).

    Returns:
        A ``StructuralProfile`` with ``heading_defaultness`` (HeadingDefaultness
        dict when 1a runs, else None), ``mechanism_ratio``,
        ``assertion_ratio``, and ``assertion_precision``.
    """
    heading_defaultness: HeadingDefaultness | None = None
    if topic is not None and baseline_generator is not None:
        heading_defaultness = _compute_heading_defaultness(
            text, topic, baseline_generator, n_baselines
        )
    ratio, precision = _assertion_ratio(text)
    return {
        "heading_defaultness": heading_defaultness,
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
    """Layer 3: cross-version number stability across regenerated outputs.

    Construct: fraction of unique (value, type) number pairs that appear
    in only SOME versions of the same task. Instability is a PROXY for
    fabrication, not a direct measurement: EXP-081c showed ~46% of
    unstable numbers coincidentally match source material (parametric-
    memory overlap, not retrieval). Instability overcounts true
    fabrication by approximately half. Cannot detect stable fabrication
    (consistently wrong numbers across regenerations).

    Algorithm: extract digit-formatted numbers from ``text`` plus each
    comparison; build a set of (value, type) pairs per version; numbers
    in ALL versions are stable, numbers in only SOME are unstable.
    ``instability_rate = unstable / total_unique``.

    Args:
        text: Primary document.
        comparisons: List of one or more alternative regenerations of
            the same task. May be empty: with no comparisons, every
            number in text is "stable" (appears in all 1 versions),
            so instability_rate is 0.0 (uninformative — supply at
            least one comparison for a meaningful signal).

    Returns:
        ``TemporalInstability`` with rate, counts, and versions
        compared. Empty input or zero numbers yields all-zero output.
    """
    all_texts = [text, *comparisons]
    all_num_sets: list[set[tuple[str, str]]] = []

    for t in all_texts:
        nums = _filter_numbers(_extract_numbers_for_matching(t), t)
        all_num_sets.append({(n["value"], n["type"]) for n in nums})

    all_nums = set().union(*all_num_sets) if all_num_sets else set()
    n_versions = len(all_texts)
    stable = {v for v in all_nums if sum(v in s for s in all_num_sets) == n_versions}
    n_unstable = len(all_nums) - len(stable)
    total = len(all_nums)
    instability_rate = n_unstable / total if total > 0 else 0.0

    return {
        "instability_rate": round(instability_rate, 3),
        "n_unstable": n_unstable,
        "n_total": total,
        "versions_compared": n_versions,
    }


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

# Broader assertion patterns than Layer 1c REGISTER_PATTERNS["ASSERTION"].
# The structural assertion ratio (Layer 1c) was validated on the original
# 13 patterns; Layer 8 uses a wider set including additional high-confidence
# phrases the structural ratio intentionally omits (to preserve its
# reference distributions). Vault-faithful.
_CALIBRATION_ASSERTION_PATTERNS: tuple[str, ...] = (
    # Original Layer 1c ASSERTION patterns
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
    # Expanded calibration-only patterns (v1.3)
    r"\bit\s+is\s+clear\s+that\b",
    r"\bthere\s+is\s+no\s+doubt\b",
    r"\bwithout\s+(?:question|doubt|exception)\b",
    r"\bproves?\s+(?:that|beyond)\b",
    r"\bindisputabl[ye]\b",
    r"\bconclusivel[ye]\b",
    r"\bunambiguous(?:ly)?\b",
    r"\bdefinitiv(?:e|ely)\b",
    r"\binevitabl[ye]\b",
    r"\bunquestionabl[ye]\b",
    r"\bcertainly\b",
    r"\bdemonstrates?\s+(?:that|the|a|an)\b",
    r"\bwill\s+(?:always|never|inevitably|certainly)\b",
    r"\bno\s+(?:question|doubt|exception)\b",
    r"\bcannot\s+(?:fail|be\s+denied|be\s+disputed)\b",
    r"\bis\s+(?:undeniable|indisputable|certain|inevitable)\b",
    r"\bwill\s+(?:definitely|undoubtedly|surely)\b",
    r"\bproven\s+(?:to|that|by)\b",
)

_CALIBRATION_ASSERTION_RE = re.compile("|".join(_CALIBRATION_ASSERTION_PATTERNS), re.IGNORECASE)


def _calibration_precision(total: int) -> Literal["high", "adequate", "low"]:
    """Map total assertion count to precision indicator.

    Vault thresholds: < 5 = low, < 15 = adequate, >= 15 = good. The
    Touchstone TypedDict uses ``high`` instead of ``good`` for the
    upper tier (vocabulary normalisation across layers); semantics
    are identical.
    """
    if total < 5:
        return "low"
    if total < 15:
        return "adequate"
    return "high"


def epistemic_calibration(text: str, source: str) -> EpistemicCalibration:
    """Layer 8 (EXPERIMENTAL in v1.0): per-sentence assertion grounding.

    Cross-layer metric. For each sentence containing assertion markers
    (broader set than Layer 1c), checks whether grounding evidence
    exists via three independent paths:

    1. **Sourced number** — sentence contains a digit-formatted number
       (Layer 4 extraction) verified present in source.
    2. **Sourced entity** — sentence contains a Title Case multi-word
       phrase (e.g., ``Stanford University``) found in source via
       lowercase substring search.
    3. **High vocabulary overlap** — sentence's content words (Layer 9
       extraction) have >50% substring presence in source.

    A sentence with at least one ground is GROUNDED; otherwise it is
    OVERCLAIMING. Returns the calibration score (grounded fraction),
    the overclaiming rate, and a precision indicator.

    The expanded assertion set (v1.3 calibration-only) catches phrases
    like "it is clear that", "indisputable", "conclusively",
    "definitive(ly)", "inevitable", "demonstrates that" — vault-faithful
    augmentation that Layer 1c's structural ratio omits to preserve
    validated reference distributions.

    Returns 0.0 / "low" precision when no assertion-bearing sentences
    are found (the TypedDict requires float values; the vault's
    ``None`` sentinel is normalised to 0.0 here).
    """
    sentences = _split_sentences_simple(text)
    source_lower = source.lower()

    total_assertions = 0
    grounded_assertions = 0

    for sent in sentences:
        if not _CALIBRATION_ASSERTION_RE.findall(sent):
            continue

        total_assertions += 1
        grounded = False

        # Ground 1: sourced number in sentence
        sent_numbers = _filter_numbers(_extract_numbers_for_matching(sent), sent)
        for num in sent_numbers:
            if _number_in_source(num, source):
                grounded = True
                break

        # Ground 2: sourced Title Case entity (multi-word phrase)
        if not grounded:
            for m in re.finditer(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", sent):
                if m.group(1).lower() in source_lower:
                    grounded = True
                    break

        # Ground 3: high vocabulary overlap with source (>50%)
        if not grounded:
            sent_words = _content_words(sent)
            if sent_words:
                grounded_count = sum(1 for w in sent_words if w in source_lower)
                vocab_score = grounded_count / len(sent_words)
                if vocab_score > 0.5:
                    grounded = True

        if grounded:
            grounded_assertions += 1

    if total_assertions == 0:
        return {
            "calibration_score": 0.0,
            "overclaiming_rate": 0.0,
            "n_assertions": 0,
            "n_grounded": 0,
            "precision": "low",
        }

    calibration = grounded_assertions / total_assertions
    overclaim_rate = (total_assertions - grounded_assertions) / total_assertions
    return {
        "calibration_score": round(calibration, 3),
        "overclaiming_rate": round(overclaim_rate, 3),
        "n_assertions": total_assertions,
        "n_grounded": grounded_assertions,
        "precision": _calibration_precision(total_assertions),
    }


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
    comparisons: list[str] | None = None,
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
    * ``epistemic_calibration`` = epistemic_calibration.calibration_score
      (Layer 8), contributed when ``source`` is provided and the
      calibration precision is not ``low`` (≥5 assertions found).
    * ``temporal_stability`` = 1 - temporal_instability.instability_rate
      (Layer 3), contributed when ``comparisons`` is provided and at least
      10 unique numbers appear across versions (vault precision threshold).

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

        # Epistemic calibration (Layer 8) when precision is at least
        # adequate (≥5 assertion-bearing sentences).
        ec = epistemic_calibration(text, source)
        if ec["precision"] != "low":
            substance["epistemic_calibration"] = ec["calibration_score"]

    # Temporal stability (Layer 3) when comparisons are supplied and at
    # least 10 unique numbers appear across versions (vault precision
    # threshold). Independent of source.
    if comparisons:
        ti = temporal_instability(text, comparisons)
        if ti["n_total"] >= 10:
            substance["temporal_stability"] = 1.0 - ti["instability_rate"]

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

# External entity P-markers: hard-coded names/concepts not typically in
# analytical source documents (drugs, companies, products, indices). The
# list is domain-biased toward the operator's research corpus; extend it
# for new domains. Vault-faithful; static in v1.0.
_GFP_EXTERNAL_ENTITIES: tuple[str, ...] = (
    r"\bSTEP\s+\d\b",
    r"\bSURMOUNT\b",
    r"\bSELECT\b",
    r"\bRybelsus\b",
    r"\borforglipron\b",
    r"\btirzepatide\b",
    r"\bZepbound\b",
    r"\bphentermine\b",
    r"\borlistat\b",
    r"\bHuawei\b",
    r"\bSamsung\b",
    r"\bLilly\b",
    r"\biPhone\s*1[5-9]\b",
    r"\bVision\s*Pro\b",
    r"\bSiri\b",
    r"\bApple\s*Intelligence\b",
    r"\bM-series\b",
    r"\bISM\b",
    r"\bADP\b",
    r"\bOkun\b",
    r"\bNAIRU\b",
    r"\bDMA\b",
    r"\bNovo\s*Nordisk\b",
)


def _gfp_is_derivable(value: float, source_floats: set[float], tolerance: float = 0.02) -> bool:
    """Check whether ``value`` is arithmetically derivable from source numbers.

    Handles single-number derivations (``A/100``, ``A*100`` for percent
    conversion), two-number derivations (``A/B``, ``A/B*100``, ``A*B``,
    ``A+B``, ``A-B``), and two-step add/subtract intermediates combined
    with another source number (tighter 1% tolerance).

    Vault-faithful. The derivation checker is known to saturate as the
    source's number count grows: at N>=10 source floats, false-positive
    rate approaches 100%, effectively disabling Layer 11's primary P
    signal for number-dense sources. See Standard Section 5.11 scope
    boundary and ``_gfp_assess_regime`` below.
    """
    if not source_floats:
        return False

    src = list(source_floats)

    def close(derived: float, target: float) -> bool:
        if abs(target) < 0.001:
            return abs(derived) < 0.001
        return abs(derived - target) / abs(target) < tolerance

    # Single-number derivations: percentage conversion
    for a in src:
        if close(a / 100, value) or close(a * 100, value):
            return True

    # Two-number derivations: ratios, products
    for a in src:
        if a == 0:
            continue
        for b in src:
            if b == 0:
                continue
            if close(a / b * 100, value) or close(a / b, value) or close(a * b, value):
                return True

    # Two-number additive forms
    for i in range(len(src)):
        for j in range(i, len(src)):
            a, b = src[i], src[j]
            if close(a + b, value):
                return True
            for diff in (a - b, b - a):
                if abs(diff) > 0.001 and close(diff, value):
                    return True

    # Two-step add/subtract intermediates combined with a source number.
    # Multiplication/division intermediates are excluded because they
    # produce coincidental matches on small-number sources. Tighter 1%
    # tolerance for these to limit the combinatorial false-positive rate.
    add_sub_intermediates: set[float] = set()
    for i in range(len(src)):
        for j in range(i, len(src)):
            a, b = src[i], src[j]
            add_sub_intermediates.add(a + b)
            if a != b:
                add_sub_intermediates.add(a - b)
                add_sub_intermediates.add(b - a)

    def close_tight(derived: float, target: float) -> bool:
        if abs(target) < 0.001:
            return abs(derived) < 0.001
        return abs(derived - target) / abs(target) < 0.01

    for inter in add_sub_intermediates:
        if close_tight(inter, value):
            return True
        for s in src:
            if s != 0:
                if close_tight(inter / s * 100, value):
                    return True
                if close_tight(inter / s, value):
                    return True
            if close_tight(inter + s, value):
                return True
            if abs(inter - s) > 0.001 and close_tight(inter - s, value):
                return True

    # Percentage application: (a/100) * b — Revenue * Margin%, Total *
    # Share%, Base * Rate%. Only percentage-to-decimal intermediates
    # participate in multiplication to avoid larger intermediate sets.
    for a in src:
        if a == 0:
            continue
        pct = a / 100
        for b in src:
            if close(pct * b, value):
                return True

    return False


def grounding_decomposition(
    text: str,
    source: str,
    *,
    p_detection_mode: str = "conservative",  # noqa: ARG001 (reserved)
) -> GroundingDecomposition:
    """Layer 11 (EXPERIMENTAL in v1.0): per-sentence Grounded / Framed /
    Projected classification.

    For each sentence, classify the primary information provenance:

    * **G (Grounded)** — restates or mechanically derives from source data.
    * **F (Framed)** — interprets, evaluates, or assigns significance.
    * **P (Projected)** — introduces external data, predictions, or
      unsourced specifics.

    P decision uses three signals:

    1. **Unsourced numbers** (primary): sentence contains a digit-formatted
       number that is neither in source verbatim nor derivable via
       ``_gfp_is_derivable`` from source numbers.
    2. **External entities** (secondary): sentence matches a hard-coded
       pattern from ``_GFP_EXTERNAL_ENTITIES`` (drug names, companies,
       indices). Domain-biased; extend for new corpora.
    3. **Unsourced years** (gated): year (19xx/20xx) absent from source,
       gated on either an unsourced number being present OR cleaned
       sentence length > 50 chars.

    G score (when not P): ``0.5 × has_sourced_or_derived + 0.3 ×
    vocab_overlap + 0.2 × all_nums_sourced_bonus``. Threshold 0.4.

    F is the residual.

    Sentences cleaned to <20 chars (markdown stripped) are skipped.

    Scope boundary (vault Standard 5.11): the primary unsourced-number
    signal saturates as source number count grows. At ≥10 source numbers,
    derivation-checker false-positive rate approaches 100%. P falls back
    to secondary signals (external entities, gated years). Cross-reference
    Layer 4 for digit-level fabrication detection on number-dense
    sources.

    Args:
        text: Output to classify.
        source: Source material.
        p_detection_mode: Reserved for future ``conservative`` /
            ``liberal`` differentiation. Currently inert; only conservative
            is implemented and is required for Standard conformance.

    Returns:
        ``GroundingDecomposition`` with proportions, per-sentence
        classifications, projection flag, and prohibition recommendation
        when projection is detected.
    """
    sentences = _split_sentences_simple(text)

    # Source numbers as floats for derivation checking.
    src_nums = _filter_numbers(_extract_numbers_for_matching(source), source)
    source_floats: set[float] = set()
    for nd in src_nums:
        try:
            source_floats.add(float(nd["value"]))
        except (ValueError, KeyError):
            continue

    # Source years for unsourced-year gating.
    source_years = {int(m.group(1)) for m in re.finditer(r"\b((?:19|20)\d{2})\b", source)}

    classifications: list[dict[str, object]] = []

    for sent in sentences:
        # Clean for length check (drop markdown markers).
        clean = re.sub(r"[#*|_\-]", "", sent).strip()
        if len(clean) < 20:
            classifications.append({"_skip": True})
            continue

        # Number provenance: sourced / derived / unsourced.
        sent_nums = _filter_numbers(_extract_numbers_for_matching(sent), sent)
        sourced: list[dict[str, str]] = []
        derived: list[dict[str, str]] = []
        unsourced: list[dict[str, str]] = []

        for nd in sent_nums:
            if _number_in_source(nd, source):
                sourced.append(nd)
                continue
            try:
                fval = float(nd["value"])
            except (ValueError, KeyError):
                unsourced.append(nd)
                continue
            if _gfp_is_derivable(fval, source_floats):
                derived.append(nd)
            else:
                unsourced.append(nd)

        # Filter unsourced of small ints (1-10) and explicit ranges.
        filtered_unsourced: list[dict[str, str]] = []
        for nd in unsourced:
            try:
                fval = float(nd["value"])
            except (ValueError, KeyError):
                filtered_unsourced.append(nd)
                continue
            if fval == int(fval) and 1 <= fval <= 10:
                continue
            raw = nd.get("raw", "")
            if re.search(r"\b" + re.escape(raw) + r"\s*-\s*\d+\b", sent):
                continue
            filtered_unsourced.append(nd)
        unsourced = filtered_unsourced

        # External entity matches.
        ext_entities: list[str] = []
        for pat in _GFP_EXTERNAL_ENTITIES:
            for m in re.finditer(pat, sent, re.IGNORECASE):
                ext_entities.append(m.group())

        # Unsourced years (gated on additional evidence).
        sent_years = {int(m.group(1)) for m in re.finditer(r"\b((?:19|20)\d{2})\b", sent)}
        unsourced_yrs = sent_years - source_years

        # P decision.
        p_markers: list[str] = []
        if unsourced:
            p_markers.append("unsourced_numbers")
        if ext_entities:
            p_markers.append("external_entities")
        if unsourced_yrs and (unsourced or len(clean) > 50):
            p_markers.append("unsourced_years")

        if p_markers:
            classifications.append(
                {
                    "sentence": sent,
                    "primary": "P",
                    "p_markers": p_markers,
                }
            )
            continue

        # G score (only when not P).
        has_sourced = bool(sourced) or bool(derived)
        sent_words = set(_content_words(sent))
        src_words = set(_content_words(source))
        vocab_overlap = len(sent_words & src_words) / len(sent_words) if sent_words else 0.0

        grounding = 0.0
        if has_sourced:
            grounding += 0.5
        grounding += vocab_overlap * 0.3
        total_nums = len(sourced) + len(derived) + len(unsourced)
        if total_nums > 0 and not unsourced and (sourced or derived):
            grounding += 0.2

        primary: str = "G" if grounding >= 0.4 else "F"
        classifications.append(
            {
                "sentence": sent,
                "primary": primary,
                "grounding_score": round(grounding, 3),
            }
        )

    # Aggregate.
    n_g = sum(1 for c in classifications if c.get("primary") == "G")
    n_f = sum(1 for c in classifications if c.get("primary") == "F")
    n_p = sum(1 for c in classifications if c.get("primary") == "P")
    n_classified = n_g + n_f + n_p
    proportions: GFPProportions = {
        "G": round(n_g / n_classified, 3) if n_classified > 0 else 0.0,
        "F": round(n_f / n_classified, 3) if n_classified > 0 else 0.0,
        "P": round(n_p / n_classified, 3) if n_classified > 0 else 0.0,
    }

    # The internal classifications list uses dict[str, object] (which is
    # a structural superset of GFPSentence). Cast at the boundary; runtime
    # shape matches the TypedDict.
    sentence_classifications: list[GFPSentence] = cast(
        "list[GFPSentence]",
        [c for c in classifications if not c.get("_skip")],
    )

    has_projection = n_p > 0
    recommendation: str | None = None
    if has_projection:
        recommendation = (
            "Projected content detected. To eliminate, add to your prompt: "
            '"Do not use any numbers that are not in the provided source." '
            "This reduces projected content by 84-100% while preserving "
            "grounded analysis (EXP-095, 30 prohibition outputs, 3 models)."
        )

    return {
        "proportions": proportions,
        "sentence_classifications": sentence_classifications,
        "p_detection_mode": "conservative",
        "n_sentences": n_classified,
        "n_grounded": n_g,
        "n_framed": n_f,
        "n_projected": n_p,
        "has_projection": has_projection,
        "recommendation": recommendation,
    }


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
