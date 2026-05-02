# Touchstone Standard 1.0 (DRAFT)

**Status:** Draft v0.2. Sections 1, 3, 5, 6, 9, 10 substantially complete pending operator review. Sections 2, 4, 7, 8, 11, 12 require operator-authored finalization.
**Version:** 1.0.0-draft.2
**Date:** 2026-05-02 (drafting in progress)
**License:** CC-BY 4.0
**Canonical URL:** https://github.com/Clarethium/touchstone/blob/main/STANDARDS/touchstone-1.0.md

---

## Abstract

Touchstone Standard defines a model-independent methodology for verifying the structural quality, source grounding, fabrication characteristics, and specification compliance of AI-coupled work outputs. The Standard specifies eleven measurement layers for output profiling, five layers for specification compliance verification, calibration discipline, threshold conventions, and conformance requirements. Of the eleven measurement layers, ten use deterministic regex pattern matching, string analysis, and arithmetic; one uses optional LLM API for baseline generation. The Standard does not depend on AI models judging AI outputs.

---

## 1. Introduction

### 1.1 Purpose

The Standard provides a verifiable methodology for measuring AI-coupled work. Two complementary functions are defined:

- **Output measurement** (Section 5): profiling structural quality, claim density, source grounding, fabrication characteristics, presentation features, and grounding decomposition of AI-generated text against optional source material.
- **Specification compliance verification** (Section 6): extracting requirements from a written specification and verifying that an output addresses them.

Both functions are designed to operate without depending on a separate AI model to judge correctness. The Standard rests on the principle that an auditor cannot be made of the same material as the audited; AI evaluating AI inherits structural conflicts of interest.

### 1.2 Scope

The Standard covers:

- Eleven measurement layers for output profiling (Section 5)
- Five layers of specification compliance verification (Section 6)
- Eight requirement types for spec extraction (Section 6.4)
- Threshold values and calibration discipline (Section 7)
- Reference test cases for implementation validation (Section 8)
- Versioning and conformance rules (Sections 10-11)

### 1.3 Non-goals

The Standard does NOT:

- Define what AI outputs are subjectively *valuable*, *useful*, or *correct*
- Replace human judgment about fitness for purpose
- Detect malicious or adversarial intent of authors
- Verify factual claims against external knowledge bases beyond provided source material
- Substitute for legal, medical, or other domain-specific verification standards
- Judge truth of claims; only measure structural relationships to source material

### 1.4 Audience

This Standard targets:

- Software developers building verification tooling
- Researchers studying AI output quality and methodology
- Auditors and compliance professionals working with AI-generated work
- Educational institutions teaching AI methodology
- Platforms hosting AI-coupled work (such as FieldReceipts)

### 1.5 Status of this document

This document is a working draft of the canonical Touchstone Standard 1.0. Ratification follows operator-authored completion of remaining sections, editor-body review, and the Suggestion process documented in `SUGGESTIONS/PROCESS.md`.

---

## 2. Terminology

> **Operator finalization required.** Define key terms used throughout, including: Build, output, source, spec, claim, evidence, layer, conforming implementation. RFC 2119 keywords (MUST, SHOULD, MAY, RECOMMENDED, OPTIONAL) are used per their conventional meanings throughout this Standard.

---

## 3. Substrate principles

The Standard rests on four principles that distinguish it from LLM-as-judge approaches.

### 3.1 Model-independence

All required measurements MUST be performable without invoking an AI model to evaluate the output. Layer 1a (heading defaultness) and Layer 5 of specification compliance (semantic alignment) MAY use AI for ancillary tasks; these are explicitly OPTIONAL or conditionally executable. The core measurement methodology MUST function without AI when source and spec material are deterministic.

### 3.2 Structural over semantic

Measurements prioritize structural properties (presence of citations, claim density, source matching via string search, vocabulary proximity, format compliance) over semantic judgment (is this claim true). Structural properties are reproducible across implementations and time-stable.

### 3.3 Calibrated thresholds

