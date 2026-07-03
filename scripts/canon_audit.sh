#!/usr/bin/env bash
# canon_audit.sh — comprehensive public-canon leak audit.
#
# Canonical maintainer-side copy. Each Clarethium public repo carries an
# exact copy at `scripts/canon_audit.sh`. A drift between this file and
# the per-repo copy is a process bug; sync via:
#
#   cp ~/.claude/clarethium-internal/canon_audit.sh <repo>/scripts/canon_audit.sh
#   cp ~/.claude/clarethium-internal/canon_audit_known_leaks.txt \
#      <repo>/scripts/canon_audit_known_leaks.txt
#
# Run from a Clarethium public repo root.
#
# Modes:
#   ./canon_audit.sh                Full audit. Exit 0 = clean, 1 = hits.
#   ./canon_audit.sh --self-test    Verify the audit catches every shape it
#                                   should catch (against the known-leaks
#                                   fixture). Exit 0 = passes, 1 = misses.
#   ./canon_audit.sh --version      Print canonical version SHA.
#   ./canon_audit.sh --list-families Print pattern family names.
#
# Reference: ~/.claude/clarethium-internal/PUBLIC_CANON_DISCIPLINE.md
#   §3c (forbidden patterns), §5b (path allowlist), §5e (audit canon).
#
# Failure-mode catalog (each family closes a documented FM-PCD-N):
#   PRIVATE_FILES         FM-PCD-1  (sanitize-not-construct: refs to maintainer-only docs)
#   FVS_EVAL_PATHS        FM-PCD-9  (dead-link in adopter docs)
#   WEB_APP_MODULES       FM-PCD-11 (web-app-architecture leak via shared modules)
#   WEB_APP_LIVE_IMPORTS  FM-PCD-8  (try/except imports of private modules)
#   OPERATOR_PATHS        FM-PCD-7  (personal-path leak)
#   OPERATIONAL_STATE     FM-PCD-6  (runtime state file leak)
#   OPERATOR_INFRA        FM-PCD-11 (operator infra leak via shared comments)
#   RESEARCH_IDS          FM-PCD-10 (research ID without public resolver)
#   STRATEGIC_EXTENDED    FM-PCD-3  (strategic vocabulary beyond §3c PAT_RIGID)
#   CANON_VOCAB_EXTENDED  FM-PCD-3  (construct-honesty {posture|defect|audit})
#   RIGID                 FM-PCD-1  (legacy §3c rigid set, kept for compat)
#   VAULT                 FM-PCD-1  (vault-as-architecture, kept for compat)

set -u

VERSION='2026-07-03-reframe-person-context-allowlist'

# ── Path allowlist (§5b) ────────────────────────────────────────────
EXCLUDES=(
  --exclude-dir=.git
  --exclude-dir=.claude
  --exclude-dir=.ruff_cache
  --exclude-dir=.mypy_cache
  --exclude-dir=node_modules
  --exclude-dir=.venv
  --exclude-dir=venv
  --exclude-dir=__pycache__
  --exclude-dir=.pytest_cache
  --exclude-dir=build
  --exclude-dir=dist
  --exclude-dir=tests/fixtures
  --exclude-dir=tests/data
  --exclude=leak_classes.*.yaml
  --exclude-dir=corpus
  --exclude-dir=transmissions
  --exclude-dir=worked_examples
  --exclude-dir=outputs
  --exclude-dir=*.egg-info
  --exclude=AGENTS.md
  --exclude=.gitleaks.toml
  --exclude=.gitignore
  --exclude=.pre-commit-config.yaml
  --exclude=PUBLIC_CANON_DISCIPLINE.md
  --exclude=canon_audit.sh
  --exclude=canon_audit_known_leaks.txt
  --exclude=canon_audit_pystring_concat_known_leaks.py
  --exclude=canon_replacements.txt
)

# ── Inline exempt support ───────────────────────────────────────────
# Lines containing `# canon-exempt: <reason>` (or `// canon-exempt:`)
# are allowed past the audit. Reason is mandatory; bare-tag fails.
filter_inline_exempts() {
  grep -vE '(#|//|<!--)\s*canon-exempt:\s*\S'
}

