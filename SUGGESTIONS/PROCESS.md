# Touchstone Suggestion Process

How proposed changes to Touchstone (Standard or library) are submitted, reviewed, and resolved.

This process is modeled on Python Enhancement Proposals (PEP-1) and Bitcoin Improvement Proposals (BIP-1). It is intentionally lightweight at this stage; the project will formalize as community grows.

---

## What is a Suggestion

A Suggestion is a proposed change to Touchstone. It can be:

- A change to the Touchstone Standard (specification)
- A change to the `clarethium_touchstone` library (implementation)
- A change to the project's processes or governance
- A new informational document (best practices, integration guide, etc.)

Bug fixes that do not change behavior do not require a Suggestion. Open a pull request directly with tests.

## Audience

Anyone may submit a Suggestion. Native English is not required; if writing in another language, the maintainers can help with translation as bandwidth allows.

The author of a Suggestion is sometimes called the *champion*. The champion shepherds the proposal through review and is the primary respondent to feedback.

---

## Suggestion types

### Standard Track

Suggestions that propose changes to the Touchstone Standard (`STANDARDS/touchstone-1.0.md` and its successors).

**Examples:**
- Adding a new measurement layer
- Modifying a threshold value
- Changing required vs optional layer classification
- Renaming an output field
- Adding a new requirement type

Standard Track suggestions follow semantic versioning per Standard Section 10. Major changes (breaking) require a major version bump; additive changes are minor. Editorial changes are patch-level.

### Library Track

Suggestions that propose changes to the `clarethium_touchstone` library that do not require Standard changes.

**Examples:**
- Performance improvements
- New integrations (frameworks, languages)
- API additions that conform to the Standard
- Bug fix releases

### Process Track

Suggestions that propose changes to the project's processes or governance.

**Examples:**
- Changes to this Suggestion process
- Changes to editor selection
- Changes to testing or release discipline

### Informational

Suggestions that document best practices, integration guides, or rationale without changing the Standard or library.

**Examples:**
- Guidance for using Touchstone with specific AI tools
- Tutorials
- Position papers on related work

---

## Workflow

```
   ┌──────┐
   │ Idea │
   └───┬──┘
       │
       ▼
   ┌──────┐
   │ Draft│ ────────── Open issue for early discussion (optional)
   └───┬──┘
       │
       ▼
 ┌────────┐
 │ Review │ ────────── Pull request opened against repository
 └───┬────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  Resolution                              │
│   - Accepted (merged by maintainers)    │
│   - Rejected (closed with rationale)    │
│   - Deferred (closed; revisit later)    │
│   - Withdrawn (closed by author)        │
└─────────────────────────────────────────┘
```

### Idea phase

The proposed change exists informally. Discussion in any venue (issues, social media, mailing lists). Champion gauges interest before drafting.

### Draft phase

Champion writes the Suggestion document using the template appropriate for the track:

- Standard Track: `SUGGESTIONS/template-standard.md`
- Library Track: `SUGGESTIONS/template-library.md`
- Process Track: `SUGGESTIONS/template-process.md`
- Informational: `SUGGESTIONS/template-informational.md`

Library Track changes that are simple bug fixes or small improvements MAY skip the template and use the standard pull request template instead.

Draft suggestions can be:

- Opened as a GitHub issue first to gather feedback before writing the full proposal
- Opened directly as a pull request with the proposal document

### Review phase

The Suggestion is opened as a pull request against this repository. Discussion happens on the pull request thread. The maintainers respond as bandwidth allows; at this stage the project does not commit to a fixed response SLA.

Reviewers evaluate against:

**For Standard Track:**
- Does the proposed change fit the Standard's scope (model-independent measurement, structural over semantic)?
- Is the change well-specified (concrete enough to implement)?
- Are reference test cases provided?
- Does it have backwards-compatibility implications?
- Has the champion considered alternatives?

**For Library Track:**
- Does the change conform to the Standard?
- Are tests included?
- Does it follow project code style?
- Is the change scoped (one concern per PR)?

**For Process Track:**
- Does the change improve clarity, fairness, or operability?
- Is there community consensus or strong rationale?

**For Informational:**
- Is the document accurate?
- Does it complement existing documentation?

### Resolution

Resolution is one of:

- **Accepted.** Maintainers merge the pull request. The change is incorporated. Standard Track changes trigger a version bump per Section 10.
- **Rejected.** The proposal is closed with a rationale comment. The rationale becomes part of the project's reasoning record. Rejected suggestions can be reopened with new evidence or modified scope.
- **Deferred.** The proposal is closed but tagged for later reconsideration. Common reasons: dependency on other in-progress work, or the proposal is good but lacks priority.
- **Withdrawn.** The champion closes the proposal voluntarily.

Resolution is by maintainer consensus. As the project matures and an editor body is constituted (Standard §11), formal reviewer-assignment, voting, and tie-breaking rules will be added here.

---

## Maintainers and governance evolution

The current maintainers are responsible for:

- Triaging incoming Suggestions
- Reviewing Suggestions
- Merging accepted Suggestions
- Maintaining the Standard document
- Releasing library versions
- Documenting the project's reasoning record

The Standard reserves formal certification by an editor body to a future Standard version once such a body is constituted (Standard §11). Until then, all responsibilities above sit with the project maintainers; conformance is by self-certification.

---

## Versioning of Suggestions

Suggestions themselves are not versioned (a Suggestion is the unit of change; the Standard or library version is what gets bumped). Each merged Suggestion is associated with the Standard or library version that incorporates it.

The CHANGELOG.md records merged Suggestions in the version entry where they ship.

---

## Conflict of interest

Editors who have a commercial interest that could be affected by a Suggestion MUST disclose the interest and recuse from reviewing or voting on that Suggestion. Recusal is documented in the pull request thread.

---

## Reasoning record

The project maintains a reasoning record. Rejected and deferred Suggestions remain visible (closed pull requests on GitHub) so future contributors can see what was considered, what was decided, and why.

This is not a graveyard; it is an asset. Future contributors who propose similar changes find prior reasoning and either build on it or articulate why it should be revisited.

---

## When to open an issue vs a pull request

**Open an issue first when:**

- You're not sure if a change is in scope
- You want to discuss alternatives before writing a full proposal
- You're reporting a bug that may turn into a Suggestion
- You're a new contributor unsure of the project's conventions

**Open a pull request directly when:**

- You have a clear, well-scoped change with implementation
- You're confident the change is in scope
- You're a returning contributor familiar with the conventions
- You're fixing a documented bug

---

## Templates

Templates for Suggestion documents:

- [`SUGGESTIONS/template-standard.md`](template-standard.md) (Standard Track)
- [`SUGGESTIONS/template-library.md`](template-library.md) (Library Track)
- [`SUGGESTIONS/template-process.md`](template-process.md) (Process Track)
- [`SUGGESTIONS/template-informational.md`](template-informational.md) (Informational)

Copy the appropriate template, fill in the sections, and submit as a pull request against this repository.

---

## References

- [PEP 1 - PEP Purpose and Guidelines](https://peps.python.org/pep-0001/)
- [BIP 1 - BIP Purpose and Guidelines](https://github.com/bitcoin/bips/blob/master/bip-0001.mediawiki)
- Standard Section 10 (Versioning and evolution)
- Standard Section 11 (Conformance)

---

## Process versioning

This document is a Process Track Suggestion. Changes to it follow the same workflow described above.

Current version: 1.0.0-draft. Ratification follows maintainer completion of the pending sections and Suggestion-process review.
