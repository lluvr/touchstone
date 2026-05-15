# Reference test suite

This directory is reserved for the canonical reference test cases shipped with the Touchstone Standard. A conforming implementation MUST pass all reference test cases at the Standard version it implements (Standard §11).

## Status

The reference suite is not yet populated. Standard 1.0 is at `1.0.0-draft.8`; the reference cases extracted into this directory will land alongside ratification. Until then, the regression benchmarks under `benchmarks/exp_081_discrimination/` and `benchmarks/exp_095_grounding/` plus the unit tests under `tests/` are the practical conformance surface, as Standard §11 directs.

## Planned structure

```
tests/reference/
├── README.md                      # this file
├── source_matching/               # Layer 4 reference cases
├── entity_provenance/             # Layer 5 reference cases
├── temporal_instability/          # Layer 3 reference cases
├── grounding_decomposition/       # Layer 11 G/F/P reference cases
└── quality_profile/               # Layer 10 reference cases
```

Section 6 (Specification Compliance) is reserved for Standard 1.1; reference cases for that section will land when 1.1 ratifies.

## Case format (planned)

Each case directory will contain:

- Input files (`source.md`, `output.md`, and `spec.md` where applicable)
- `expected.json` with the canonical expected output, with documented numerical tolerance per case

Implementations run against the inputs and compare results against `expected.json`. Per-case tolerance is part of the case definition.

## Versioning

Reference cases version with the Standard. Reference suite 1.0 will correspond to Standard 1.0. Changes to reference cases require Standard version bumps.

## Adding new cases

New reference cases require a Standard Track Suggestion per `SUGGESTIONS/PROCESS.md`. Cases added without a corresponding Standard update are not part of the canonical conformance suite.

Implementations MAY include their own additional test cases under `tests/synthetic/` or similar; those are implementation-specific and not part of the conformance surface.

## Running

When the suite is populated:

```bash
pytest tests/reference/
```

This runs all reference cases against the local `clarethium-touchstone` implementation.