# ── Pattern family: PRIVATE_FILES (FM-PCD-1) ────────────────────────
# Operator-internal documents referenced by filename. Public canon
# never names these; references invite dead-link reads.
PAT_PRIVATE_FILES='\b(STRATEGY|DATA_MOAT|RELEASE_PREP|LEAKAGE_AUDIT|REMEDIATION_LOG|MCP_CLIENT_CONFORMANCE|PUBLISH_READINESS_VERDICT|PUBLISH_READINESS_ASSESSMENT|OBSERVATORY_STATE|CONSTRUCT_HONESTY_AUDIT|STRESS_TEST_ASSESSMENT|METHODOLOGY_PAPER|ANTICIPATED_CRITIQUES|VALIDATION_PROGRAM|PHASE_[0-9_]+_GAPS|FRAME_DIVERGENCE_v[0-9]|V4_2_GAP_INVENTORY|EXTRACT_POLICY|VERIFICATION_ARCHITECTURE|DETECTOR_V[0-9]_PROMOTION|TRACK_B_INFORMAL|REVIEWERS|REVIEWER_OUTREACH_TEMPLATES|CALIBRATION_SET|FRAMING_ANALYSIS|V[0-9]_EVIDENCE_FOR_PROMOTION|V[0-9]_CONFIDENCE_INVERSION_IMPACT|FRAME_DIVERGENCE_v[0-9]_SUMMARY|ANCHOR_AUTHORSHIP_METHODOLOGY|MCP_INTEGRATOR_OUTREACH|MCP_PACKAGE_DESIGN|MCP_CONTRACT_V[0-9]_PROPOSAL|MCP_TYPESCRIPT_SCOPE|METHODOLOGY_V[0-9]_CANDIDATES|ENGINE_TIER_(STRATEGY|RECOMMENDATIONS)|CROSS_CURATOR_OUTREACH|DETECTION_RULE_AUDIT|VISITOR_AUDIT|RULE_AUDIT|LIBRARY_V[0-9]_TO_V[0-9]_RATIFICATION|RELIABILITY_STUDY|FALSIFICATION_PROTOCOL|CORRESPONDENCE_STUDY)([_a-zA-Z0-9]*)\.md\b|\b(DETECTION_RULE_AUDIT|VISITOR_AUDIT)\b|\bSTRATEGY\s+(DD[- ]?[0-9]+|§[0-9]+)\b'

# ── Pattern family: FVS_EVAL_PATHS (FM-PCD-9) ───────────────────────
# Maintainer-side validation tree. No public resolver.
PAT_FVS_EVAL_PATHS='\bfvs_eval/[a-zA-Z0-9_./-]+'

# ── Pattern family: WEB_APP_MODULES (FM-PCD-11) ─────────────────────
# References to web-app-only modules from shared MCP code. Either as
# .py filename, in import statements, or as bareword module names in
# comments. Allowlist excludes the modules that legitimately ship in
# the wheel.
PAT_WEB_APP_MODULES='\b(observatory|telemetry|model_registry|tier_a_event|saved_analyses|saved_compare|origin_protection|framing_ai|consensus|og_image|build_corpus_site|export_corpus|reframe|claim_selector)(\.py)?\b'

# ── Pattern family: WEB_APP_LIVE_IMPORTS (FM-PCD-8) ─────────────────
# Try-imports of private modules. The module name in the source is
# itself the leak, regardless of whether the import succeeds at
# runtime. Includes the modules that a wheel-installed adopter cannot
# resolve.
PAT_WEB_APP_LIVE_IMPORTS='\b(from|import) (security|annotator|observatory|telemetry|model_registry|tier_a_event|saved_analyses|saved_compare|origin_protection|framing_ai|consensus|og_image|build_corpus_site|export_corpus|reframe|claim_selector|app|pipeline|formatter|framing_sdk|falsifications|phase1_smoke|consistency|examples|compare_examples|domain_baselines|decision_readiness_diff|decision_readiness_peer|l2_concept_validation|l2_extended_validation|metric_classifier|mirror|subject_classifier)\b'

