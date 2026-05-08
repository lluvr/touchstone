"""Tests for Layer 5 entity provenance (Touchstone Standard Section 5.5).

Layer 5 is DIRECTIONAL in v1.0 (Standard Section 5.5). Five regex
patterns extract named entities from text, then check each against the
source via two-pass match (whole substring, then word-by-word).

Patterns:
1. Person names following a trigger prefix
2. Organisations with explicit suffix (Labs, Corp, Foundation, ...)
3. Attributions ("according to ...", "per ...", "cited by ...")
4. Parenthetical citations ``(Author, YYYY)``
5. CamelCase organisation names (OpenAI, GitHub)
"""

from __future__ import annotations

from clarethium_touchstone.measure import (
    _entity_in_source,
    _extract_entities,
    entity_provenance,
)

# ---------------------------------------------------------------------------
# Output shape contract
# ---------------------------------------------------------------------------


def test_output_shape_is_well_formed() -> None:
    """All required fields present with correct types."""
    text = "According to John Smith, the result holds."
    result = entity_provenance(text, "John Smith reference.")
    assert isinstance(result["entity_unsourced_rate"], float)
    assert isinstance(result["n_entities"], int)
    assert isinstance(result["n_unsourced"], int)
    assert isinstance(result["unsourced_entities"], list)
    assert all(isinstance(s, str) for s in result["unsourced_entities"])


def test_output_keys_are_exact_set() -> None:
    """No extra fields leak from the reference implementation."""
    result = entity_provenance("Some text.", "Some source.")
    assert set(result.keys()) == {
        "entity_unsourced_rate",
        "n_entities",
        "n_unsourced",
        "unsourced_entities",
    }


def test_empty_text_returns_zero() -> None:
    """Empty input: zero entities, zero rate."""
    result = entity_provenance("", "Source content here.")
    assert result["n_entities"] == 0
    assert result["n_unsourced"] == 0
    assert result["entity_unsourced_rate"] == 0.0
    assert result["unsourced_entities"] == []


# ---------------------------------------------------------------------------
# Pattern 1: Person names with triggering prefix
# ---------------------------------------------------------------------------


def test_person_pattern_requires_trigger_prefix() -> None:
    """Behaviour: 'John Smith' bare in mid-sentence is NOT detected
    as a Person. The pattern requires 's, 'according to', 'by ', comma,
    em-dash, or period before the name.
    """
    # Bare "John Smith said" - no triggering prefix
    no_trigger = _extract_entities("John Smith said it would work.")
    assert not any(e["type"] == "PERSON" for e in no_trigger)

    # With "by" prefix → detected
    with_trigger = _extract_entities("The work was led by John Smith here.")
    assert any(e["type"] == "PERSON" and "John" in e["value"] for e in with_trigger)


def test_attribution_triggers_are_case_sensitive() -> None:
    """Behaviour: trigger words are matched WITHOUT re.IGNORECASE.

    Sentence-start 'According to' (capitalised A) does NOT trigger the
    PERSON or ATTRIBUTED patterns; mid-sentence lowercase 'according to'
    does. Pinned because this is surprising and affects downstream
    entity counts. Callers writing test inputs must use lowercase
    triggers or other prefixes (commas, periods, "by ").
    """
    sentence_start = _extract_entities("According to John Smith, this holds.")
    # 'According to' fails to trigger; only the post-comma 'John Smith'
    # matches via the comma trigger
    assert not any(e["type"] == "ATTRIBUTED" and "John" in e["value"] for e in sentence_start)

    mid_sentence = _extract_entities("Findings according to John Smith confirm.")
    # Lowercase 'according to' triggers both PERSON and ATTRIBUTED
    assert any(e["type"] == "ATTRIBUTED" and "John" in e["value"] for e in mid_sentence)


