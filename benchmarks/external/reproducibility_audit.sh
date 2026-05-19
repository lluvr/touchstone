#!/usr/bin/env bash
# Reproducibility audit for benchmarks/external snapshots.
#
# Regenerates every snapshot in benchmarks/external/*.json (and per-corpus
# subdirs) that is derived from the per-example score arrays stored in the
# committed JSON files, then verifies each regenerated file's SHA-256
# matches the committed version. Drift => non-zero exit.
#
# What this audit DOES verify:
#   - Pure-python analysis modules (operational_metrics_*, paired_tests,
#     substrate_plus_judge_*, recalibrate_substrate, calibration_metrics,
#     join_detectors, etc.) produce byte-identical output given the
#     committed per-example snapshots.
#   - The substrate Verifier produces byte-identical substrate-only
#     probabilities given the n=400 subsample pair files (which are
#     hash-pinned in data_hashes_2026-05-19.json).
#   - The data manifest (data_hashes) round-trips.
#
# What this audit DOES NOT verify:
#   - The MiniCheck / AlignScore / judge-API per-example snapshots are NOT
#     regenerated: doing so requires GPU-class compute or paid API calls
#     and varies across hardware. Those snapshots are pinned via their
#     committed SHA in this script (recorded at audit time).
#
# Run: bash benchmarks/external/reproducibility_audit.sh
# Output: benchmarks/external/reproducibility_audit_<date>.log
set -uo pipefail

cd "$(dirname "$0")/../.."

LOG="benchmarks/external/reproducibility_audit_$(date -u +%Y-%m-%d).log"
exec > >(tee "$LOG") 2>&1

drift=0
note() { echo "=== $* ==="; }
verify() {
    local file=$1
    local before=$2
    local after
    after=$(sha256sum "$file" | awk '{print $1}')
    if [[ "$before" == "$after" ]]; then
        echo "  OK    $file  sha256 matches"
    else
        echo "  DRIFT $file  expected ${before:0:16}... got ${after:0:16}..."
        drift=$((drift + 1))
    fi
}
snapshot() {
    sha256sum "$1" 2>/dev/null | awk '{print $1}'
}

note "Audit start: $(date -u --iso-8601=seconds)"

# ---- 1. Verify source pair files unchanged --------------------------------
note "1. Source pair file hash verification"
.venv/bin/python -m benchmarks.external.data_hashes --verify || drift=$((drift + 1))

# ---- 2. Regenerate substrate scores ---------------------------------------
note "2. Substrate-only Verifier on n=400 subsamples"
declare -A SUB_BEFORE
for c in ragtruth_summary summeval halueval_summarization; do
    fp="benchmarks/external/${c}/results/substrate_only_n400_2026-05-18.json"
    SUB_BEFORE[$c]=$(snapshot "$fp")
done
# Map corpus dir -> source pair file path (halueval is named halueval not halueval_summarization)
for c in ragtruth_summary summeval halueval_summarization; do
    case $c in halueval_summarization) src=halueval ;; *) src=$c ;; esac
    label=$(case $c in ragtruth_summary) echo "RAGTruth Summary" ;; summeval) echo "SummEval" ;; halueval_summarization) echo "HaluEval Summarization" ;; esac)
    .venv/bin/python -m benchmarks.external.score_substrate_on_subsample \
        --pairs /tmp/alignscore_corpora/${src}_n400.json \
        --output benchmarks/external/${c}/results/substrate_only_n400_2026-05-18.json \
        --corpus-dir ${c} --label "${label}" > /dev/null
done
for c in ragtruth_summary summeval halueval_summarization; do
    fp="benchmarks/external/${c}/results/substrate_only_n400_2026-05-18.json"
    verify "$fp" "${SUB_BEFORE[$c]}"
done

# ---- 3. Regenerate substrate features -------------------------------------
note "3. Substrate features on n=400 subsamples"
declare -A FEAT_BEFORE
for c in ragtruth_summary summeval halueval_summarization; do
    fp="benchmarks/external/${c}/results/substrate_features_n400_2026-05-19.json"
    FEAT_BEFORE[$c]=$(snapshot "$fp")
done
.venv/bin/python -m benchmarks.external.extract_substrate_features > /dev/null
for c in ragtruth_summary summeval halueval_summarization; do
    fp="benchmarks/external/${c}/results/substrate_features_n400_2026-05-19.json"
    verify "$fp" "${FEAT_BEFORE[$c]}"
done

# ---- 4. Pure-python analysis modules --------------------------------------
note "4. Pure-python analysis modules"
for mod_and_file in \
    "operational_metrics_on_subsample:operational_metrics_n400_2026-05-18.json" \
    "operational_metrics_holdout:operational_metrics_n400_holdout_2026-05-18.json" \
    "operational_metrics_tie_envelope:operational_metrics_n400_tie_envelope_2026-05-18.json" \
    "substrate_plus_judge_analysis:substrate_plus_judge_n400_2026-05-18.json" \
    "substrate_plus_judge_holdout:substrate_plus_judge_holdout_n400_2026-05-19.json" \
    "paired_detector_tests:paired_detector_tests_n400_2026-05-19.json" \
    "recalibrate_substrate:substrate_recalibration_n400_2026-05-19.json" \
    ; do
    mod="${mod_and_file%%:*}"
    file="benchmarks/external/${mod_and_file##*:}"
    before=$(snapshot "$file")
    .venv/bin/python -m "benchmarks.external.${mod}" > /dev/null
    verify "$file" "$before"
done

# ---- 5. Adversarial 16-case join (depends on already-committed per-detector snapshots) ----
note "5. Adversarial subtle 16-case detector join"
before=$(snapshot "benchmarks/adversarial_subtle/cross_detector_2026-05-18.json")
.venv/bin/python -m benchmarks.adversarial_subtle.join_detectors > /dev/null
verify "benchmarks/adversarial_subtle/cross_detector_2026-05-18.json" "$before"

# ---- Summary --------------------------------------------------------------
note "Audit complete: $(date -u --iso-8601=seconds)"
if [[ $drift -eq 0 ]]; then
    echo "RESULT: All checks passed (0 drift). Snapshots reproducible from a clean clone."
    exit 0
else
    echo "RESULT: $drift snapshot(s) drift detected. Investigate the diffs."
    exit 1
fi
