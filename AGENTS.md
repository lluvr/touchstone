# AGENTS.md

Guidance for AI coding agents (Claude Code, Cursor, Codex, Aider,
etc.) working in this repository.

This file is loaded by most agent runtimes the same way `CLAUDE.md`
or `.cursorrules` is. Agents should read it before making changes.

## Public-canon discipline

This repository is one of several public Clarethium artifacts. The
operator maintains a separate, private working set of strategic
memos, audit deliverables, methodology drafts, outreach lists, and
similar artifacts. Those **never** enter this repository, regardless
of how relevant they feel to the change in front of you.

If you are tempted to commit a file with any of these shapes:

- A document analyzing why some choice was made (rationale memos,
  decision drafts, "repo shape" or "project shape" discussions).
- An audit of leakage, security, methodology gaps, publication
  readiness, or engine performance.
- An outreach plan, reviewer list, methodology paper outline, or
  cross-curator coordination doc.
- Anything mentioning the operator's secrets vault, claude memory
  layout, or absolute paths into the operator's home directory
  (`/home/<operator>/...`).

Stop. That belongs in the operator's private workspace, not in
this repository. Either drop the change, or write a generalized
public-canon version that documents the *outcome* (what was decided,
what shipped) without the operator-internal *reasoning* (why
specifically, who else is involved, what is queued).

## When you find an existing leak

If you discover that the public history contains operator-internal
content (rare, but happens), do not silently delete it in a
forward-only commit. Instead:

1. Open an issue describing what you found, where, and the rough
   shape of the content (do not paste the leak itself into the
   issue).
2. Wait for operator-side acknowledgment before any history
   rewrite. History rewrite invalidates external references and
   may require coordinated downstream cleanup.

## Commit-message hygiene

A commit that removes leaked content should not narrate the leak
in its own message. The diff shows what was removed; the message
should not re-narrate it. Use a generic descriptor like "an
operator-internal artifact" rather than the document name or
content category.

## Engineering norms

- No AI attribution in commit messages. No "Generated with Claude
  Code" footer. No `Co-Authored-By: Claude`. The work is the
  operator's regardless of which tool produced the diff.
- Style: no em-dashes, en-dashes, smart quotes, or curly
  apostrophes anywhere in committed content (prose, code, commit
  messages). Use straight quotes and rewrite sentences rather
  than reaching for an em-dash.
- Branch protection on the default branch blocks force-push,
  deletion, and non-linear history. History rewrite is an
  operator-side recovery operation, not part of normal flow.

## Forbidden vocabulary

Beyond the file shapes above, certain phrasings always leak. These never appear in committed content (with the exception of this AGENTS.md, the canon audit script, and its self-test fixture, which are allowed to name the patterns in order to forbid them):

- `operator-side`, `operator-internal` (any compound).
- `the operator's [strategy|methodology|notes|vault|workspace|tree|dev tree|bet|stake|positioning]` — also when an adjective intervenes (`the operator's research vault`).
- Bare `operator [methodology|framework|practice|positioning|paper|study|playbook|doctrine|memo|brief]`.
- Any definite reference to `vault` as a body of operator material: `the vault`, `in the vault`, `from the vault`. Also forbidden as terms of art: `vault-faithful`, `vault-validated`, `vault behaviour`, `vault precision threshold`, `vault notes`. Allowed only in domain compounds where `vault` is unrelated (`password vault`, `secrets vault`, `hashicorp vault`, `key vault`).
- Sanitization-shape parentheticals: `(see private)`, `(internal reference)`, `(operator-side reference)`, `(see operator-side ...)`.
- Strategic-positioning vocabulary: `trust|data|authorship|named-authorship|compounding|methodology moat`, `Clarethium-empire`, `empire-grade`, `the project's empire`, `compounding claim`, `construct-honesty discipline`.
- Operator hostname / username: `Powerhouse.localdomain`, `llucic@`.

Subtract over substitute: when removing one of these, delete the sentence and rewrite the surrounding paragraph. Do not replace it with a placeholder marker; the marker itself is a leak.

## Verification before commit

Run the canon audit:

```bash
bash scripts/canon_audit.sh --self-test   # verify the audit catches every forbidden shape
bash scripts/canon_audit.sh               # check the working tree
```

Both must exit 0. The self-test runs the audit against `scripts/canon_audit_known_leaks.txt` (the fixture lists every shape forbidden above) and confirms the pattern set still catches all of them. The working-tree check verifies your changes don't introduce new violations.

False positives can be tagged with an inline comment: `# canon-exempt: <reason>`. The reason is mandatory; bare `# canon-exempt:` without a reason is rejected.

## Build artifacts

`build/`, `dist/`, `*.egg-info/`, `__pycache__/`, `.pytest_cache/`, `.venv/`, `venv/`, `.tox/`, `.coverage`, `htmlcov/` MUST NOT be committed. They re-import previously-sanitized text from prior pipeline runs and have leaked operator-side content in past releases. The repository `.gitignore` covers these patterns; do not bypass.
