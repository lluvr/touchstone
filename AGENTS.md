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
  decision drafts, "repo shape" or "empire shape" discussions).
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
