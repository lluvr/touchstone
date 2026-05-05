# Touchstone Standard 1.0 (DRAFT)

**Status:** Draft v0.3. Scope-tightening pass complete (Section 6 deferred to Standard 1.1; Appendices A and B deferred to 1.1; Sections 4, 7, 8, 9.2, 12 settled). Sections 2 (Terminology) and 11 (Conformance) require operator authoring before ratification.
**Version:** 1.0.0-draft.3
**Date:** 2026-05-05 (drafting in progress)
**License:** CC-BY 4.0
**Canonical URL:** https://github.com/Clarethium/touchstone/blob/main/STANDARDS/touchstone-1.0.md

---

## Abstract

Touchstone Standard defines a model-independent methodology for verifying the structural quality, source grounding, and fabrication characteristics of AI-coupled work outputs. The Standard specifies eleven measurement layers for output profiling, calibration discipline, threshold conventions, and conformance requirements. Of the eleven measurement layers, ten use deterministic regex pattern matching, string analysis, and arithmetic; one uses optional LLM API for baseline generation. The Standard does not depend on AI models judging AI outputs. Specification compliance verification is reserved for Standard 1.1.

---

## 1. Introduction

### 1.1 Purpose

The Standard provides a verifiable methodology for measuring AI-coupled work. The Standard defines:

- **Output measurement** (Section 5): profiling structural quality, claim density, source grounding, fabrication characteristics, presentation features, and grounding decomposition of AI-generated text against optional source material.

Output measurement is designed to operate without depending on a separate AI model to judge correctness. The Standard rests on the principle that an auditor cannot be made of the same material as the audited; AI evaluating AI inherits structural conflicts of interest.

Specification compliance verification (extracting requirements from a written specification and verifying that an output addresses them) is reserved for Standard 1.1.

### 1.2 Scope

The Standard covers:

- Eleven measurement layers for output profiling (Section 5)
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
- Platforms hosting AI-coupled work

### 1.5 Status of this document

This document is a working draft of the canonical Touchstone Standard 1.0. Ratification follows operator-authored completion of remaining sections, editor-body review, and the Suggestion process documented in `SUGGESTIONS/PROCESS.md`.

---

## 2. Terminology

> **Operator finalization required.** Define key terms used throughout, including: Build, output, source, spec, claim, evidence, layer, conforming implementation. RFC 2119 keywords (MUST, SHOULD, MAY, RECOMMENDED, OPTIONAL) are used per their conventional meanings throughout this Standard.

---

## 3. Substrate principles

The Standard rests on four principles that distinguish it from LLM-as-judge approaches.

### 3.1 Model-independence

All required measurements MUST be performable without invoking an AI model to evaluate the output. Layer 1a (heading defaultness) MAY use AI for ancillary tasks; this layer is explicitly OPTIONAL. The core measurement methodology MUST function without AI when source material is deterministic.

### 3.2 Structural over semantic

Measurements prioritize structural properties (presence of citations, claim density, source matching via string search, vocabulary proximity, format compliance) over semantic judgment (is this claim true). Structural properties are reproducible across implementations and time-stable.

### 3.3 Calibrated thresholds

Threshold values for accept/reject decisions MUST be explicit, versioned, and overridable. Default thresholds are specified in Section 7. Implementations and applications MAY adjust thresholds for their context but MUST document the adjustment.

### 3.4 Open and verifiable

The Standard, its threshold values, and its reference test cases are public. Conforming implementations MAY be open or proprietary; the Standard itself remains under CC-BY 4.0.

---

## 4. Output structure

The Standard primarily addresses Markdown analytical documents. Reference implementation operates on this format; validated scope is documented in Section 9. Extension to structured outputs (JSON, structured markup) and to other text formats is layer-specific and MAY be implementation-defined; conforming implementations claiming extended scope MUST document the validation supporting that claim.

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

> **Reserved for Standard 1.1.** Verification of output coverage against a written specification (requirement extraction, type-routed coverage mapping, scope drift detection, emphasis balance, optional semantic alignment) is deferred to Standard 1.1. Reference implementation `clarethium-touchstone` v0.1 implements Section 5 only; the canonical research substrate for this section lives in the operator's vault as `clarethium_align.py` and is not yet packaged for release.

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