def test_person_blocklist_filters_common_nouns() -> None:
    """Names containing 'source', 'extends', 'mechanism', 'falsifier', or
    'section' are filtered out (false-match avoidance).
    """
    text = "The methodology extends Source Section here in the paper."
    entities = _extract_entities(text)
    # 'Source Section' would otherwise match the person pattern after the
    # period; blocklist catches 'source' and 'section'
    person_values = [e["value"] for e in entities if e["type"] == "PERSON"]
    for v in person_values:
        assert "Source" not in v.split()
        assert "Section" not in v.split()


# ---------------------------------------------------------------------------
# Pattern 2: Organisations with suffix
# ---------------------------------------------------------------------------


def test_org_suffix_patterns_detected() -> None:
    """Title Case word(s) + suffix (Labs/Corp/Inc/Foundation/University/...)
    matches the ORG pattern.
    """
    text = (
        "The MIT Foundation reported progress yesterday. "
        "Stanford University also contributed today. "
        "Acme Corp announced new initiatives globally."
    )
    entities = _extract_entities(text)
    org_values = {e["value"] for e in entities if e["type"] == "ORG"}
    assert any("Foundation" in v for v in org_values)
    assert any("University" in v for v in org_values)
    assert any("Corp" in v for v in org_values)


def test_org_pattern_includes_leading_the() -> None:
    """Behaviour: the ORG pattern's leading ``[A-Z][a-zA-Z]+``
    captures 'The' as a Title Case word, so 'The MIT Foundation' is
    extracted as a single entity rather than 'MIT Foundation'.
    """
    entities = _extract_entities("The MIT Foundation reported progress today.")
    org_values = [e["value"] for e in entities if e["type"] == "ORG"]
    assert any(v.startswith("The MIT") for v in org_values)


# ---------------------------------------------------------------------------
# Pattern 3: Attributions
# ---------------------------------------------------------------------------


def test_attribution_patterns_detected() -> None:
    """``according to``, ``per``, ``cited by``, ``reported by`` trigger
    attribution extraction.
    """
    text = "The findings according to John Smith confirm the result here."
    entities = _extract_entities(text)
    attrib = [e for e in entities if e["type"] == "ATTRIBUTED"]
    assert len(attrib) >= 1
    assert any("John" in e["value"] for e in attrib)


def test_attribution_pattern_is_greedy() -> None:
    """Behaviour: the attribution pattern's ``[A-Z]?`` makes the
    leading capital optional within the {0,4} quantifier, so trailing
    lowercase words are captured into the entity value.

    'according to John Smith confirms the result' → entity value
    'John Smith confirms the result'. Pinned because this produces
    noisy values that callers may need to post-process.
    """
    text = "Findings according to John Smith confirm the result yesterday."
    entities = _extract_entities(text)
    attrib_values = [e["value"] for e in entities if e["type"] == "ATTRIBUTED"]
    # At least one attribution captures more than just 'John Smith'
    assert any(len(v.split()) > 2 for v in attrib_values)


def test_attribution_blocklist_filters_pronouns() -> None:
    """'source', 'the', 'this', 'one' are filtered from attribution names."""
    text = "According to the report, this is true."
    entities = _extract_entities(text)
    attrib_values = [e["value"].lower() for e in entities if e["type"] == "ATTRIBUTED"]
    assert "the" not in attrib_values
    assert "this" not in attrib_values


# ---------------------------------------------------------------------------
# Pattern 4: Parenthetical citations
# ---------------------------------------------------------------------------


def test_parenthetical_citation_detected() -> None:
    """``(Author, YYYY)`` form is extracted as CITATION."""
    text = "Recent work (Smith, 2020) demonstrated this effect across studies."
    entities = _extract_entities(text)
    citations = [e for e in entities if e["type"] == "CITATION"]
    assert len(citations) == 1
    assert "Smith" in citations[0]["value"]
    assert "2020" in citations[0]["value"]


# ---------------------------------------------------------------------------
# Pattern 5: CamelCase organisations
# ---------------------------------------------------------------------------


def test_camelcase_org_detected() -> None:
    """OpenAI, GitHub, etc. are CamelCase ORG matches."""
    text = "OpenAI and GitHub announced their joint partnership last week."
    entities = _extract_entities(text)
    org_values = {e["value"] for e in entities if e["type"] == "ORG"}
    assert "OpenAI" in org_values
    assert "GitHub" in org_values


