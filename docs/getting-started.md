# Getting started

This guide covers installation, basic usage, and first measurements with the
`clarethium-touchstone` library.

> **Status:** v0.1 ships Section 5 measurement only. All eleven measurement
> layers (Standard Section 5) are implemented and tested with empirical
> validation against the published EXP-081 adversarial-validity finding
> (Cohen's d = -5.43 reproduced). Section 6 (Specification Compliance) is
> reserved for a future release; the `align()` API is not part of v0.1.

## Installation

When the package is published to PyPI:

```bash
pip install clarethium-touchstone
```

The library is dependency-free. Layer 1a (heading defaultness) accepts a
caller-supplied LLM client via a `BaselineGenerator` callable, so no
provider SDK is required to install.

For development (running tests, linting):

```bash
pip install "clarethium-touchstone[dev]"
```

Until PyPI publication, install from source:

```bash
git clone https://github.com/Clarethium/touchstone.git
cd touchstone
pip install -e .
```

## First measurement

Profile an AI-generated output against source material:

```python
from clarethium_touchstone import measure

text = "Revenue grew 12% to $143M with 25% margins reported."
source = "Revenue grew 12% to $143M with 25% margins."

result = measure(text, source=source)

# Layer 4: number provenance
result["source_matching"]["unsourced_rate"]   # 0.0 — every number in source

# Layer 11: per-sentence Grounded / Framed / Projected decomposition
result["grounding_decomposition"]["proportions"]   # {"G": 1.0, "F": 0.0, "P": 0.0}
result["grounding_decomposition"]["has_projection"]  # False
```

The composite `quality_profile` (Layer 10) requires at least 10 numbers in
text for `source_fidelity` to qualify (vault precision threshold). For the
substance vs presentation gap signal, supply a longer document:

```python
text = (
    "Revenue grew 12% to $143M with 25% margins reported. "
    "Costs declined 8% across 5,000 employees over 18 months. "
    "Headcount reached 2,500 with $45,000 average compensation paid. "
    "Customer acquisition cost dropped to $1,200 from baseline. "
    "Retention improved 7.5% to 94.2% across all major segments."
)

result = measure(text, source=text)
result["quality_profile"]["substance_index"]    # 1.0 (self-source)
result["quality_profile"]["gap"]                # -0.54
```

## Layer 1a (heading defaultness)

Layer 1a is the only layer that requires an LLM. The library ships
vendor-neutral via a callable injection, so you supply your own client:

```python
def baseline_generator(prompt: str) -> str | None:
    # Your LLM call. Return generated text or None on failure.
    return your_llm_client.generate(prompt, temperature=1.0)

result = measure(
    text,
    source=source,
    topic="quarterly earnings analysis",
    baseline_generator=baseline_generator,
)
result["structural_profile"]["heading_defaultness"]
# {"jaccard_overlap": 0.33, "is_default": False, "n_baseline_documents": 3}
```

When `topic` or `baseline_generator` is missing, `heading_defaultness` is
`None` and the rest of `structural_profile` (mechanism ratio, assertion
ratio) runs normally on text alone.

## Layer 11 scope assessment

Layer 11's derivation checker saturates as the source's unique-number count
grows. The `scope_assessment` field tells consumers which signal to trust:

```python
from clarethium_touchstone import assess_derivation_regime

assessment = assess_derivation_regime(source_num_count=14)
assessment["derivation_regime"]                      # "saturated"
assessment["cross_reference_layer_4_for_numbers"]    # True
assessment["note_user_facing"]                       # UX-safe explanation
```

Boundaries are validated against the EXP-095 Monte Carlo data:

| Source unique numbers | Regime | Primary P-signal |
|---|---|---|
| < 5 | diagnostic | Reliable |
| 5–9 | transition | Cross-reference Layer 4 |
| ≥ 10 | saturated | Trust Layer 4 for numerical fabrication |

The same dict is returned as `result["grounding_decomposition"]["scope_assessment"]`
on every Layer 11 call, so consumers don't need to compute it separately
unless they want a pre-measurement hint.

## Individual layer functions

When you only need one specific measurement:

```python
from clarethium_touchstone.measure import (
    source_matching,
    grounding_decomposition,
    structural_profile,
)

# Single layer use
sourcing = source_matching(text, source)
gfp = grounding_decomposition(text, source)
profile = structural_profile(text)
```

All eleven layer functions are accessible via `clarethium_touchstone.measure`.
See the [Touchstone Standard 1.0](../STANDARDS/touchstone-1.0.md) for the
specification of each layer.

## What measurements mean

Touchstone measures structural relationships, not subjective quality:

- **Low `unsourced_rate`** means the output's numerical claims appear in the
  source. It does not mean the source's claims are true.
- **Low `quality_profile.gap`** means substance index exceeds presentation
  index. It does not mean the document is well-written or correct.
- **High `G` proportion** in grounding decomposition means most sentences
  restate or directly derive from source. It does not mean those sentences
  are interesting or insightful.

The Standard's Section 9 in its methodology paper documents known limitations
and gaming vectors. Read those before deploying Touchstone in high-stakes
settings.

## Threshold guidance

Default thresholds are calibrated against research-validated reference
distributions. See Standard Section 7 for specific values and the
`benchmarks/` directory for empirical validation evidence.

The most common interpretive defaults:

- `unsourced_rate > 0.30` indicates fabrication zone (source-absent or
  fabricated numbers)
- `unsourced_rate < 0.17` indicates grounded zone (source-present and
  well-cited)
- `quality_profile.gap > 0.0` indicates overclaiming risk (presentation
  exceeds substance)
- `scope_assessment.derivation_regime == "saturated"` indicates Layer 11's
  primary number-based P signal is unreliable on this source — trust Layer 4
  instead

Adjust thresholds for your domain with documented justification per
Section 7 of the Standard.

## Empirical validation

Two reproducible benchmarks ship in `benchmarks/`. Anyone with a clone can
run them and reproduce the published numbers:

```bash
python -m benchmarks.exp_081_discrimination.run
python -m benchmarks.exp_095_grounding.run
```

EXP-081 reproduces the published Cohen's d = -5.43 with d = -5.238 on the
same 12-document corpus. EXP-095 validates Layer 11 against 13
hand-classified outputs with 100% P-direction agreement against manual
classification.

Both benchmarks pin a dated JSON snapshot via byte-match pytest assertion;
CI catches silent regression on any change affecting per-doc predictions.

## Next steps

- Read the [Touchstone Standard 1.0](../STANDARDS/touchstone-1.0.md) for
  complete specifications
- Read [CONTRIBUTING.md](../CONTRIBUTING.md) if you want to contribute
- Watch the [GitHub repository](https://github.com/Clarethium/touchstone)
  for updates