Threshold values for accept/reject decisions MUST be explicit, versioned, and overridable. Default thresholds are specified in Section 7. Implementations and applications MAY adjust thresholds for their context but MUST document the adjustment.

### 3.4 Open and verifiable

The Standard, its threshold values, and its reference test cases are public. Conforming implementations MAY be open or proprietary; the Standard itself remains under CC-BY 4.0.

---

## 4. Output structure

> **Operator finalization required.** Specify canonical output format primarily addressed by the Standard. Reference implementation operates on Markdown analytical documents (validated scope per Section 9). Extension to structured outputs (JSON, structured markup) and other text formats is layer-specific and MAY be implementation-defined.

---

## 5. Output measurement layers

The Standard defines eleven measurement layers for output profiling. Implementations MUST implement Layers 1-7 and Layer 10 to be conforming. Layers 8-9 are EXPERIMENTAL in version 1.0; conforming implementations MAY include them. Layer 11 is REQUIRED when source material is provided; OPTIONAL otherwise.

### 5.1 Layer 1: Structural profile

The structural profile decomposes into three sub-layers measuring different structural dimensions:

**Layer 1a: Heading defaultness.** OPTIONAL. Generates baseline documents from a generic prompt (using an external LLM API such as Gemini Flash) and computes word-level Jaccard overlap between the document's headings and the baseline headings. Low overlap indicates non-default structure. This is the only layer with an LLM dependency.

**Layer 1b: Mechanism ratio.** REQUIRED. Counts regex matches against canonical causal-language patterns and buzzword patterns. Score = causal / (causal + buzzword). Measures reasoning style, not quality.

**Layer 1c: Assertion ratio.** REQUIRED. Counts epistemic register markers across five categories (ASSERTION, QUALIFIED, CONDITIONAL, EVIDENCED, SPECULATIVE). Score = ASSERTION / total. Operates on section bodies excluding headings. Implementations SHOULD flag low-precision results when total markers < 10.

### 5.2 Layer 2: Claim density

REQUIRED. Extracts sentences containing digit-formatted numbers (six pattern types: percentage, dollar amount, multiplier, entity count, duration, range) or causal markers. Reports counts per 1,000 words. Recall on digit-formatted numbers SHOULD exceed 95% on validated reference cases.

### 5.3 Layer 3: Temporal instability

REQUIRED when two or more independently generated versions of the output are provided. Extracts all digit-formatted numbers from the versions; classifies each unique (value, type) pair as stable (present in all versions) or unstable (present in only some). Instability rate = unstable / total. Implementations MUST filter year-like values and explicit word counts.

Note: Layer 3 measures instability, not fabrication directly. Instability is an upper bound on fabrication. The deprecated alias `fabrication_rate` MAY be retained for backwards compatibility and MUST be removed in version 2.0.

### 5.4 Layer 4: Source matching

REQUIRED when source material is provided. Extracts digit-formatted numbers from the document. Checks each against the source text via exact string search with type-aware matching (percent suffix for percentages, dollar prefix for dollar amounts, comma-formatted variants for integers). Unsourced rate = numbers not found / total numbers extracted.

Implementations MUST achieve zero false positive rate on documents where the source equals the document (every number in the document MUST be found if the document is the source).

### 5.5 Layer 5: Entity provenance

REQUIRED when source material is provided. Extracts named entities (person names, organization names, attribution patterns, parenthetical citations, CamelCase identifiers) using regex patterns. Checks each against source text via case-insensitive substring search. Entity unsourced rate = entities not found / total entities extracted.

### 5.6 Layer 6: Vocabulary proximity

REQUIRED when source material is provided. For each sentence, computes the fraction of content words (non-stopword, three or more characters) that also appear anywhere in the source text. Reports mean across all sentences. Low proximity is ambiguous: original analysis or fabricated content; MUST be interpreted alongside Layers 4-5.

### 5.7 Layer 7: Presentation features

