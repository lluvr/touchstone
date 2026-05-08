# Reference test suite

This directory contains the canonical reference test cases for the Touchstone Standard. A conforming implementation MUST pass all reference test cases at the Standard version it implements.

## Status

The reference test suite is being authored against the Touchstone Standard. Initial content placeholder. Full reference suite ships with Standard 1.0 ratification.

## Structure (planned)

```
tests/reference/
├── README.md                      # this file
├── source_matching/               # Layer 4 reference cases
│   ├── case_001/
│   │   ├── source.md
│   │   ├── output.md
│   │   └── expected.json
│   └── ...
├── entity_provenance/             # Layer 5 reference cases
├── temporal_instability/          # Layer 3 reference cases
├── grounding_decomposition/       # Layer 11 G/F/P reference cases
├── quality_profile/               # Layer 10 reference cases (4 validation studies)
├── alignment/
│   ├── requirement_extraction/    # Compliance Layer 1 reference cases
│   ├── coverage_mapping/          # Compliance Layer 2 reference cases
│   └── scope_drift/               # Compliance Layer 3 reference cases
└── integration/                   # Combined profile reference cases
```

## Case format

Each case directory contains:

- Input files (source.md, output.md, spec.md as applicable)
- `expected.json` with the canonical expected output

Implementations run against the inputs and compare results against `expected.json`. Tolerance for numerical comparisons is documented per case.

## Versioning

Reference cases are versioned with the Standard. Reference suite v1.0 corresponds to Standard 1.0. Changes to reference cases require Standard version bumps.

## Adding new cases

New reference cases require a Standard Track Suggestion per `SUGGESTIONS/PROCESS.md`. Cases added without Standard updates are not part of the canonical suite.

Implementations MAY include their own additional test cases under `tests/synthetic/` or similar; those are implementation-specific and not part of the conformance test.

## Validation pedigree

The reference suite draws from existing validation work:

- 171 measure tests + 19 Layer 11 tests
- 148 align self-tests
- Cross-domain validation (3 document types: product specs, research summaries, code documentation)
- Cross-generator validation (Anthropic, Gemini, OpenAI/xAI families)
- Studies 8-9 discriminant validity (100 pairs)

For ratification, a representative subset (~30-100 cases) is selected as the canonical reference suite.

## Running

When the suite is populated:

```bash
pytest tests/reference/
```

This runs all reference cases against the local `clarethium-touchstone` implementation.