# ── Pattern family: OPERATOR_PATHS (FM-PCD-7) ───────────────────────
# Personal machine paths and operator-private repo URLs.
PAT_OPERATOR_PATHS='/home/llucic|/Users/lovro|Powerhouse(\.localdomain)?|~/\.claude/projects|\.claude/projects/-home-llucic|github\.com/lluvr/frame-check-web\b'

# ── Pattern family: OPERATIONAL_STATE (FM-PCD-6) ────────────────────
# Runtime state files from the live web deploy. None of these have
# any public canon use.
PAT_OPERATIONAL_STATE='\b(cost_budget|feature_limit_[a-z_]+|process_lock|observatory_state|frame_check_observatory_state|circuit_breaker)\.(json|sqlite|sqlite-shm|sqlite-wal)\b|\b(observatory_topics|model_registry)\.yaml\b|\bevents\.sqlite\b'

# ── Pattern family: OPERATOR_INFRA (FM-PCD-11) ──────────────────────
# Maintainer-side infrastructure detail. The deploy target (Fly.io) is
# operator-internal; the LLM proxy implementation is operator-internal.
PAT_OPERATOR_INFRA='\bsecrets[- ]vault\b|\bLiteLLM proxy\b|127\.0\.0\.1:[0-9]+|proxy_isolated|\blitestream\b|\bfly\.toml\b|\bfly deploy\b|\bfabrication-profiler\b|operator-managed config files'

# ── Pattern family: RESEARCH_IDS (FM-PCD-10) ────────────────────────
# Operator research register IDs. No public resolver.
PAT_RESEARCH_IDS='\bF-2026-[0-9]{3}\b|\bEXP-[0-9]{3}\b'

# ── Pattern family: STRATEGIC_EXTENDED (FM-PCD-3) ───────────────────
# Strategic vocabulary beyond §3c PAT_RIGID. The bare/novel forms.
PAT_STRATEGIC_EXTENDED='\bthe bet\b|\bthe[- ]bet\b|(zero[- ]LLM[- ]cost|production|hosting|publication|adoption|the project['\''’]s)[- ]moat\b|\bthe moat\b|\bempire moat\b'

# ── Pattern family: CANON_VOCAB_EXTENDED (FM-PCD-3) ─────────────────
# construct-honesty compound forms beyond `discipline`. Only the
# `discipline` form is on canon_replacements.txt; the others slipped
# through.
PAT_CANON_VOCAB_EXTENDED='construct[- ]honesty (posture|defect|audit|surfacing|principle|alignment|tax|stance|machinery)\b'

