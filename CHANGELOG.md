# Changelog

All notable changes to Touchstone (Standard and library) are documented here.

The Standard and library are versioned independently. Standard versions track methodology evolution; library versions track implementation releases.

---

## 2026-05-01: Repository initialized

Repository created at `Clarethium/touchstone`. Initial structure:

- `README.md` — repository orientation
- `CHANGELOG.md` (this file)
- `STANDARDS/touchstone-1.0.md` — Touchstone Standard 1.0 (in drafting)

PyPI organization application pending approval. Library extraction from research vault in progress.

Architecture committed:
- Touchstone is a Clarethium sub-brand at `touchstone.clarethium.com`
- Repository under `github.com/Clarethium/touchstone` organization
- Standard document under CC-BY 4.0
- Library under Apache 2.0 (or MIT, pending final decision)
- PyPI package name: `clarethium-touchstone` (or fallback if `touchstone` namespace becomes available)

## Standard versioning policy

Touchstone Standard follows semantic versioning:

- **Major (1.0 → 2.0):** Breaking changes to required fields, methodology, or thresholds. Existing implementations require updates to remain conformant.
- **Minor (1.0 → 1.1):** Additive changes — new optional layers, new requirement types, new measurement dimensions. Existing implementations remain conformant for the previous version.
- **Patch (1.0 → 1.0.1):** Editorial changes, clarifications, typo corrections, expanded examples. No methodology changes.

## Library versioning policy

The `clarethium-touchstone` library follows semantic versioning independently:

- Library version aligns with the Standard version it implements (e.g., library 1.0.x implements Standard 1.0.x)
- Library patches can ship without Standard changes
- Library may temporarily implement features ahead of Standard ratification (flagged as experimental)
- Library deprecations announced one minor version before removal

---

## Pending releases

- **Standard 1.0** — drafting in progress (May 2026 target)
- **`clarethium-touchstone` 0.1.0** — initial library release (Q3 2026 target, dependent on PyPI approval and substrate extraction)