### 7.5 Calibration discipline

Threshold values MUST:
- Be explicit and version-controlled
- Be overridable with documented justification
- Carry caveats noting calibration corpus and conditions
- Be revisited via the Suggestion process when reference distributions evolve

Layers 5, 7, and 9 do not carry normative pass/fail thresholds at Standard 1.0: Layer 5 is at directional validation only, Layer 7 is descriptive-not-pass/fail per Section 5.7, and Layer 9 is experimental and length-confounded per Section 5.9. Layer 1c precision-flag bands (high / adequate / low) are documented in the reference implementation's `assertion_precision` output field.

---

## 8. Reference test cases

> **Operator finalization required.** Confirm conformance bands in §8.1 and §8.2 below; author normative framing for what the conformance test asserts (reproduction on the packaged corpus vs construct generalization to other corpora) and the fast-tier-corpus caveat (signal validated on fast-tier model outputs; flagship-tier construct generalization is open research). A minimal conformance subset extracted into `tests/conformance/` is reserved for Standard 1.0.1.

For v1.0, reference test cases are the published reproducibility benchmarks at `benchmarks/exp_081_discrimination/` and `benchmarks/exp_095_grounding/`. Both are byte-pinned via pytest snapshot assertion in the reference implementation's CI. Implementations claiming conformance MUST pass the bands declared at the Standard version they implement.

### 8.1 EXP-081 adversarial discrimination

- Path: `benchmarks/exp_081_discrimination/`
- Corpus: 12 documents (faithful N=6, embellished N=6); fast-tier model variants from Anthropic, Gemini, OpenAI, and xAI/Grok families
- Reference result: Cohen's d = -5.238 vs published d = -5.43 (CI [-9.077, -4.681])
- Reference per-output MAE: unsourced_rate 0.014, gap 0.010, substance 0.010, presentation 0.000
- Per-output gap-direction agreement: 100% (12/12)

Conformance bands (corpus-bound, proposed):

| Measurement | Required band |
|-------------|---------------|
| Cohen's d on packaged corpus | -5.238 ± 0.5 |
| Per-output gap-direction agreement | 100% (12/12) |
| Per-output MAE: unsourced_rate | ≤ 0.05 |
| Per-output MAE: gap | ≤ 0.05 |
| Per-output MAE: substance | ≤ 0.05 |

### 8.2 EXP-095 grounding decomposition

- Path: `benchmarks/exp_095_grounding/`
- Corpus: 13 hand-classified outputs; 3 source documents; 3 model families
- Reference result: P-direction agreement on existence (P>0 vs P=0) is 100% (13/13); aggregate MAE vs detector v0.3.1 is 0.02-0.04 across G/F/P; per-output P-magnitude drift on 4/13 outputs is documented in benchmark README

Conformance bands (corpus-bound, proposed):

| Measurement | Required band |
|-------------|---------------|
| P-existence agreement on packaged corpus | 100% (13/13) |
| Aggregate G/F/P MAE | ≤ 0.10 |

---

## 9. Implementation guidance

### 9.1 Conforming implementation requirements

A conforming implementation MUST:

- Implement Layers 1, 1b, 1c, 2, 3, 4, 5, 6, 7, 10 of output measurement (Section 5)
- Implement Layer 11 when source material is provided
- Use threshold values from Section 7 as defaults
- Pass all reference test cases (Section 8)
- Document any threshold adjustments
- Report layers as per the output format specified in Section 5

A conforming implementation MAY:

- Implement Layer 1a (heading defaultness, requires LLM API)
- Implement Layers 8-9 (experimental in v1.0)
- Add additional measurement layers as documented extensions
- Optimize for specific use cases with documented adjustments

### 9.2 Validated scope

The Standard's reference implementation has been validated on:
- Markdown analytical documents (strategic analysis, product specifications, research summaries, code documentation)
- Generators: fast-tier model variants from Anthropic, Gemini, OpenAI, and xAI/Grok families. Construct generalization to flagship-tier model outputs is open research; signal may attenuate when stronger models reject the embellishment prompt or produce sophisticated content not tripped by the simpler signals.
- English language

