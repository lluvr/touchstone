# Touchstone

Model-independent verification for AI-coupled work.

A Clarethium project. Standards and reference implementation for measuring AI output structure, fabrication, grounding, and specification compliance without depending on a model to judge a model.

## Start here

- [Touchstone Standard 1.0](../STANDARDS/touchstone-1.0.md) — the canonical specification (CC-BY 4.0)
- [Getting started](getting-started.md) — install and first measurement
- [Contributing](../CONTRIBUTING.md) — how to propose changes
- [Suggestion process](../SUGGESTIONS/PROCESS.md) — how Standard and library evolve

## Why model-independent

LLM-as-judge approaches use AI to evaluate AI output. Touchstone uses regex pattern matching, structural analysis, source comparison, and arithmetic. The substrate does not depend on the model being measured.

This matters when the auditor cannot be made of the same material as the audited. AI evaluating AI inherits the same biases, modes, and failures as the AI being evaluated. Touchstone breaks that loop by operating outside the model.

## What Touchstone measures

**Output measurement (eleven layers):**

| Layer | Construct | Source required |
|-------|-----------|-----------------|
| 1 | Structural profile (heading defaultness, mechanism ratio, assertion ratio) | Optional (Layer 1a only) |
| 2 | Claim density | No |
| 3 | Temporal instability across versions | Comparisons required |
| 4 | Source matching (numerical claims) | Yes |
| 5 | Entity provenance | Yes |
| 6 | Vocabulary proximity | Yes |
| 7 | Presentation features | No |
| 8 | Epistemic calibration | Yes |
| 9 | Information novelty | No |
| 10 | Quality profile (composite) | Optional |
| 11 | Grounding decomposition (G/F/P) | Yes |

**Specification compliance verification (five layers):**

| Layer | Construct |
|-------|-----------|
| 1 | Requirement extraction (8 types) |
| 2 | Coverage mapping (type-routed verification) |
| 3 | Scope drift |
| 4 | Emphasis balance |
| 5 | Semantic coverage (opt-in, embedding-based) |

See the [Touchstone Standard 1.0](../STANDARDS/touchstone-1.0.md) for full specifications.

## What Touchstone does NOT do

- Does not judge subjective quality
- Does not verify factual truth against external knowledge bases
- Does not detect malicious intent
- Does not replace human judgment about fitness for purpose
- Does not substitute for legal, medical, or domain-specific verification standards

## Use cases

- AI integrity research and benchmarking
- Internal AI quality verification at organizations
- Substrate enforcement for AI-coupled work platforms (used by FieldReceipts)
- Independent third-party verification of AI vendor claims
- Educational use in AI methodology courses

## Related projects

- [Clarethium](https://clarethium.com) — methodology umbrella, mothership
- [Frame Check](https://frame.clarethium.com) — applied tool for frame validation
- [FieldReceipts](https://fieldreceipts.com) — community platform using Touchstone substrate

## Status

Pre-launch. Standard 1.0 drafting in progress. Library extraction in progress. PyPI organization pending approval.

Expected first release: Q3 2026.

## License

- **Standard:** CC-BY 4.0
- **Library:** Apache 2.0

Both licenses permit commercial use with attribution.

## Citation

```
Touchstone Standard 1.0 (2026), Clarethium.
https://github.com/Clarethium/touchstone/blob/main/STANDARDS/touchstone-1.0.md
```

For library citation, see [CITATION.cff](../CITATION.cff).