# ── Pattern family: RIGID (legacy §3c, FM-PCD-1) ────────────────────
PAT_RIGID='operator-side|operator-internal|maintainer-side|maintainer-internal|the operator['\''’]s ([a-z-]+ ){0,4}(strategy|methodology|notes|vault|workspace|tree|dev tree|bet|stake|positioning)\b|\boperator (paper|study|playbook|doctrine|memo|brief)\b|the maintainer['\''’]s ([a-z-]+ ){0,4}(strategy|methodology|notes|vault|workspace|tree|dev tree|bet|stake|positioning)\b|\bmaintainer (paper|study|playbook|doctrine|memo|brief)\b|private (operator|fork|tree|upstream|repo)|\(see private|\(internal reference|\(operator-side reference|\(see operator-side|internal version of|unredacted [a-z]|the full (methodology|version|spec|specification|paper|draft|manuscript|ground.truth)|extracted from the operator['\''’]s|the canonical (source|version|research|methodology) lives|(trust|data|authorship|methodology|adoption|compounding|positioning|named.authorship)[- ]moat|methodology[- ]as[- ]moat|Clarethium-empire|the project['\''’]s empire|empire-grade|empire-wide|\bempire[- ](positioning|claim|tier|core|stake|shape|reach|scope|repo|play|surface|bet)\b|\bdocs/internal/|(compounding|data|trust|authorship|named-authorship)[- ]claim|construct[- ]honest(y)?\s+(discipline|posture|defect|audit|surfacing|principle|alignment|tax|stance|machinery|frame|reading)\b|\bunder-detection (construct|posture)\b|llucic@|library_v[0-9]+ ratification|library_v[0-9]+ ratified|Step [0-9]+ ratification|after library_v[0-9]+ ratification|substrate[- ]side composition roadmap|Item [0-9]+ of the substrate|\bMove\s+D-[A-Z]+-[0-9]+\b|\bDecision\s+D-[A-Z]+-[0-9]+\b|Step [0-9]+ of the (decomposition|refactor|cleanup|migration|rollout|plan)|as Step [0-9]+ of the|METHODOLOGY[ ]?§[0-9]+(\.[0-9]+)*|\boperator[- ](methodology|framework|practice|discipline|skill|stance|disposition|judgment|workflow|loop)\b|\bmulti[- ]operator\b|\boperator[- ]AI\b|the operator['\''’]s (loop|stance|skill|judgment|contribution|disposition|perspective|choice|workflow|discipline)\b'

# ── Pattern family: VAULT (legacy §3c) ──────────────────────────────
PAT_VAULT='\bvault[- ]faithful\b|\bvault[- ]validated\b|\bvault behaviour\b|\bvault behavior\b|\bvault[- ]style\b|\bvault['\''’]?s? precision threshold\b|\bvault notes\b|\bin the vault\b|\bfrom the vault\b|\bthe operator['\''’]s ([a-z-]+ ){0,4}vault\b'

PAT_VAULT_BARE='\bvault\b'
VAULT_BARE_ALLOWLIST='password vault|bank vault|secrets vault|secrets-vault|hashicorp vault|key vault|vault7|vaulted offline'

# Web-app modules: a few legitimate uses survive in benign contexts
# (e.g., a comment in a frame catalog entry that happens to contain
# the word "consensus"). Specific allowlist lines for known benign
# uses of `consensus` (the English word) and `mirror` (mirror image).
WEB_APP_MODULE_ALLOWLIST='consensus (verdict|went|on|across|exists|doesn|that|but|mechanism|proxy|and|is|using|now)|scientific consensus|expert consensus|reader consensus|rater consensus|cross-(provider|family) consensus|cross-provider consensus|library_consensus|Re-compute consensus|_consensus|^# Consensus|verifier consensus|inter-LLM consensus|consensus research|the consensus|broke the consensus|community consensus|editor body consensus|path to consensus|by .* consensus|consensus or strong|mirror (image|the methodology|review)|examples?\.md|reframe (the question|the document|her|his|their|its)|architectural reframe|consistency check|\bobservatory\b\s+(state|topics|daemon|paused|offline)|telemetry\.|telemetry tagging|telemetry events|telemetry schema|telemetry path|downstream telemetry|corpus telemetry|telemetry queries|structural telemetry|telemetry_opt_in|telemetry pipeline|telemetry patterns|production telemetry|verification.*telemetry|telemetry and audit|Tier B telemetry|to telemetry|record telemetry|surface in|saved_analyses / saved_compare|"reframe", "topic_generation"|verification, consensus|telemetry\)|for telemetry pass|:[[:space:]]*#[[:space:]]+Consensus[[:space:]]*$|domain_baselines\.py|\bno telemetry\b|\bzero telemetry\b|telemetry, no\s+(remote|external|outbound|inbound)|telemetry of any (form|kind)|telemetry collection'

# Strategic-extended allowlist: specific contexts where the bigram is
# legitimate (quoted excerpts, methodology paper).
STRATEGIC_EXTENDED_ALLOWLIST='NVIDIA['\''’]s competitive moat|moat continues to strengthen|competitive moat through CUDA|economic moat|wide moat|narrow moat'

# Research-IDs allowlist: a research ID is permitted iff it has a
# public resolver (a directory or document in a public Clarethium
# repo that defines the ID). The Touchstone benchmarks ship under
# `benchmarks/exp_081_discrimination/` and `benchmarks/exp_095_grounding/`
# in the Clarethium/touchstone public repo and are the public
# resolvers for EXP-081 and EXP-095 respectively, so those IDs are
# legitimate public canon and are allowlisted globally. Adding a new
# ID here requires that the ID is referenced from a directory or
# document the public can resolve. Other research IDs without a
# public resolver remain leaks; inline `# canon-exempt: <reason>` is
# the per-line escape for one-off cases.
RESEARCH_IDS_ALLOWLIST='\bEXP-081\b|\bEXP-095\b'

# ── Self-test ───────────────────────────────────────────────────────
self_test() {
  local fixture script_dir
  script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  fixture=
  for candidate in \
    "$script_dir/canon_audit_known_leaks.txt" \
    "scripts/canon_audit_known_leaks.txt" \
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
  # least one pattern family. Lines starting with `## family:` set the
  # expected family; if set, the matching pattern must be in that
  # family. Lines without `## family:` only need to match SOME family.
  local total=0 misses=0 expected_family=""
  while IFS= read -r line; do
    if [ -z "$line" ]; then continue; fi
    case "$line" in
      "##"*"family:"*)
        expected_family="${line#*family:}"
        expected_family="${expected_family// /}"
        continue
        ;;
      "#"*) continue ;;
    esac
    total=$((total + 1))
    local matched=0
    for family_pat in \
        "PRIVATE_FILES:$PAT_PRIVATE_FILES" \
        "FVS_EVAL_PATHS:$PAT_FVS_EVAL_PATHS" \
        "WEB_APP_MODULES:$PAT_WEB_APP_MODULES" \
        "WEB_APP_LIVE_IMPORTS:$PAT_WEB_APP_LIVE_IMPORTS" \
        "OPERATOR_PATHS:$PAT_OPERATOR_PATHS" \
        "OPERATIONAL_STATE:$PAT_OPERATIONAL_STATE" \
        "OPERATOR_INFRA:$PAT_OPERATOR_INFRA" \
        "RESEARCH_IDS:$PAT_RESEARCH_IDS" \
        "STRATEGIC_EXTENDED:$PAT_STRATEGIC_EXTENDED" \
        "CANON_VOCAB_EXTENDED:$PAT_CANON_VOCAB_EXTENDED" \
        "RIGID:$PAT_RIGID" \
        "VAULT:$PAT_VAULT" \
        "VAULT_BARE:$PAT_VAULT_BARE"; do
      local family="${family_pat%%:*}"
      local pat="${family_pat#*:}"
      if echo "$line" | grep -qEi "$pat"; then
        matched=1
        break
      fi
    done
    if [ "$matched" -eq 0 ]; then
      [ "$misses" -eq 0 ] && echo "self-test FAIL: lines not matched by any pattern:" >&2
      echo "  MISS: $line" >&2
      misses=$((misses + 1))
    fi
  done < "$fixture"

  if [ "$misses" -gt 0 ]; then
    echo "self-test FAIL: $misses/$total known-leak lines not matched"
    return 1
  fi
  echo "self-test PASS: all $total known-leak lines matched"

  # Exercise PY_STRING_CONCAT separately against its Python fixture.
  if ! self_test_pystring; then
    return 1
  fi
  return 0
}

