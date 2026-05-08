#!/usr/bin/env bash
# canon_audit.sh — public-canon §3c + §5b audit.
#
# Canonical operator-side copy. Each Clarethium public repo carries an
# exact copy at `scripts/canon_audit.sh`. A drift between this file and
# the per-repo copy is a process bug; sync via:
#
#   cp ~/.claude/clarethium-internal/canon_audit.sh <repo>/scripts/canon_audit.sh
#   cp ~/.claude/clarethium-internal/canon_audit_known_leaks.txt \
#      <repo>/tests/fixtures/canon_audit_known_leaks.txt
#
# Run from a Clarethium public repo root.
#
# Modes:
#   ./canon_audit.sh                Full audit. Exit 0 = clean, 1 = hits.
#   ./canon_audit.sh --self-test    Verify the audit catches every shape it
#                                   should catch (against the known-leaks
#                                   fixture). Exit 0 = passes, 1 = misses.
#   ./canon_audit.sh --version      Print canonical version SHA.
#
# Reference: ~/.claude/clarethium-internal/PUBLIC_CANON_DISCIPLINE.md §3c, §5b, §5e.

set -u

VERSION='2026-05-08'

# ── Forbidden patterns (§3c) ────────────────────────────────────────
# These patterns must produce zero matches in tracked content outside
# the §5b path allowlist. Case-insensitive throughout.

# Rigid shapes — high-confidence, no false-positive cost.
PAT_RIGID='operator-side|operator-internal|the operator['\''’]s ([a-z-]+ ){0,4}(strategy|methodology|notes|vault|workspace|tree|dev tree|bet|stake|positioning)\b|\boperator (paper|study|playbook|doctrine|memo|brief)\b|private (operator|fork|tree|upstream|repo)|\(see private|\(internal reference|\(operator-side reference|\(see operator-side|internal version of|unredacted [a-z]|the full (methodology|version|spec|specification|paper|draft|manuscript|ground.truth)|extracted from the operator['\''’]s|the canonical (source|version|research|methodology) lives|(trust|data|authorship|methodology|adoption|compounding|positioning|named.authorship)[- ]moat|methodology[- ]as[- ]moat|Clarethium-empire|the project['\''’]s empire|empire-grade|empire-wide|(compounding|data|trust|authorship|named-authorship)[- ]claim|construct[- ]honesty discipline|Powerhouse\.localdomain|llucic@'

# Vault-as-architecture — the noun and its term-of-art compounds.
PAT_VAULT='\bvault[- ]faithful\b|\bvault[- ]validated\b|\bvault behaviour\b|\bvault behavior\b|\bvault[- ]style\b|\bvault['\''’]?s? precision threshold\b|\bvault notes\b|\bin the vault\b|\bfrom the vault\b|\bthe operator['\''’]s ([a-z-]+ ){0,4}vault\b'

# Bare "vault" — context-dependent. Reported as a soft-finding (review
# each hit; reject unless it's a domain compound on the allowlist).
PAT_VAULT_BARE='\bvault\b'
VAULT_BARE_ALLOWLIST='password vault|bank vault|secrets vault|secrets-vault|hashicorp vault|key vault|vault7|vaulted offline'

# ── Path allowlist (§5b) ────────────────────────────────────────────
EXCLUDES=(
  --exclude-dir=.git
  --exclude-dir=node_modules
  --exclude-dir=.venv
  --exclude-dir=venv
  --exclude-dir=__pycache__
  --exclude-dir=.pytest_cache
  --exclude-dir=build
  --exclude-dir=dist
  --exclude-dir=tests/fixtures
  --exclude-dir=tests/data
  --exclude-dir=corpus
  --exclude-dir=transmissions
  --exclude-dir=worked_examples
  --exclude-dir=outputs
  --exclude-dir=*.egg-info
  --exclude=AGENTS.md
  --exclude=.gitleaks.toml
  --exclude=.gitignore
  --exclude=PUBLIC_CANON_DISCIPLINE.md
  --exclude=canon_audit.sh
  --exclude=canon_audit_known_leaks.txt
)

# ── Inline exempt support ───────────────────────────────────────────
# Lines containing `# canon-exempt: <reason>` (or `// canon-exempt:`)
# are allowed past the audit. The reason is mandatory; bare-tag fails.

filter_inline_exempts() {
  grep -vE '(#|//|<!--)\s*canon-exempt:\s*\S'
}

# ── Self-test ───────────────────────────────────────────────────────
self_test() {
  local fixture script_dir
  script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  fixture=
  for candidate in \
    "$script_dir/canon_audit_known_leaks.txt" \
    "tests/fixtures/canon_audit_known_leaks.txt" \
    ~/.claude/clarethium-internal/canon_audit_known_leaks.txt; do
    if [ -f "$candidate" ]; then
      fixture="$candidate"
      break
    fi
  done
  if [ -z "$fixture" ]; then
    echo "self-test: known-leaks fixture not found" >&2
    return 1
  fi

  # Each non-comment, non-blank fixture line MUST be matched by at
  # least one of: PAT_RIGID, PAT_VAULT, or PAT_VAULT_BARE.
  local expected misses=0
  expected=$(grep -cv '^\s*\(#\|$\)' "$fixture" 2>/dev/null || echo 0)

  while IFS= read -r line; do
    [ -z "$line" ] && continue
    case "$line" in \#*) continue ;; esac
    if ! echo "$line" | grep -qEi "$PAT_RIGID|$PAT_VAULT|$PAT_VAULT_BARE"; then
      [ "$misses" -eq 0 ] && echo "self-test FAIL: lines not matched by any pattern:" >&2
      echo "  MISS: $line" >&2
      misses=$((misses + 1))
    fi
  done < "$fixture"

  if [ "$misses" -gt 0 ]; then
    echo "self-test FAIL: $misses/$expected known-leak lines not matched"
    return 1
  fi
  echo "self-test PASS: all $expected known-leak lines matched"
  return 0
}

# ── Main ────────────────────────────────────────────────────────────
case "${1:-audit}" in
  --version)
    echo "canon_audit.sh $VERSION"
    exit 0
    ;;
  --self-test)
    self_test
    exit $?
    ;;
  audit|"")
    rigid_hits=$(grep -rEn -i "${EXCLUDES[@]}" --binary-files=without-match "$PAT_RIGID" . 2>/dev/null | filter_inline_exempts || true)
    vault_hits=$(grep -rEn -i "${EXCLUDES[@]}" --binary-files=without-match "$PAT_VAULT" . 2>/dev/null | filter_inline_exempts || true)
    bare_hits=$(grep -rEn -i "${EXCLUDES[@]}" --binary-files=without-match "$PAT_VAULT_BARE" . 2>/dev/null \
      | grep -viE "$VAULT_BARE_ALLOWLIST" \
      | filter_inline_exempts || true)

    fail=0
    if [ -n "$rigid_hits" ]; then
      echo "## §3c rigid-pattern hits ##"
      echo "$rigid_hits"
      fail=1
    fi
    if [ -n "$vault_hits" ]; then
      [ -n "$rigid_hits" ] && echo
      echo "## §3c vault-as-architecture hits ##"
      echo "$vault_hits"
      fail=1
    fi
    if [ -n "$bare_hits" ]; then
      [ -n "$rigid_hits$vault_hits" ] && echo
      echo "## §3c bare-vault hits (review each) ##"
      echo "$bare_hits"
      fail=1
    fi
    exit $fail
    ;;
  *)
    echo "usage: $0 [--version|--self-test|audit]" >&2
    exit 2
    ;;
esac
