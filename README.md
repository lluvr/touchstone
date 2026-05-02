# Touchstone

Model-independent verification for AI-coupled work.

A Clarethium project. Standards and reference implementation for measuring AI output structure, fabrication, grounding, and spec compliance without depending on a model to judge a model.

## What's here

This repository contains:

- **Touchstone Standard** — the canonical specification (CC-BY 4.0) at `STANDARDS/touchstone-1.0.md`
- **`clarethium-touchstone`** — Python reference implementation (Apache 2.0 or MIT, pending decision)

The Standard defines the methodology. The library implements it. Other implementations conforming to the Standard are welcome.

## Status

Pre-launch. Standard 1.0 drafting in progress. Library extraction from research vault in progress. PyPI organization application pending approval.

Expected first release: Q3 2026.

## Quick example (when published)

```python
from clarethium_touchstone import measure, align

# Profile output: fabrication, grounding, structural quality, G/F/P decomposition
profile = measure(text, source=source)

# Verify output meets spec: coverage, structural compliance
alignment = align(text, spec=spec)
```

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