REQUIRED. Computes:
- Type-token ratio (vocabulary diversity)
- Flesch-Kincaid grade level
- Formatting density (headings + bold + list items per 100 words)
- Assertiveness ratio (strong assertions / (assertions + hedges))
- Named concept count

These are descriptive features, not pass/fail metrics.

### 5.8 Layer 8: Epistemic calibration

EXPERIMENTAL in version 1.0. For each sentence containing ASSERTION register markers, checks three grounding signals: (1) contains a digit-formatted number found in source, (2) contains a capitalized multi-word entity found in source, (3) content word overlap with source exceeds a calibrated threshold. Calibration score = grounded assertions / total assertions. Overclaiming rate = 1 - calibration.

Implementations MUST flag results as low precision when total assertions < 5.

### 5.9 Layer 9: Information novelty

EXPERIMENTAL in version 1.0. Processes sentences in document order. For each sentence, computes fraction of content words not seen in any previous sentence. Tracks: mean novelty, repetition rate (sentences with low novelty), information decay (slope over position), first/last quartile novelty.

Note: Layer 9 measures lexical novelty, not semantic information content. Length-confounded by Heaps' law.

### 5.10 Layer 10: Quality profile

REQUIRED. Composite metric computed from Layers 1, 4, 5, 7, 8.

Substance index = mean of (1 - unsourced_rate, 1 - instability_rate, 1 - entity_unsourced_rate, calibration_score). Calibration is included only when its precision is "adequate" (assertion count >= 5).

Presentation index = mean of (assertiveness_ratio, min(formatting_density / 3, 1), type_token_ratio, 1 - heading_defaultness when available).

Quality gap = presentation_index - substance_index. Positive gap indicates overclaiming risk; negative gap indicates understated quality.

Implementations MUST document component availability when reporting quality_profile. Composite values without all required components MUST be flagged as such.

### 5.11 Layer 11: Grounding decomposition (G/F/P)

REQUIRED when source material is provided. For each sentence in the document, classifies the sentence's primary function as:

- **G (Grounded):** Restates or directly derives from source data
- **F (Framed):** Interprets, evaluates, or assigns significance to source data
- **P (Projected):** Cites external data, predicts futures, or states specifics not in or derivable from source

Reports document-level proportions (G%, F%, P%) and per-sentence classifications with grounding scores.

Implementation algorithm:

1. Compute per-sentence grounding score using Layer 4 (sourced number presence), Layer 5 (sourced entity presence), Layer 6 (vocabulary overlap).
2. Sentences with grounding score above threshold classify as G.
3. Sentences below threshold are checked for P-markers (forward temporal references, unsourced specific numbers, off-domain entities).
4. Sentences below threshold with P-markers classify as P.
5. Remaining sentences below threshold classify as F.

Conservative and liberal P-detection modes MAY be implemented; conservative is the default and required for conformance.

When a document includes an explicit prohibition recommendation (e.g., "do not project beyond source"), implementations SHOULD verify projection elimination as a downstream metric.

---

## 6. Specification compliance verification

The Standard defines five layers of specification compliance verification. Implementations MUST implement Layers 1-4 to be conforming. Layer 5 is OPTIONAL.

### 6.1 Layer 1: Requirement extraction

REQUIRED. Extracts discrete requirements from a written specification using regex patterns for: lists, bullets, parenthetical labels (such as "(A1)..(A5)"), imperatives, constraints, format markers, structural labels.

Each extracted requirement MUST be classified by type per Section 6.4.

### 6.2 Layer 2: Coverage mapping

REQUIRED. For each extracted requirement, verifies output coverage using type-routed verification:

- TOPIC and IMPERATIVE: keyword overlap (with optional semantic upgrade per Layer 5)
- CONSTRAINT: dedicated constraint checker (negation and limit detection)
- FORMAT: format checker (structure detection)
- STRUCTURAL_LABEL: regex counting against expected labels
- QUALITY_CRITERION, META_INSTRUCTION, BEHAVIORAL: reported as unverifiable; not scored as coverage

