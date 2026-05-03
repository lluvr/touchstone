# Touchstone

Model-independent verification for AI-coupled work.

A Clarethium project. Standards and reference implementation for measuring AI output structure, fabrication, grounding, and spec compliance without depending on a model to judge a model.

## What's here

This repository contains:

- **Touchstone Standard** — the canonical specification (CC-BY 4.0) at `STANDARDS/touchstone-1.0.md`
- **`clarethium-touchstone`** — Python reference implementation (Apache 2.0 or MIT, pending decision)

The Standard defines the methodology. The library implements it. Other implementations conforming to the Standard are welcome.

## Status

Pre-launch on PyPI; reference implementation is feature-complete on `main`. All eleven measurement layers from Standard 1.0 are implemented and tested (338 tests, all CI green: lint, type check, test on Python 3.10/3.11/3.12, build distribution).

PyPI organization application pending approval. Until then, install from source:

```bash
git clone https://github.com/Clarethium/touchstone.git
cd touchstone
pip install -e .
```

## Quick example

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

The composite quality profile (Layer 10) requires ≥10 numbers in text for the source-fidelity contribution to qualify (vault precision threshold). For the substance vs presentation gap signal, supply a longer document:

```python
text = (
    "Revenue grew 12% to $143M with 25% margins reported. "
    "Costs declined 8% across 5,000 employees over 18 months. "
    "Headcount reached 2,500 with $45,000 average compensation paid. "
    "Customer acquisition cost dropped to $1,200 from baseline. "
    "Retention improved 7.5% to 94.2% across all major segments."
)

result = measure(text, source=text)
result["quality_profile"]["substance_index"]   # 1.0 (self-source, all numbers grounded)
result["quality_profile"]["gap"]               # negative — substance exceeds presentation
result["quality_profile"]["components_available"]  # ["source_fidelity", "assertiveness", ...]
```

For Layer 1a (heading defaultness), supply your own LLM client as a callable (vendor-neutral):

```python
def baseline_generator(prompt: str) -> str | None:
    # Your LLM call here. Return generated text or None on failure.
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

## Library layers

The reference implementation covers every layer in Standard Section 5:

| Layer | Function | Requires |
|------|----------|----------|
| 1a heading defaultness | `structural_profile` | `topic` + `baseline_generator` |
| 1b mechanism ratio | `structural_profile` | text |
| 1c assertion ratio | `structural_profile` | text |
| 2 claim density | `claim_density` | text |
| 3 temporal instability | `temporal_instability` | text + `comparisons` |
| 4 source matching | `source_matching` | text + `source` |
| 5 entity provenance | `entity_provenance` | text + `source` |
| 6 vocabulary proximity | `vocabulary_proximity` | text + `source` |
| 7 presentation features | `presentation_features` | text |
| 8 epistemic calibration | `epistemic_calibration` | text + `source` |
| 9 information novelty | `information_novelty` | text |
| 10 quality profile composite | `quality_profile` | text (substance from L3/L4/L5/L8) |
| 11 grounding decomposition | `grounding_decomposition` | text + `source` |

The top-level `measure()` orchestrator runs every layer whose preconditions are met. Layers without preconditions return `None` for that key in the `MeasureResult` dict. Specification compliance (Standard Section 6) is reachable via `align()`; combined output via `profile()`.

## Use cases

- AI integrity research and benchmarking
- Internal AI quality verification at organizations
- Substrate enforcement for AI-coupled work platforms (used by [FieldReceipts](https://fieldreceipts.com))
- Independent third-party verification of AI vendor claims
- Educational use in AI methodology courses

## Why model-independent

LLM-as-judge approaches use AI to evaluate AI output. Touchstone uses regex, structural analysis, source matching, and arithmetic. The substrate does not depend on the model being measured. This matters when the auditor cannot be made of the same material as the audited.

## Licensing

- **Standard:** CC-BY 4.0 (content)
- **Library:** Apache 2.0 (recommended) or MIT (alternative)

Final library license decision pending. Both are permissive open source and allow commercial use.

## Related

- [Clarethium](https://clarethium.com) — methodology umbrella, mothership
- [Frame Check](https://frame.clarethium.com) — applied tool for frame validation
- [FieldReceipts](https://fieldreceipts.com) — community platform using Touchstone substrate
- Documentation: `https://touchstone.clarethium.com` (coming)

## Contributing

Pre-launch. Contribution process documented after Standard 1.0 is published. Watch this repo for updates.

## Citation

When citing the Standard:

```
Touchstone Standard 1.0 (2026), Clarethium.
https://github.com/Clarethium/touchstone/blob/main/STANDARDS/touchstone-1.0.md
```

When citing the library: BibTeX entry will be provided with the first published release.