# ---------------------------------------------------------------------------
# Heading and table stripping
# ---------------------------------------------------------------------------


def test_headings_stripped_before_extraction() -> None:
    """Markdown heading lines are removed; entities only extracted from body."""
    text = (
        "## Heading containing John Smith name in the title\n"
        "Body paragraph: according to Jane Doe, the result holds."
    )
    entities = _extract_entities(text)
    person_values = [e["value"] for e in entities if e["type"] == "PERSON"]
    # Body PERSON match present
    assert any("Jane" in v for v in person_values)
    # Heading 'John Smith' must NOT be extracted (line stripped)
    # (Note: 'name in the title' contains lowercase, so wouldn't match anyway,
    # but the principle is the heading line is dropped entirely.)


def test_table_rows_stripped() -> None:
    """Markdown table rows (``|...|``) are removed before extraction."""
    text = "| John Smith | data row |\nBody: according to Jane Doe present."
    entities = _extract_entities(text)
    # 'John Smith' from table NOT extracted
    person_values = [e["value"] for e in entities if e["type"] == "PERSON"]
    assert all("John" not in v for v in person_values)


# ---------------------------------------------------------------------------
# Source matching
# ---------------------------------------------------------------------------


def test_self_source_yields_zero_unsourced() -> None:
    """Document = source: every entity must be in source."""
    text = (
        "The findings according to John Smith confirm. "
        "OpenAI and GitHub partnered. "
        "Stanford University did research. "
        "Recent work (Brown, 2021) demonstrated. "
        "The IBM Research lab contributed insights."
    )
    result = entity_provenance(text, text)
    assert result["entity_unsourced_rate"] == 0.0


def test_disjoint_source_marks_all_unsourced() -> None:
    """Source containing none of the doc's entities: rate = 1.0."""
    text = "OpenAI and GitHub announced new initiatives this quarter globally."
    result = entity_provenance(text, "Generic source content with no entities.")
    assert result["entity_unsourced_rate"] == 1.0
    assert result["n_unsourced"] == result["n_entities"]


def test_word_by_word_fallback_for_multiword_entities() -> None:
    """Behaviour: when full string isn't in source but each content
    word (>3 chars, non-stop) appears, the entity counts as in-source.
    """
    e = {"value": "Stanford University", "type": "ORG", "context": ""}
    # Source has both words separately
    assert _entity_in_source(e, "The Stanford team and the University worked together.")
    # Source missing one word
    assert not _entity_in_source(e, "The Stanford team only contributed today.")


def test_substring_match_full_value() -> None:
    """When the entity value (lowercased) is a substring of source
    (lowercased), the entity is grounded.
    """
    e = {"value": "OpenAI", "type": "ORG", "context": ""}
    assert _entity_in_source(e, "openai released a new model")
    # Substring match: 'openai' in 'openai...' → True


def test_entity_match_is_case_insensitive_both_directions() -> None:
    """Entity value and source are both .lower()'d before substring search,
    so case mismatches don't prevent grounding either way.
    """
    # Lowercase entity value, mixed-case source
    e_lower = {"value": "openai", "type": "ORG", "context": ""}
    assert _entity_in_source(e_lower, "OpenAI Inc was founded recently.")
    # Mixed-case entity value, lowercase source
    e_mixed = {"value": "OpenAI", "type": "ORG", "context": ""}
    assert _entity_in_source(e_mixed, "openai inc was founded recently.")


def test_substring_match_inflates_short_entity_values() -> None:
    """Behaviour: entity 'Smith' is grounded by source containing
    'Smithsonian' because Python ``in`` is a substring check, not a
    word-boundary check. Pinned because this affects interpretation -
    short entity values can match unrelated longer words.
    """
    e = {"value": "Smith", "type": "PERSON", "context": ""}
    assert _entity_in_source(e, "The Smithsonian Institution opened in 1846.")
    # 'smith' is substring of 'smithsonian' → True