Coverage decomposition MUST be reported as separate rates:
- `concrete_coverage_rate`: TOPIC + IMPERATIVE coverage
- `structural_compliance_rate`: STRUCTURAL_LABEL coverage
- `n_unverifiable`: count of requirements that cannot be automatically verified

A single inflated `coverage_rate` MUST NOT be used as the primary reported metric.

### 6.3 Layer 3: Scope drift

REQUIRED. Identifies output content not traceable to spec via section-level keyword absence. With Layer 5 enabled, embedding similarity upgrades drift assessment via cascade with default thresholds 0.60 (paraphrase recovery) and 0.55 (drift confirmation).

### 6.4 Requirement types

Eight requirement types are recognized:

| Type | Description | Verifier | Semantic upgrade eligible |
|------|-------------|----------|---------------------------|
| TOPIC | Content area requirement | Keyword overlap | Yes |
| IMPERATIVE | Must-do action requirement | Keyword overlap | Yes |
| CONSTRAINT | Boundary condition (negation/limit) | Constraint checker | No |
| FORMAT | Format requirement (structure) | Format checker | No |
| STRUCTURAL_LABEL | Labeled section requirement | Regex counting | No |
| QUALITY_CRITERION | Quality threshold (abstract) | Unverifiable; reported only | No |
| META_INSTRUCTION | Instruction-about-instruction | Unverifiable; reported only | No |
| BEHAVIORAL | Behavioral pattern (abstract) | Unverifiable; keyword overlap if attempted | No |

Only TOPIC and IMPERATIVE requirements are eligible for semantic upgrade in Layer 5. Abstract types (QUALITY_CRITERION, META_INSTRUCTION, BEHAVIORAL) MUST NOT receive semantic upgrades; embedding similarity to any same-topic content is unfalsifiable for these types.

### 6.5 Layer 4: Emphasis balance

REQUIRED. Computes Spearman rank correlation between output word allocation per requirement and spec ordering. Measures distribution alignment, not importance weighting.

### 6.6 Layer 5: Semantic coverage (opt-in)

OPTIONAL. Uses embedding similarity for synonym paraphrase recovery on TOPIC and IMPERATIVE requirements only. Cascade architecture: lexical pass first; MISSING or PARTIAL results upgraded only if eligible by type. ADDRESSED results checked for substance via causal/data marker density.

Implementations using Layer 5 MUST:
- Restrict semantic upgrades to TOPIC and IMPERATIVE types
- Document the embedding model used
- Provide graceful fallback to lexical-only if embedding service unavailable
- Flag substance warnings when keyword presence lacks supporting density

---

## 7. Threshold values and calibration discipline

Default threshold values are calibrated from reference distributions documented in this section.

### 7.1 Layer 4 (source matching)

Default unsourced rate threshold for "fabrication zone" classification: > 30%. Default threshold for "grounded zone": < 17%.

These thresholds reflect a binary diagnostic structure: source-grounded outputs cluster at 0-17% unsourced (median ~7%); source-absent outputs cluster at 31-81% (median ~47%). Within-zone variance is topic-driven.

### 7.2 Layer 6 (vocabulary proximity)

Default threshold for grounding signal in Layer 11: > 50% content word overlap with source.

### 7.3 Layer 8 (epistemic calibration)

Default precision threshold: assertion count >= 5 for inclusion in composite quality_profile.

### 7.4 Layer 10 (quality profile)

Quality gap interpretation:
- Gap > 0: overclaiming risk; presentation exceeds substance
- Gap < 0: understated quality; substance exceeds presentation
- Gap ≈ 0: balanced

Validated separation: source-grounded documents have gap mean -0.357; source-absent documents have gap mean +0.313. Threshold of 0 cleanly separates these conditions in calibration data.

### 7.5 Spec compliance thresholds

Default keyword overlap threshold for ADDRESSED classification: 60%. Calibrated against synthetic test pairs at 94% accuracy.

Default semantic upgrade threshold (Layer 5): 0.60 cosine similarity (paraphrase recovery) and 0.55 (drift confirmation).