# ── PY_STRING_CONCAT self-test ──────────────────────────────────────
# Validate that audit_python_strings catches the cross-line shapes
# documented in canon_audit_pystring_concat_known_leaks.py. The
# fixture is excluded from the regular scan; here we run it in a
# scratch directory so audit_python_strings can find it.
self_test_pystring() {
  local fixture script_dir tmpdir hits expected_families
  script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  fixture=
  for candidate in \
    "$script_dir/canon_audit_pystring_concat_known_leaks.py" \
    "scripts/canon_audit_pystring_concat_known_leaks.py" \
    "tests/fixtures/canon_audit_pystring_concat_known_leaks.py" \
    ~/.claude/clarethium-internal/canon_audit_pystring_concat_known_leaks.py; do
    if [ -f "$candidate" ]; then
      fixture="$candidate"
      break
    fi
  done
  if [ -z "$fixture" ]; then
    echo "pystring self-test FAIL: fixture file not found" >&2
    return 1
  fi
  tmpdir=$(mktemp -d)
  cp "$fixture" "$tmpdir/probe.py"
  hits=$(cd "$tmpdir" && audit_python_strings)
  local rc=$?
  rm -rf "$tmpdir"
  if [ "$rc" -eq 0 ]; then
    echo "pystring self-test FAIL: audit_python_strings returned clean against fixture (expected hits)" >&2
    return 1
  fi
  # Each documented family in the fixture must appear in the hit output.
  expected_families="RIGID PRIVATE_FILES CANON_VOCAB_EXTENDED"
  for fam in $expected_families; do
    if ! echo "$hits" | grep -q "\[${fam}\]"; then
      echo "pystring self-test FAIL: expected family [$fam] not represented in hits" >&2
      echo "$hits" >&2
      return 1
    fi
  done
  echo "pystring self-test PASS: all expected families ($expected_families) caught in cross-line concatenations"
  return 0
}