def test_word_by_word_fallback_when_substring_fails() -> None:
    """When the entity value (full string) is NOT a substring of source,
    but every content word (>3 chars, non-stop) IS in source, the
    entity counts as grounded via the word-by-word fallback.
    """
    e = {"value": "Stanford University", "type": "ORG", "context": ""}
    # Source has 'Stanford' and 'University' but not contiguous
    src_split = "The University of California has many colleges, including Stanford in our state."
    # Substring 'stanford university' is NOT in this source string
    assert "stanford university" not in src_split.lower()
    # But word-by-word fallback succeeds
    assert _entity_in_source(e, src_split)


def test_word_by_word_fallback_fails_when_word_missing() -> None:
    """If any required content word is absent, word-by-word fails."""
    e = {"value": "Stanford University", "type": "ORG", "context": ""}
    src_partial = "The Stanford team contributed but the affiliation was elsewhere."
    # 'University' missing from source → word-by-word fails
    # And 'stanford university' substring also fails
    assert not _entity_in_source(e, src_partial)


# ---------------------------------------------------------------------------
# ORG pattern overlap with CamelCase pattern
# ---------------------------------------------------------------------------


def test_org_suffix_and_camelcase_coexist() -> None:
    """Behaviour: when text contains 'OpenAI Foundation', the ORG
    suffix pattern captures 'OpenAI Foundation' AND the CamelCase
    pattern separately captures 'OpenAI'. Both are stored because the
    dedup key for CamelCase is ('ORG_CAMEL', value) - distinct from
    ('ORG', 'OpenAI Foundation'). This inflates entity counts when
    CamelCase orgs appear inside larger ORG-suffix phrases.
    """
    text = "OpenAI Foundation announced new initiatives across all sites today."
    entities = _extract_entities(text)
    org_values = {e["value"] for e in entities if e["type"] == "ORG"}
    assert "OpenAI Foundation" in org_values
    assert "OpenAI" in org_values
    # Both stored: 2 ORG entries for what semantically reads as one org
    assert sum(1 for e in entities if e["type"] == "ORG") == 2


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_same_entity_value_under_different_types_kept_separately() -> None:
    """Behaviour: dedup is keyed on (type, value), so the same
    string captured under PERSON and ATTRIBUTED counts as two entities.
    """
    text = "Findings according to John Smith confirm the result yesterday."
    entities = _extract_entities(text)
    # Both PERSON and ATTRIBUTED capture forms involving 'John Smith'
    types_for_john = {e["type"] for e in entities if "John" in e["value"]}
    assert "PERSON" in types_for_john
    assert "ATTRIBUTED" in types_for_john


def test_repeated_mention_dedup_within_type() -> None:
    """Same entity under same type mentioned twice: dedup to one."""
    text = (
        "OpenAI announced one product. "
        "Later OpenAI announced another product. "
        "Then OpenAI continued operations."
    )
    entities = _extract_entities(text)
    openai_orgs = [e for e in entities if e["value"] == "OpenAI"]
    assert len(openai_orgs) == 1


# ---------------------------------------------------------------------------
# Adversarial discrimination
# ---------------------------------------------------------------------------


def test_faithful_vs_fabricated_unsourced_rate() -> None:
    """Adversarial: faithful output (all entities in source) has lower
    unsourced rate than fabricated output (entities absent from source).
    """
    src = (
        "OpenAI partnered with GitHub. "
        "The Stanford University team led the research. "
        "Findings from John Smith were cited extensively."
    )
    faithful = (
        "OpenAI partnered with GitHub on this initiative today. "
        "Stanford University led the research effort throughout. "
        "According to John Smith, the result holds across cases."
    )
    fabricated = (
        "Anthropic partnered with Microsoft on the new initiative. "
        "Berkeley University led the research effort throughout. "
        "According to Jane Brown, the result holds across cases."
    )
    faithful_r = entity_provenance(faithful, src)
    fab_r = entity_provenance(fabricated, src)
    assert faithful_r["entity_unsourced_rate"] < fab_r["entity_unsourced_rate"]