### 7.6 Calibration discipline

Threshold values MUST:
- Be explicit and version-controlled
- Be overridable with documented justification
- Carry caveats noting calibration corpus and conditions
- Be revisited via the Suggestion process when reference distributions evolve

> **Operator finalization required.** Confirm or adjust threshold values for v1.0 ratification. Add additional thresholds for Layers 5, 7, 9, and Layer 1c (low-precision flag).

---

## 8. Reference test cases

> **Operator finalization required.** Specify canonical reference test suite for compliance.

The reference implementation `clarethium-touchstone` includes:
- 171 tests for output measurement (Layer 1-10)
- 19 additional tests for Layer 11 (G/F/P decomposition)
- 148 self-tests for specification compliance verification
- Cross-domain validation across product specifications, research summaries, code documentation
- Cross-generator validation across at least three model families (Anthropic, Gemini, OpenAI/xAI)

For v1.0 ratification, a minimal compliance test suite MUST be extracted into `tests/reference/` and versioned with the Standard. Implementations claiming conformance MUST pass all reference test cases at the Standard version they implement.

---

## 9. Implementation guidance

### 9.1 Conforming implementation requirements

A conforming implementation MUST:

- Implement Layers 1, 1b, 1c, 2, 3, 4, 5, 6, 7, 10 of output measurement (Section 5)
- Implement Layer 11 when source material is provided
- Implement Layers 1-4 of specification compliance (Section 6)
- Use threshold values from Section 7 as defaults
- Pass all reference test cases (Section 8)
- Document any threshold adjustments
- Report layers as per the output format specified in Section 5

A conforming implementation MAY:

- Implement Layer 1a (heading defaultness, requires LLM API)
- Implement Layers 8-9 (experimental in v1.0)
- Implement Layer 5 of specification compliance (semantic alignment)
- Add additional measurement layers as documented extensions
- Optimize for specific use cases with documented adjustments

### 9.2 Validated scope

The Standard's reference implementation has been validated on:
- Markdown analytical documents (strategic analysis, product specifications, research summaries, code documentation)
- Generators: Anthropic, Gemini, OpenAI, xAI/Grok families
- English language

Use outside this validated scope is explicitly OUT-OF-SCOPE for the Standard at version 1.0; conforming implementations MAY claim extended scope with documented validation.

### 9.3 Versioning of conformance claims

Implementations declare conformance to a specific Standard version (e.g., "Touchstone Standard 1.0-conformant"). Cross-version compatibility rules are defined in Section 10.

---

## 10. Versioning and evolution

The Standard follows semantic versioning:

- **Major (1.0 → 2.0):** Breaking changes to required layers, methodology, layer definitions, or normative threshold values. Existing implementations require updates to remain conformant.
- **Minor (1.0 → 1.1):** Additive changes — new optional layers, new requirement types, additional threshold defaults. Existing implementations remain conformant for the previous version.
- **Patch (1.0 → 1.0.1):** Editorial changes, clarifications, expanded examples. No methodology changes.

The deprecated `fabrication_rate` alias for `instability_rate` is retained at v1.0 for backwards compatibility and MUST be removed in v2.0.

Evolution is governed by the Suggestion process documented in `SUGGESTIONS/PROCESS.md` (modeled on PEP-1 / BIP-1).

---

## 11. Conformance

> **Operator finalization required.** Specify formal conformance process. Initial proposal: self-certification via passing reference test cases plus documentation of threshold adjustments. Year 2-3: optional formal certification by editor body.

---

## 12. References

> **Operator finalization required.** Add citations to underlying research:
> - EXP-078 through EXP-081 (fabrication and grounding studies)
> - EXP-084 (gaming resistance / Goodhart dynamics validation)
> - EXP-087 (alignment calibration)
> - EXP-088 (typed verifiers + semantic gating validation)
> - EXP-089 (binary diagnostic structure analysis)
> - EXP-094 (construct audit, instability vs fabrication rename)
> - EXP-095 (G/F/P decomposition origin)
> - AIRP R-series papers when published (R3 FVS canon, R4 methodology)

