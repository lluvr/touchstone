# Suggestion: [Title]

**Track:** Standard Track
**Author:** [Your name and contact]
**Status:** Draft
**Standard sections affected:** [e.g., Section 5.4, Section 7]
**Version impact:** [Major / Minor / Patch]
**Created:** [YYYY-MM-DD]

---

## Summary

One paragraph describing the proposed change to the Touchstone Standard.

## Motivation

Why this change matters. What problem in the current Standard does it address? What use case is currently underserved?

If this Suggestion responds to a specific issue or community discussion, link it.

## Proposed change

Specific, concrete description of what the Standard text becomes. Use diff-style formatting if helpful:

```
BEFORE (Section X.Y):
[current Standard text]

AFTER (Section X.Y):
[proposed Standard text]
```

For new layers, requirement types, or other additions, write the proposed Standard text in full as it would appear in the Standard document.

## Rationale

Why this specific approach? What alternatives were considered and rejected?

If this change derives from research or experimentation, cite the work. EXP-### references and external papers should be cited specifically.

## Reference test cases

Standard Track Suggestions MUST propose reference test cases that verify the change. These ship with the Standard version that incorporates the change.

For each reference case, provide:

- Inputs (source.md, output.md, spec.md as applicable)
- Expected outputs (`expected.json` structure)
- Tolerance for numerical comparisons

Example:

```
tests/reference/[layer-name]/case_NNN/
├── source.md
├── output.md
└── expected.json
```

## Backwards compatibility

Does this change break existing implementations or users?

- [ ] No backwards-compatibility implications
- [ ] Backwards-compatible (additive only)
- [ ] Breaking change requiring major version bump

If breaking, describe the migration path for existing implementations.

## Implementation notes

Sketch how a conforming implementation would implement this change. For changes affecting the reference library, include a code outline.

If the change adds optional capability, note what implementations get if they implement it and what they get if they don't.

## Open questions

Questions the editor body or community needs to resolve before this Suggestion can be accepted. List explicitly so reviewers can address each.

## References

Related issues, prior discussions, external work, EXP papers, AIRP publications. Use stable links where possible.

## Copyright

This Suggestion is placed in the public domain. By submitting, the author agrees that the Suggestion content may be incorporated into the Touchstone Standard under CC-BY 4.0.
