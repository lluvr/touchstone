# Getting started

This guide covers installation, basic usage, and first measurements.

> **Status:** Pre-launch. The library is in active development; some functions raise `NotImplementedError` until extraction from the operator's research vault completes. The Touchstone Standard is the canonical reference; this guide reflects the intended API.

## Installation

When the package is published to PyPI:

```bash
pip install clarethium-touchstone
```

For Layer 1a (heading defaultness) and Layer 5 (semantic alignment), install with the `gemini` extra:

```bash
pip install "clarethium-touchstone[gemini]"
```

For development (running tests, linting):

```bash
pip install "clarethium-touchstone[dev]"
```

## First measurement

Profile an AI-generated output against source material:

```python
from clarethium_touchstone import measure

source = """
Acme Corp reported revenue of $143.8B in fiscal year 2024,
up 12% year-over-year. CEO Maria Chen attributed growth to
expansion in the European market.
"""

output = """
Acme Corp's fiscal year 2024 revenue reached $143.8B,
representing 12% growth. CEO Maria Chen credited European
market expansion as a key driver.
"""

profile = measure(output, source=source)

print(f"Source matching: {profile['source_matching']['unsourced_rate']:.2%}")
print(f"Quality gap: {profile['quality_profile']['gap']:.3f}")
print(f"G/F/P: {profile['grounding_decomposition']['proportions']}")
```

Expected (when implementation lands):

```
Source matching: 0.00%
Quality gap: -0.34   (negative gap = understated, well-grounded)
G/F/P: {'G': 0.83, 'F': 0.17, 'P': 0.00}
```

## Specification compliance

Verify an output against a written specification:

```python
from clarethium_touchstone import align

spec = """
Write a brief financial summary that:
1. States revenue figure for fiscal year 2024
2. Reports year-over-year growth percentage
3. Names the CEO
4. Identifies one key driver of growth
"""

output = """
Acme Corp's fiscal year 2024 revenue reached $143.8B,
representing 12% growth. CEO Maria Chen credited European
market expansion as a key driver.
"""

alignment = align(output, spec=spec)

print(f"Coverage rate: {alignment['summary']['coverage_rate']:.2%}")
print(f"Concrete coverage: {alignment['summary']['concrete_coverage_rate']:.2%}")
for entry in alignment['coverage']:
    req = entry['requirement']['text'][:60]
    status = entry['status']
    print(f"  [{status}] {req}")
```

## Combined profile

Run both measurement and compliance in one call:

```python
from clarethium_touchstone import profile

result = profile(output, source=source, spec=spec)

# result['quality'] is the MeasureResult
# result['alignment'] is the AlignResult
# result['combined_summary'] aggregates key metrics
```

## Individual layer functions

Sometimes you only need one specific measurement:

```python
from clarethium_touchstone.measure import (
    source_matching,
    grounding_decomposition,
)
from clarethium_touchstone.align import (
    extract_requirements,
    coverage_mapping,
)

# Single layer use
sourcing = source_matching(output, source)
gfp = grounding_decomposition(output, source)
```

See the [Touchstone Standard 1.0](../STANDARDS/touchstone-1.0.md) for the specification of each layer.

## What measurements mean

Touchstone measures structural relationships, not subjective quality. Specifically:

- **Low `unsourced_rate`** means the output's numerical claims appear in the source. It does not mean the source's claims are true.
- **Low `quality_profile.gap`** means substance index exceeds presentation index. It does not mean the document is well-written or correct.
- **High `G` proportion** in grounding decomposition means most sentences restate or directly derive from source. It does not mean those sentences are interesting or insightful.
- **`coverage_rate`** measures requirement presence in output, not requirement quality of execution.

The Standard's Section 9 in its methodology references documents known limitations and gaming vectors. Read those before deploying Touchstone in high-stakes settings.

## Threshold guidance

Default thresholds are calibrated against research-validated reference distributions. See Standard Section 7 for specific values.

The most common interpretive defaults:

- `unsourced_rate > 0.30` indicates fabrication zone (source-absent or fabricated)
- `unsourced_rate < 0.17` indicates grounded zone (source-present and well-cited)
- `quality_profile.gap > 0.0` indicates overclaiming risk
- `coverage_rate > 0.60` indicates ADDRESSED requirements (calibrated at 94% accuracy on synthetic test pairs)

Adjust thresholds for your domain with documented justification per Section 7 of the Standard.

## Next steps

- Read the [Touchstone Standard 1.0](../STANDARDS/touchstone-1.0.md) for complete specifications
- Read [CONTRIBUTING.md](../CONTRIBUTING.md) if you want to contribute
- Watch the [GitHub repository](https://github.com/Clarethium/touchstone) for updates
- Watch [FieldReceipts](https://fieldreceipts.com) for the community platform built on Touchstone