External references:

- RFC 2119 (Key words for use in RFCs to Indicate Requirement Levels)
- Creative Commons Attribution 4.0 International License (CC-BY 4.0)

Field positioning context (related approaches and their distinctions):

- **FActScore** (per-claim truth checking against external knowledge): different construct; LLM-heavy; truth-judging not generation profiling.
- **MiniCheck, HHEM, AlignScore** (semantic faithfulness sentence-level): different construct; semantic models; produces single score not decomposition.
- **SelfCheckGPT** (multi-sample consistency): adjacent to Layer 3; full-text NLI vs Touchstone's digit-formatted exact-match.
- **RAGAS, TruLens** (RAG pipeline evaluation): pipeline-scoped not output-scoped.
- **C2PA Content Credentials** (metadata-on-artifact): different layer entirely; signed provenance metadata not structural measurement.

---

## Appendix A: Worked examples

> **Operator finalization required.** Include 3-5 worked examples covering high-quality output passing all layers, output with detected fabrication, output with poor source grounding, spec compliance success and failure cases, edge cases requiring threshold adjustment.

---

## Appendix B: FAQ

> **Operator finalization required.** Anticipated questions to address:
> - How does this differ from LLM-as-judge approaches?
> - How does this differ from C2PA Content Credentials?
> - Can Touchstone be used with structured outputs (JSON, markup)?
> - What about non-English text?
> - What if my use case requires custom thresholds?
> - How do I report discrepancies in my implementation against reference test cases?
> - What is the relationship between Touchstone Standard and the `clarethium-touchstone` library?

---

## Appendix C: Implementation status

| Layer | Status in `clarethium-touchstone` v0.x |
|-------|----------------------------------------|
| 1a Heading defaultness | Implemented; conditional on Gemini API |
| 1b Mechanism ratio | Implemented; validated d=0.93 |
| 1c Assertion ratio | Implemented; validated d=0.83-0.95 |
| 2 Claim density | Implemented; validated 97% recall |
| 3 Temporal instability | Implemented; renamed from fabrication_rate v1.4 |
| 4 Source matching | Implemented; 0% FPR validated |
| 5 Entity provenance | Implemented; directional validation N=18 |
| 6 Vocabulary proximity | Implemented; directional validation N=18 |
| 7 Presentation features | Implemented; descriptive |
| 8 Epistemic calibration | Implemented; experimental v1.3 |
| 9 Information novelty | Implemented; experimental v1.3; length-confounded |
| 10 Quality profile | Implemented; validated across 4 studies |
| 11 G/F/P decomposition | Implemented v1.4; 19 tests passing |

| Spec Compliance Layer | Status in `clarethium-touchstone` v0.x |
|-----------------------|----------------------------------------|
| 1 Requirement extraction | Implemented; 8-type classification |
| 2 Coverage mapping | Implemented with type-routed verification |
| 3 Scope drift | Implemented; bidirectional |
| 4 Emphasis balance | Implemented; Spearman rank correlation |
| 5 Semantic coverage | Implemented; opt-in; embedding-based |

---

## Drafting status

Sections substantially complete (operator review only):

- Section 1 (Introduction)
- Section 3 (Substrate principles)
- Section 5 (Output measurement layers, all eleven)
- Section 6 (Specification compliance verification, all five layers)
- Section 9 (Implementation guidance)
- Section 10 (Versioning)
- Appendix C (Implementation status)

Sections requiring operator-authored finalization:

- Section 2 (Terminology — define key terms)
- Section 4 (Output structure — confirm scope)
- Section 7 (Threshold values — finalize specific numerical thresholds)
- Section 8 (Reference test cases — extract minimal compliance suite)
- Section 11 (Conformance — specify formal process)
- Section 12 (References — add EXP citations and AIRP coupling)
- Appendix A (Worked examples)
- Appendix B (FAQ)

The 12-week drafting target from FieldReceipts strategy aligns with completion of the operator-authored sections.
