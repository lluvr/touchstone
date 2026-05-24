# Touchstone

Hallucination detection for LLM outputs — without calling another LLM.

A Clarethium project. Standard and reference implementation for measuring LLM-generated text against its source: structural quality, claim density, source matching, grounding decomposition, and other layers. The scoring substrate is regex, structural analysis, source matching, and arithmetic; no model is called to judge another model's output. Specification compliance verification is reserved for Standard 1.1.

## Start here

- [Touchstone Standard 1.0](../STANDARDS/touchstone-1.0.md) - the canonical specification (CC-BY 4.0)
- [Getting started](getting-started.md) - install and first measurement
- [API reference](api-reference.md) - the public Verifier / measure / scope surface
- [Production readiness](production_readiness.md) - operational metrics, threshold guidance, what Touchstone is and is not for production deployment
- [Methodology summary](methodology.md) - substrate hypothesis, falsification protocol, cross-corpus evidence, caveats (intended for readers evaluating Touchstone for adoption or methodological critique)
- [Touchstone MCP](mcp.md) - Model Context Protocol server; host wiring for Claude Desktop / Claude Code / Cursor / custom hosts
- [Contributing](../CONTRIBUTING.md) - how to propose changes
- [Suggestion process](../SUGGESTIONS/PROCESS.md) - how Standard and library evolve

## Install

```bash
pip install clarethium-touchstone                  # base library
pip install touchstone-mcp                         # MCP server (separate distribution)
```

## Why model-independent

LLM-as-judge approaches use a model to evaluate a model's output. Touchstone's scoring functions are regex, structural analysis, string search, and arithmetic; they do not invoke an LLM on the output being measured. Layer 1a (optional) calls an LLM to generate baseline documents on the same topic, not to score the output. The scoring substrate is independent of the model under measurement.

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

**Specification compliance verification:** reserved for Standard 1.1.
Section 6 of the Standard is a placeholder in v1.0; the `align()` API is
not part of the v0.1 library and the per-layer breakdown will land with
1.1 when the methodology is settled.

See the [Touchstone Standard 1.0](../STANDARDS/touchstone-1.0.md) for full specifications.

## What Touchstone does NOT do

- Does not judge subjective quality
- Does not verify factual truth against external knowledge bases
- Does not detect malicious intent
- Does not replace human judgment about fitness for purpose
- Does not substitute for legal, medical, or domain-specific verification standards

## Use cases

What this release has been exercised on:

- Regression testing of AI-output verification implementations (the bundled benchmarks demonstrate this).
- Research-style profiling of analytical documents against their sources.

Plausibly suited but not yet validated against an externally curated corpus:

- AI integrity research and benchmarking, including head-to-head comparison against published faithfulness metrics.
- Educational use in AI methodology courses where the regex-and-arithmetic substrate is the pedagogical point.

NOT yet a production claim (see README §Limitations):

- Internal AI-quality verification at organizations operating at scale (no batch API, no performance characterization).
- Substrate enforcement on platforms that host LLM-generated content (no adversarial-robustness claim; patterns are public and evadable).
- Independent third-party verification of AI vendor claims (no external-corpus validation; no head-to-head baselines).

## Related projects

- [Clarethium](https://clarethium.com) - methodology umbrella, mothership
- [Frame Check](https://frame.clarethium.com) - applied tool for frame validation

Published on PyPI as [`clarethium-touchstone`](https://pypi.org/project/clarethium-touchstone/).
All eleven Section 5 measurement layers are implemented and tested
(469 tests; CI green on ruff lint + format, mypy strict, and the
pytest matrix across Python 3.10/3.11/3.12). Test coverage is at 97%
with a 95% CI gate. Two internal regression benchmarks plus three
external corpus comparisons ship in `benchmarks/`. Internal: EXP-081
(Cohen's d = -5.238 on a 12-document single-vendor corpus, vs the
recorded `detector_v031` baseline of -5.43) and EXP-095 (P-existence
direction agreement 100% on 13 outputs). External: RAGTruth Summary,
SummEval, HaluEval summarization (n totals 900 / 1600 / 1000;
permissively licensed; the runners stream from HuggingFace Hub at
runtime). The cross-corpus Touchstone signal pattern is internally
consistent across three corpora and three task types, with 95%
percentile bootstrap CIs reported per signal; see the main README
§Empirical validation. Validation against TRUE, LLM-AggreFact held-out,
and HaluBench remains open work.

Section 6 (Specification Compliance) is reserved for Standard 1.1.
See [Getting started](getting-started.md) for install and first usage.

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