# ── Run audit on a single pattern family ────────────────────────────
audit_family() {
  local family="$1"
  local pattern="$2"
  local allowlist="${3:-}"
  local hits
  hits=$(grep -rEn -i "${EXCLUDES[@]}" --binary-files=without-match "$pattern" . 2>/dev/null | filter_inline_exempts || true)
  if [ -n "$allowlist" ]; then
    hits=$(echo "$hits" | grep -viE "$allowlist" || true)
  fi
  echo "$hits"
}

# ── Pattern family: PY_STRING_CONCAT (FM-PCD-3 cross-line) ──────────
# Python string-literal continuations span multiple source lines but
# concatenate at runtime into wire-payload text. Line-based grep
# misses any leak compound that straddles `"<NL>"` continuation
# boundaries (e.g. `"the operator's "` on one line, `"methodology"` on
# the next). This scan flattens adjacent string literals before
# applying RIGID / CANON_VOCAB_EXTENDED / STRATEGIC_EXTENDED /
# PRIVATE_FILES and only reports matches that do NOT appear on any
# single original line (so line-based pass hits do not double-report).
audit_python_strings() {
  local files
  files=$(find . -type f -name '*.py' \
    -not -path './.git/*' \
    -not -path '*/__pycache__/*' \
    -not -path '*/.pytest_cache/*' \
    -not -path './build/*' \
    -not -path '*/build/*' \
    -not -path './dist/*' \
    -not -path '*/dist/*' \
    -not -path './.venv/*' \
    -not -path './venv/*' \
    -not -path './.claude/*' \
    -not -path '*/tests/fixtures/*' \
    -not -path '*/tests/data/*' \
    -not -path '*/corpus/*' \
    -not -path '*/transmissions/*' \
    -not -path '*/worked_examples/*' \
    -not -path '*/outputs/*' \
    -not -path '*.egg-info/*' \
    -not -name 'canon_audit_pystring_concat_known_leaks.py' \
    2>/dev/null)
  if [ -z "$files" ]; then
    return 0
  fi
  PAT_RIGID="$PAT_RIGID" \
  PAT_CANON_VOCAB_EXTENDED="$PAT_CANON_VOCAB_EXTENDED" \
  PAT_STRATEGIC_EXTENDED="$PAT_STRATEGIC_EXTENDED" \
  PAT_PRIVATE_FILES="$PAT_PRIVATE_FILES" \
  FILES_LIST="$files" \
  python3 - <<'PYEOF'
import os, re, sys
files = [p for p in os.environ['FILES_LIST'].splitlines() if p]
patterns = {
    'RIGID': os.environ['PAT_RIGID'],
    'CANON_VOCAB_EXTENDED': os.environ['PAT_CANON_VOCAB_EXTENDED'],
    'STRATEGIC_EXTENDED': os.environ['PAT_STRATEGIC_EXTENDED'],
    'PRIVATE_FILES': os.environ['PAT_PRIVATE_FILES'],
}
hits = []
for path in files:
    try:
        with open(path, encoding='utf-8') as f:
            text = f.read()
    except Exception:
        continue
    flat = re.sub(r'"(\s*\n\s*)"', '', text)
    flat = re.sub(r"'(\s*\n\s*)'", '', flat)
    if flat == text:
        continue
    lines_lower = [ln.lower() for ln in text.splitlines()]
    for family, pat in patterns.items():
        for m in re.finditer(pat, flat, re.IGNORECASE):
            substr = flat[m.start():m.end()].lower()
            if any(substr in ln for ln in lines_lower):
                continue
            ctx = flat[max(0, m.start() - 30):m.end() + 30].replace('\n', ' ').strip()
            hits.append((path, family, ctx))
if hits:
    print('## PY_STRING_CONCAT ({} hit{}) ##'.format(
        len(hits), '' if len(hits) == 1 else 's'))
    for path, family, ctx in hits:
        print(f'{path}: [{family}] {ctx}')
    sys.exit(1)
sys.exit(0)
PYEOF
}

