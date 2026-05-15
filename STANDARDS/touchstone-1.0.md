# Touchstone Standard 1.0 (DRAFT)

**Status:** Draft v0.6. All Section 4-12 content substantively complete, including Terminology (§2), Output structure (§4), Conformance declaration mechanism + invalidation criteria (§11), confirmed reference-test conformance bands (§8) disambiguated against the regression reference, structured Field positioning references (§12), falsifiable construct claims (§3.5) updated with the first external corpus result, and Appendix C citing public-surface validation artifacts only. Section 6 (Specification Compliance) and Appendices A and B remain reserved for Standard 1.1. Independent editor review is pending.
**Version:** 1.0.0-draft.6
**Date:** 2026-05-15 (drafting in progress)
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

Output measurement is designed to operate without invoking an AI model to score the output it measures. Layer 1a (optional) calls an LLM to generate baseline documents on the same topic, not to score the output. The remaining ten layers run on regex, structural analysis, string search, and arithmetic. This scoring substrate is independent of the model under measurement.

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

This document is a working draft of the canonical Touchstone Standard 1.0. Ratification follows maintainer completion of the sections currently marked pending, review through the Suggestion process documented in `SUGGESTIONS/PROCESS.md`, and (once constituted) editor-body sign-off per §11.

---

## 2. Terminology

The Standard uses RFC 2119 keywords (MUST, SHOULD, MAY, RECOMMENDED, OPTIONAL) per their conventional meanings throughout. The following terms have specific meanings in this Standard:

**Output.** A text artifact produced by an AI model in response to a prompt. The Standard's primary validated input format is Markdown analytical documents in English; conforming implementations claiming extended scope MUST document the validation supporting that claim (§9.2).

**Source.** A text artifact the Output may reference or derive content from. Source is optional for some layers and required for others (Layers 4, 5, 6, 8, 11 require source). The Standard makes no claim about the source's own correctness; it measures structural relationships between Output and Source.

**Claim.** A unit of asserted content extracted from an Output by a measurement layer. Layer 2 (claim density) and Layer 4 (source matching) extract digit-formatted numerical claims; Layer 5 (entity provenance) extracts named-entity claims. The Standard's extraction patterns are layer-specific and documented in §5.

**Evidence.** Material in the Source that supports a Claim. Evidence is established by exact string search (Layer 4 for numbers, Layer 5 for entities, lowercase substring), by structural derivation (Layer 11 for arithmetic combinations of source numbers), or by lexical overlap (Layer 6 for vocabulary proximity). The Standard does not establish semantic evidence; truth-judgment is out of scope (§1.3).