Use outside this validated scope is explicitly OUT-OF-SCOPE for the Standard at version 1.0; conforming implementations MAY claim extended scope with documented validation.

> **Operator finalization required.** Confirm or refine the fast-tier qualifier and flagship-tier caveat phrasing above. The qualifier is load-bearing for honest scope claim against future flagship-model corpora.

### 9.3 Versioning of conformance claims

Implementations declare conformance to a specific Standard version (e.g., "Touchstone Standard 1.0-conformant"). Cross-version compatibility rules are defined in Section 10.

---

## 10. Versioning and evolution

The Standard follows semantic versioning:

- **Major (1.0 → 2.0):** Breaking changes to required layers, methodology, layer definitions, or normative threshold values. Existing implementations require updates to remain conformant.
- **Minor (1.0 → 1.1):** Additive changes - new optional layers, new requirement types, additional threshold defaults. Existing implementations remain conformant for the previous version.
- **Patch (1.0 → 1.0.1):** Editorial changes, clarifications, expanded examples. No methodology changes.

The deprecated `fabrication_rate` alias for `instability_rate` is retained at v1.0 for backwards compatibility and MUST be removed in v2.0.

Evolution is governed by the Suggestion process documented in `SUGGESTIONS/PROCESS.md` (modeled on PEP-1 / BIP-1).

---

## 11. Conformance

> **Operator finalization required.** Specify formal conformance process. Initial proposal: self-certification via passing reference test cases plus documentation of threshold adjustments. Year 2-3: optional formal certification by editor body.

---

## 12. References

> **Operator finalization required.** Convert the EXP-series research below into formal citations. Reproductions of EXP-081 and EXP-095 ship in this repository at `benchmarks/`. AIRP R-series coupling is deferred to Standard 1.0.1 patch (citations require the R-series papers to publish first; ratification cannot block on external dependency).
>
> - EXP-078 through EXP-081 (fabrication and grounding studies)
> - EXP-084 (gaming resistance / Goodhart dynamics validation)
> - EXP-087 (alignment calibration)
> - EXP-088 (typed verifiers + semantic gating validation)
> - EXP-089 (binary diagnostic structure analysis)
> - EXP-094 (construct audit, instability vs fabrication rename)
> - EXP-095 (G/F/P decomposition origin)

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

> **Reserved for Standard 1.1.** Worked examples (high-quality output passing all layers; output with detected fabrication; output with poor source grounding; edge cases requiring threshold adjustment) are deferred to Standard 1.1, to be authored from corpus material rather than synthesised in advance.

---

## Appendix B: FAQ

> **Reserved for Standard 1.1.** Frequently-asked questions are deferred to Standard 1.1, to be authored from real implementer questions surfaced after Standard 1.0 release rather than from anticipated questions in advance.

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

---

## Drafting status

Sections substantively complete:

- Section 1 (Introduction)
- Section 3 (Substrate principles)
- Section 4 (Output structure)
- Section 5 (Output measurement layers, all eleven)
- Section 7 (Thresholds and calibration discipline)
- Section 9 (Implementation guidance, with §9.2 fast-tier qualifier pending operator confirmation)
- Section 10 (Versioning)
- Appendix C (Implementation status)

Sections requiring operator authoring before ratification:

- Section 2 (Terminology: output, source, claim, evidence, layer, conforming implementation)
- Section 8 (Reference test cases: confirm conformance bands, author normative framing for corpus-bound conformance and fast-tier-corpus caveat)
- Section 11 (Conformance: self-certification process, declaration mechanism, what invalidates a claim)
- Section 12 (References: convert EXP-series list into formal citations)

Reserved for Standard 1.1:

- Section 6 (Specification compliance verification)
- Appendix A (Worked examples)
- Appendix B (FAQ)

Reserved for Standard 1.0.1 patch:

- Minimal conformance subset extraction to `tests/conformance/`
- AIRP R-series citations (gated on R-series papers publishing)