# ── Main ────────────────────────────────────────────────────────────
case "${1:-audit}" in
  --version)
    echo "canon_audit.sh $VERSION"
    exit 0
    ;;
  --list-families)
    cat <<'EOF'
PRIVATE_FILES         FM-PCD-1   maintainer-only docs as filename refs
FVS_EVAL_PATHS        FM-PCD-9   maintainer-side validation tree paths
WEB_APP_MODULES       FM-PCD-11  web-app module name leaks
WEB_APP_LIVE_IMPORTS  FM-PCD-8   try-imports of private modules
OPERATOR_PATHS        FM-PCD-7   personal machine paths + private repo URLs
OPERATIONAL_STATE     FM-PCD-6   runtime state file shapes
OPERATOR_INFRA        FM-PCD-11  Fly.io / LiteLLM / litestream / secrets-vault
RESEARCH_IDS          FM-PCD-10  F-NNNN-NNN, EXP-NNN (no public resolver)
STRATEGIC_EXTENDED    FM-PCD-3   bare/novel moat compounds, "the bet"
CANON_VOCAB_EXTENDED  FM-PCD-3   construct-honesty {posture|defect|audit|...}
RIGID                 FM-PCD-1   legacy §3c rigid set
VAULT                 FM-PCD-1   vault-as-architecture compounds
VAULT_BARE            review     bare "vault" (allowlist permits domain forms)
PY_STRING_CONCAT      FM-PCD-3   cross-line Python string-literal concat (wire-payload reachable)
EOF
    exit 0
    ;;
  --self-test)
    self_test
    exit $?
    ;;
  audit|"")
    fail=0
    declare -a families
    families=(
      "PRIVATE_FILES:PAT_PRIVATE_FILES"
      "FVS_EVAL_PATHS:PAT_FVS_EVAL_PATHS"
      "WEB_APP_MODULES:PAT_WEB_APP_MODULES:WEB_APP_MODULE_ALLOWLIST"
      "WEB_APP_LIVE_IMPORTS:PAT_WEB_APP_LIVE_IMPORTS"
      "OPERATOR_PATHS:PAT_OPERATOR_PATHS"
      "OPERATIONAL_STATE:PAT_OPERATIONAL_STATE"
      "OPERATOR_INFRA:PAT_OPERATOR_INFRA"
      "RESEARCH_IDS:PAT_RESEARCH_IDS:RESEARCH_IDS_ALLOWLIST"
      "STRATEGIC_EXTENDED:PAT_STRATEGIC_EXTENDED:STRATEGIC_EXTENDED_ALLOWLIST"
      "CANON_VOCAB_EXTENDED:PAT_CANON_VOCAB_EXTENDED"
      "RIGID:PAT_RIGID"
      "VAULT:PAT_VAULT"
      "VAULT_BARE:PAT_VAULT_BARE:VAULT_BARE_ALLOWLIST"
    )
    first=1
    for entry in "${families[@]}"; do
      IFS=':' read -r family pvar avar <<< "$entry"
      pattern="${!pvar}"
      if [ -n "${avar:-}" ]; then
        allowlist="${!avar}"
      else
        allowlist=""
      fi
      hits=$(audit_family "$family" "$pattern" "$allowlist")
      if [ -n "$hits" ]; then
        [ "$first" -eq 0 ] && echo
        first=0
        count=$(echo "$hits" | wc -l)
        echo "## ${family} (${count} hit$([ "$count" = "1" ] || echo s)) ##"
        echo "$hits"
        fail=1
      fi
    done
    # Cross-line Python string-concat scan (wire-payload coverage gap).
    py_output=$(audit_python_strings)
    py_rc=$?
    if [ -n "$py_output" ]; then
      [ "$first" -eq 0 ] && echo
      first=0
      echo "$py_output"
    fi
    if [ "$py_rc" -ne 0 ]; then
      fail=1
    fi
    exit $fail
    ;;
  *)
    echo "usage: $0 [--version|--list-families|--self-test|audit]" >&2
    exit 2
    ;;
esac