**Layer.** One of the eleven measurement constructs defined in §5. Each layer produces a structured output (specified by the layer's subsection) and is independently runnable; the composite quality_profile (Layer 10) aggregates a subset.

**Conforming implementation.** A software artifact that meets the requirements in §11 against a specific Standard version. Conformance is a property of an implementation paired with a Standard version (e.g., "Touchstone Standard 1.0-conformant"), not of the artifact alone.

**Threshold.** A numeric cutoff used by a layer to classify a measurement into bands (e.g., the Layer 4 unsourced_rate "fabrication zone" / "grounded zone" boundaries). Default thresholds are specified in §7. Implementations MAY adjust thresholds for their context but MUST document the adjustment (§7.5).

**Baseline generator.** For Layer 1a only: a callable that produces a baseline document on a given topic. Touchstone is vendor-neutral; callers supply their own implementation. The Standard does not specify which model class is appropriate; implementations SHOULD document the model class and prompting parameters used when reporting Layer 1a results.

**Regression baseline.** A pinned expected-value snapshot against which a measurement layer's output is checked for drift. The shipped benchmarks in `benchmarks/` are regression baselines (§8); they verify that the reference implementation has not drifted from previously-recorded behavior. They are not external replications and do not establish construct generalization beyond the packaged corpora.

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

### 3.5 Falsifiable construct claims

Each layer's construct claim is falsifiable in principle. The Standard names the evidence that would invalidate each:

- **Layer 4 (source matching).** Falsified if, on a corpus where every output's numerical claim is independently verified to exist verbatim in the source, the layer reports an unsourced_rate above 5% in aggregate. Recall is currently 97.1% on 70 manually annotated claims; a drop below the threshold indicates the extraction patterns no longer match the construct.
- **Layer 10 (quality_profile gap).** Falsified if, on a corpus where the faithful/embellished distinction has been independently re-annotated by a non-Clarethium party (e.g., a TRUE / LLM-AggreFact / HaluBench / HaluEval / RAGTruth subset), the gap signal fails to discriminate the two conditions at Cohen's d magnitude > 1.0 (a large effect). Status as of `1.0.0-draft.6`: **partially falsified out-of-domain.** On the RAGTruth Summary test split (n=900, MIT-licensed, multi-vendor; the `benchmarks/external/ragtruth_summary/` run), Layer 10 gap shows AUC-ROC 0.4981 against the per-output hallucination label, equivalent to d ≈ 0. The Layer 10 construct holds within its calibrated domain (long-form analytical Markdown with sufficient claim density) but does NOT generalize to short summary outputs: 97% of RAGTruth Summary outputs have zero substance components firing (`source_fidelity` 0.7%, `entity_grounding` 2.6%, `epistemic_calibration` 0.1%), so the composite reduces to presentation-only and carries no fidelity information. The Standard's scope statement (§9.2) is updated accordingly: Layer 10 gap's substrate-generalization claim is conditional on input regime, not unconditional.
- **Layer 11 (G/F/P decomposition).** Falsified if, on a corpus hand-classified by at least two independent annotators with documented inter-annotator agreement (Cohen's κ ≥ 0.7), the layer's P-existence direction agreement drops below 80%. The current 100% direction agreement is on a single-annotator corpus.
- **The "scoring substrate is independent" claim (§3.1).** Falsified if any non-Layer-1a layer's output is shown to depend on the choice of model that generated the input text in a way the layer's documented construct does not predict. The reference implementation runs identically on text from any generator; a measurement that shifts systematically with generator identity (beyond what Layer 1b/1c/10 are designed to surface) indicates an undocumented dependence. Status as of `1.0.0-draft.6`: on RAGTruth Summary, Touchstone's per-model AUC for Layer 6 (the strongest surviving signal out-of-domain) ranges 0.59-0.73 across six model families (gpt-3.5, gpt-4, llama-2-7B/13B/70B, mistral-7B). The variation is within the noise expected from the per-model hallucination-rate imbalance (3% to 57%); no systematic model-identity dependence is observed beyond what hallucination-rate variation would predict.

Reports of falsification evidence are submitted via the Suggestion process. A confirmed falsification of a layer's construct claim triggers either a Standard amendment (layer redefinition) or a layer retirement under the versioning rules of §10. A partial falsification (the construct holds in one regime but not another) triggers a §9.2 scope update rather than a layer retirement, as documented above for Layer 10.

---

## 4. Output structure

The Standard primarily addresses Markdown analytical documents. Reference implementation operates on this format; validated scope is documented in Section 9. Extension to structured outputs (JSON, structured markup) and to other text formats is layer-specific and MAY be implementation-defined; conforming implementations claiming extended scope MUST document the validation supporting that claim.

---

## 5. Output measurement layers

The Standard defines eleven measurement layers for output profiling. Implementations MUST implement Layers 1-7 and Layer 10 to be conforming. Layers 8-9 are EXPERIMENTAL in version 1.0; conforming implementations MAY include them. Layer 11 is REQUIRED when source material is provided; OPTIONAL otherwise.

### 5.1 Layer 1: Structural profile

The structural profile decomposes into three sub-layers measuring different structural dimensions:

**Layer 1a: Heading defaultness.** OPTIONAL. Generates baseline documents from a generic prompt (via a caller-supplied LLM client; the reference implementation accepts any vendor through a ``BaselineGenerator`` callable) and computes word-level Jaccard overlap between the document's headings and the baseline headings. Low overlap indicates non-default structure. This is the only layer with an LLM dependency.

**Layer 1b: Mechanism ratio.** REQUIRED. Counts regex matches against canonical causal-language patterns and buzzword patterns. Score = causal / (causal + buzzword). Measures reasoning style, not quality.

**Layer 1c: Assertion ratio.** REQUIRED. Counts epistemic register markers across five categories (ASSERTION, QUALIFIED, CONDITIONAL, EVIDENCED, SPECULATIVE). Score = ASSERTION / total. Operates on section bodies excluding headings. Implementations SHOULD flag low-precision results when total markers < 10.

### 5.2 Layer 2: Claim density

REQUIRED. Extracts sentences containing digit-formatted numbers (six pattern types: percentage, dollar amount, multiplier, entity count, duration, range) or causal markers. Reports counts per 1,000 words. Recall on digit-formatted numbers SHOULD exceed 95% on validated reference cases.

### 5.3 Layer 3: Temporal instability

REQUIRED when two or more independently generated versions of the output are provided. Extracts all digit-formatted numbers from the versions; classifies each unique (value, type) pair as stable (present in all versions) or unstable (present in only some). Instability rate = unstable / total. Implementations MUST filter year-like values and explicit word counts.

Note: Layer 3 measures instability, not fabrication directly. Instability is an upper bound on fabrication. A legacy `fabrication_rate` alias existed in pre-1.0 drafts; it was removed during greenfield cleanup before 1.0 and is not part of the Standard or reference implementation. The canonical field name is `instability_rate`.

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

Conservative P-detection is required for conformance to Standard 1.0. Implementations MAY add additional P-detection modes via the Suggestion process; such additions ship as Standard minor-version bumps per §10.

When a document includes an explicit prohibition recommendation (e.g., "do not project beyond source"), implementations SHOULD verify projection elimination as a downstream metric.

The set of external-entity P-markers (drug names, product names, indices, and similar domain-specific patterns that signal a sentence is introducing material not in the source) is a per-implementation configuration. The reference implementation ships a default list empirically seeded from its three benchmark source domains; implementations targeting other domains MUST document the entity set they use. The default list is exposed as a public constant in the reference implementation so adopter implementations can extend or replace it without monkey-patching.

---

## 6. Specification compliance verification

> **Reserved for Standard 1.1.** Verification of output coverage against a written specification (requirement extraction, type-routed coverage mapping, scope drift detection, emphasis balance, optional semantic alignment) is deferred to Standard 1.1. Reference implementation `clarethium-touchstone` v0.1 implements Section 5 only.

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

Reference test cases for Standard 1.0 are the internal regression benchmarks at `benchmarks/exp_081_discrimination/` and `benchmarks/exp_095_grounding/`, byte-pinned via pytest snapshot assertion in the reference implementation's CI. The benchmarks' corpora and expected values were authored by this project; they are regression baselines, not external replications.

**What the conformance bands assert.** Passing the bands in §8.1 and §8.2 asserts that a conforming implementation reproduces the reference implementation's behavior on the packaged corpora to within the stated tolerances. Passing does NOT assert construct generalization to other corpora, other vendors, or other model tiers; those are open research per §9.2. Implementations claiming extended construct validity MUST cite the validation supporting that claim per §9.2.

**Fast-tier corpus caveat.** Both benchmarks are validated on fast-tier model outputs (xAI grok-4-1-fast on EXP-081; gpt-4o, gemini-3-flash-preview, grok-4-1-fast on EXP-095). Construct generalization to flagship-tier models is open work. Signal may attenuate when stronger models decline embellishment instructions or produce content not surfaced by the deterministic signal set.

**Future reference suite.** A minimal conformance subset extracted into `tests/reference/` is reserved for Standard 1.0.1 ratification. Until then, the unit tests under `tests/` and the benchmark assertions under `benchmarks/` together are the conformance surface per §11.1(1).

### 8.1 EXP-081 adversarial discrimination

- Path: `benchmarks/exp_081_discrimination/`
- Corpus: 12 documents (faithful N=6, embellished N=6); single-vendor (xAI grok-4-1-fast)
- Reference result: Cohen's d = -5.238; the recorded expected values were produced by an earlier internal detector (`detector_v031`) at d = -5.43 (CI [-9.077, -4.681])
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

Cross-vendor and flagship-tier construct generalization is open work and is not asserted by passing these bands.

### 8.2 EXP-095 grounding decomposition

- Path: `benchmarks/exp_095_grounding/`
- Corpus: 13 hand-classified outputs; 3 source documents; 3 model families (gpt-4o, gemini-3-flash-preview, grok-4-1-fast)
- Reference result: P-direction agreement on existence (P>0 vs P=0) is 100% (13/13); aggregate MAE vs an earlier internal detector (`detector_v031`) is 0.02-0.04 across G/F/P. Aggregate MAE vs full manual classification (n=7 with complete annotations) is 0.12-0.13 across G/F/P. Per-output P-magnitude drift on 4/13 outputs is documented in the benchmark README.

Conformance bands (corpus-bound, proposed):

| Measurement | Required band |
|-------------|---------------|
| P-existence agreement on packaged corpus | 100% (13/13) |
| Aggregate G/F/P MAE vs `detector_v031` | ≤ 0.10 |

The MAE band is against the `detector_v031` reference recorded in `ground_truth.json` (regression baseline), not against full manual classification. Reference-implementation MAE vs full manual classification (0.12-0.13 across G/F/P) is documented in §8.2's Reference result and in the benchmark README; tightening that figure is open work and is not asserted by the band above.

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

The Standard's reference implementation has been internally validated on:
- Markdown analytical documents (financial summaries, product analyses, research summaries)
- Generators on the two shipped benchmarks: EXP-081 is single-vendor (xAI grok-4-1-fast, 12 documents); EXP-095 covers three vendors at fast-tier scale (gpt-4o, gemini-3-flash-preview, grok-4-1-fast). Construct generalization to flagship-tier model outputs and to vendors not in the EXP-095 set is open research; signal may attenuate when stronger models decline embellishment instructions or produce content not surfaced by the deterministic signal set.
- English language

Use outside this internally-validated scope is explicitly OUT-OF-SCOPE for the Standard at version 1.0; conforming implementations MAY claim extended scope with documented validation.

### 9.3 Versioning of conformance claims

Implementations declare conformance to a specific Standard version (e.g., "Touchstone Standard 1.0-conformant"). Cross-version compatibility rules are defined in Section 10.

---

## 10. Versioning and evolution

The Standard follows semantic versioning:

- **Major (1.0 → 2.0):** Breaking changes to required layers, methodology, layer definitions, or normative threshold values. Existing implementations require updates to remain conformant.
- **Minor (1.0 → 1.1):** Additive changes - new optional layers, new requirement types, additional threshold defaults. Existing implementations remain conformant for the previous version.
- **Patch (1.0 → 1.0.1):** Editorial changes, clarifications, expanded examples. No methodology changes.

Evolution is governed by the Suggestion process documented in `SUGGESTIONS/PROCESS.md` (modeled on PEP-1 / BIP-1).

---

## 11. Conformance

### 11.1 Conformance requirements

Conformance is by self-certification. An implementation is conformant against Standard 1.0 when it:

1. **Passes the conformance surface**, defined as: every unit test under `tests/` and every benchmark assertion under `benchmarks/` of the reference implementation at the Standard's published commit. Standard 1.0.1 will extract a representative subset into `tests/reference/` as the canonical conformance suite; until 1.0.1 ships, `tests/` and `benchmarks/` together are the conformance surface.
2. **Documents threshold adjustments.** Any deviation from the default thresholds in §7 MUST be documented at the point the implementation exposes its results (config file, API surface, or report). The documentation MUST state the original default, the adjusted value, and the rationale.
3. **Declares the Standard version.** The implementation MUST surface the Standard version it implements through whatever interface it exposes to callers. The reference implementation surfaces this through the `standard_version` field of `MeasureResult` and the `__standard_version__` module attribute.

### 11.2 Declaration mechanism

A conforming implementation declares conformance in the form:

> "<implementation-name> <version> conforms to Touchstone Standard <version>."

The declaration MUST be visible in at least one of: the implementation's README, its package metadata, or its API output. Implementations MAY additionally publish their conformance verification (e.g., CI logs from running the conformance surface).

There is no central registry of conforming implementations at Standard 1.0. Implementations self-declare; verification is by anyone running the conformance surface against the implementation.

### 11.3 Invalidation criteria

A conformance claim is invalidated when any of the following is true:

- The implementation fails any test in the conformance surface at the declared Standard version.
- The implementation uses thresholds that diverge from §7 defaults without documenting the adjustment per §11.1(2).
- The implementation misrepresents the Standard version it conforms to (e.g., claims Standard 1.0 but implements only a subset of the required layers per §5).
- The implementation modifies the structure of a layer's output dict (per the TypedDicts in `clarethium_touchstone.types`) without declaring an extension per §9.1.

Discovery of an invalidating discrepancy SHOULD be reported via the Suggestion process for resolution; the resolution is either a Standard amendment (if the Standard is ambiguous), a reference-implementation fix (if the reference is wrong), or a withdrawal of the conformance claim (if the implementation is wrong).

### 11.4 Transitional state at Standard 1.0-draft

Until an editor body is constituted, the conformance surface at §11.1(1) is authored by the same maintainers who author the Standard. Self-certification against this surface is consistency with the reference implementation's current behavior, not independent verification. A second-party implementation that diverges from the reference surface indicates either an implementation defect or a Standard ambiguity, both of which route through the Suggestion process for resolution.

Optional formal certification by an editor body is reserved for a future Standard version once an editor body is constituted.

---

## 12. References

### 12.1 Internal regression benchmarks shipped with this Standard

| ID | Path | Construct | Corpus |
|----|------|-----------|--------|
| EXP-081 | `benchmarks/exp_081_discrimination/` | Adversarial discrimination between faithful and embellished AI outputs against the same source | 12 documents (6 faithful, 6 embellished); single-vendor xAI grok-4-1-fast |
| EXP-095 | `benchmarks/exp_095_grounding/` | Layer 11 G/F/P decomposition agreement with manual classification | 13 hand-classified outputs; 3 source documents; 3 model families (gpt-4o, gemini-3-flash-preview, grok-4-1-fast) |

Both benchmarks ship with `README.md` files documenting methodology, expected values, and known drift; both are byte-pinned via pytest snapshot assertion (§8).

### 12.2 Normative external references

- **RFC 2119.** Key words for use in RFCs to Indicate Requirement Levels (Bradner, 1997). https://www.rfc-editor.org/rfc/rfc2119
- **CC-BY 4.0.** Creative Commons Attribution 4.0 International License. https://creativecommons.org/licenses/by/4.0/

### 12.3 Field positioning

Touchstone occupies a different construct space from existing AI-output evaluation methodologies. Distinctions are not value judgments; they describe what each approach measures.

| Approach | What it measures | How it differs from Touchstone |
|----------|------------------|--------------------------------|
| FActScore (Min et al., EMNLP 2023) | Atomic-claim truth against an external knowledge base | LLM-based truth-judging; needs a KB, not a source document |
| MiniCheck (Tang et al., EMNLP 2024) | Fine-tuned model fact-checking against grounding documents | Semantic NLI-style model output; not regex/structural |
| HHEM 2.1 (Vectara) | Factual consistency probability against evidence | Cross-encoder model; single scalar output |
| AlignScore (Zha et al., ACL 2023) | Unified alignment function across 7 tasks | Small discriminator model; not a generative judge but still a learned function |
| SelfCheckGPT (Manakul et al., EMNLP 2023) | Multi-sample consistency for hallucination detection | NLI-based over multiple samples; zero-source, where Touchstone Layer 3 needs source-anchored digit comparison |
| RAGAS (Es et al., EACL 2024) / TruLens | RAG pipeline evaluation (faithfulness, relevancy, retrieval quality) | Pipeline-scoped; assumes a retrieval step |
| G-Eval (Liu et al., EMNLP 2023) | LLM-as-judge with chain-of-thought | The category Touchstone explicitly does not implement |
| HaluEval (Li et al., EMNLP 2023) / HaluBench (Patronus, 2024) | Annotated hallucination corpora and detection benchmarks | External corpora the Standard's construct claims have not yet been benchmarked against; see §Limitations of the reference implementation README |
| C2PA Content Credentials | Signed provenance metadata on the artifact | Different layer entirely (metadata, not text-content measurement) |

### 12.4 Validation work cited in the reference implementation

Additional empirical work referenced in the reference implementation's docstrings and benchmark READMEs is documented at the point of use. Formal citations for any such work that publishes externally will land as Standard 1.0.1 editorial patches.

---

## Appendix A: Worked examples

> **Reserved for Standard 1.1.** Worked examples (high-quality output passing all layers; output with detected fabrication; output with poor source grounding; edge cases requiring threshold adjustment) are deferred to Standard 1.1, to be authored from corpus material rather than synthesised in advance.

---

## Appendix B: FAQ

> **Reserved for Standard 1.1.** Frequently-asked questions are deferred to Standard 1.1, to be authored from real implementer questions surfaced after Standard 1.0 release rather than from anticipated questions in advance.

---

## Appendix C: Implementation status

The table below records each layer's status in the reference implementation. "Validation in public surface" cites the artifacts in this repository that exercise the layer. Layers without a public validation artifact are implemented and unit-tested; their construct claims are open work per §3.5.

| Layer | Status in `clarethium-touchstone` v0.x | Validation in public surface |
|-------|----------------------------------------|------------------------------|
| 1a Heading defaultness | Implemented; runs only when caller supplies both `topic` and a vendor-neutral `BaselineGenerator` callable | Unit tests (`tests/test_structural_profile.py`) cover stub-generator paths: full overlap, disjoint, failed calls, partial exceptions, non-string returns |
| 1b Mechanism ratio | Implemented | Unit tests in `tests/test_structural_profile.py` |
| 1c Assertion ratio | Implemented; precision banding (high / adequate / low) on `assertion_precision` output field | Unit tests in `tests/test_structural_profile.py`; precision-band classifier covered |
| 2 Claim density | Implemented | Unit tests in `tests/test_claim_density.py` |
| 3 Temporal instability | Implemented; canonical field name is `instability_rate` | Unit tests in `tests/test_temporal_instability.py` |
| 4 Source matching | Implemented; 97.1% extraction recall on 70 manually annotated digit-formatted claims (internal annotation set, 3 documents × 6 categories); 0/309 numbers incorrectly flagged unsourced on self-source documents (string-equality regression check, not independent validation against an external faithfulness corpus) | Unit tests in `tests/test_source_matching.py`; component of `quality_profile.gap` exercised by EXP-081 |
| 5 Entity provenance | Implemented | Unit tests in `tests/test_entity_provenance.py`; component of `quality_profile` exercised by EXP-081 |
| 6 Vocabulary proximity | Implemented | Unit tests in `tests/test_vocabulary_proximity.py`; used as a grounding signal in Layer 11 |
| 7 Presentation features | Implemented; descriptive (no normative pass/fail thresholds per §7.5) | Unit tests in `tests/test_presentation_features.py`; presentation-side components exercised by EXP-081 |
| 8 Epistemic calibration | Implemented; EXPERIMENTAL in v1.0 (§5.8); precision flag when assertion count < 5 | Unit tests in `tests/test_epistemic_calibration.py`; substance-index contributor exercised by EXP-081 |
| 9 Information novelty | Implemented; EXPERIMENTAL in v1.0; length-confounded by Heaps' law per §5.9 | Unit tests in `tests/test_information_novelty.py` |
| 10 Quality profile | Implemented; composite of L3/L4/L5/L8 (substance) and L7 (presentation), with L1a `structural_effort` reserved until LLM-baseline runs are wired into the composite | EXP-081 (`benchmarks/exp_081_discrimination/`) records Cohen's d = -5.238 on 12 single-vendor documents against the `detector_v031` reference of d = -5.43; per-output gap-direction agreement 100% (12/12). Internal regression baseline; not external replication. |
| 11 G/F/P decomposition | Implemented; conservative P-detection (§5.11); domain-biased default external-entity P-marker list with `external_entities` extension hook | EXP-095 (`benchmarks/exp_095_grounding/`) records P-existence direction agreement 100% (13/13) across 3 model families; aggregate G/F/P MAE 0.02-0.04 vs `detector_v031`, 0.12-0.13 vs full manual classification (n=7). Unit tests in `tests/test_grounding_decomposition.py`. |

---

## Drafting status

Sections substantively complete:

- Section 1 (Introduction)
- Section 2 (Terminology)
- Section 3 (Substrate principles, including §3.5 falsification protocol)
- Section 4 (Output structure)
- Section 5 (Output measurement layers, all eleven)
- Section 7 (Thresholds and calibration discipline)
- Section 8 (Reference test cases, with explicit normative framing)
- Section 9 (Implementation guidance)
- Section 10 (Versioning)
- Section 11 (Conformance, including declaration mechanism and invalidation criteria)
- Section 12 (References, with structured field-positioning)
- Appendix C (Implementation status)

All sections of Standard 1.0 have substantive content. The "draft" qualifier on the version string is retained to flag that the Standard has not yet undergone independent editor review; the maintainers continue to invite Suggestion-process contributions.

Reserved for Standard 1.1:

- Section 6 (Specification compliance verification)
- Appendix A (Worked examples)
- Appendix B (FAQ)

Reserved for Standard 1.0.1 patch:

- Minimal conformance subset extraction to `tests/reference/`
- AIRP R-series citations (gated on R-series papers publishing)
