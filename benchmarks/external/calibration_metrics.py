"""Calibration metrics on the n=400 cross-detector scores.

§4.2.1 noted that the Grok edge is the most robust under holdout, with
two competing readings: (a) the cued judge is genuinely robust;
(b) the judge prompt induces highly-clustered probabilities so the
threshold is less sensitive to which subset chose it. This script
computes per-detector per-corpus calibration metrics to disentangle:

- **Expected Calibration Error (ECE)** with 10 equal-width bins on
  [0, 1]. ECE = sum over bins of (n_bin / N) * |mean_prob_in_bin -
  fraction_positive_in_bin|. A well-calibrated detector has ECE ≈ 0;
  an over-confident detector has positive bias on bins near 1.0
  (says 0.95 when truth is 0.6).
- **Maximum Calibration Error (MCE)** = max over bins of
  |mean_prob_in_bin - fraction_positive_in_bin|. ECE-style bias
  concentrated in one bin shows up as a large MCE/ECE ratio.
- **Brier score** = mean over examples of (prob - label)^2. Lower
  is better; the Brier score decomposes into reliability +
  resolution - uncertainty (Murphy 1973). Brier is bounded above
  by base_rate * (1 - base_rate) for a random scorer and below by
  0 for a perfect calibrated scorer.
- **Reliability diagram** per detector: for each non-empty bin,
  emit (bin_lower, bin_upper, n_bin, mean_prob_in_bin,
  fraction_positive_in_bin). The diagram is the visual companion to
  ECE; clusters of bins on the diagonal mean well-calibrated.

The substrate L6 / MiniCheck / AlignScore scores are NOT calibrated
probabilities by construction (lexical-overlap raw scores; NLI
logits-into-softmax; regression heads). Their ECE/Brier are still
meaningful as comparison numbers — the question is which detector's
raw score is closest to a usable probability without post-hoc
calibration.

Run::

    python -m benchmarks.external.calibration_metrics
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from benchmarks.external.operational_metrics_on_subsample import (
    CORPORA,
    _load_detector_scores_on_subsample,
)

N_BINS = 10


def _bin_metrics(
    scores: list[float], labels: list[int], n_bins: int = N_BINS
) -> list[dict[str, Any]]:
    """Per-bin (bin_lower, bin_upper, n, mean_prob_in_bin, frac_positive_in_bin)."""
    n = len(scores)
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for s, lab in zip(scores, labels, strict=True):
        # Clip score to [0, 1] so out-of-range scores still bin sensibly.
        s_clip = max(0.0, min(1.0, s))
        idx = min(n_bins - 1, int(s_clip * n_bins))
        bins[idx].append((s_clip, lab))
    out: list[dict[str, Any]] = []
    for i, bin_data in enumerate(bins):
        if not bin_data:
            continue
        n_bin = len(bin_data)
        mean_prob = sum(s for s, _ in bin_data) / n_bin
        frac_pos = sum(lab for _, lab in bin_data) / n_bin
        out.append(
            {
                "bin_lower": round(i / n_bins, 2),
                "bin_upper": round((i + 1) / n_bins, 2),
                "n": n_bin,
                "frac_of_total": round(n_bin / n, 4),
                "mean_prob_in_bin": round(mean_prob, 4),
                "frac_positive_in_bin": round(frac_pos, 4),
                "calibration_gap": round(mean_prob - frac_pos, 4),
            }
        )
    return out


def _calibration_metrics(scores: list[float], labels: list[int]) -> dict[str, Any]:
    n = len(scores)
    n_pos = sum(labels)
    base_rate = n_pos / n if n else 0.0
    # Brier score on raw scores (clip to [0,1] for the detectors whose
    # raw scores leak outside [0,1], which can happen for word_overlap_inv).
    brier = (
        sum((max(0.0, min(1.0, s)) - lab) ** 2 for s, lab in zip(scores, labels, strict=True)) / n
    )
    bins = _bin_metrics(scores, labels)
    ece = sum(b["frac_of_total"] * abs(b["calibration_gap"]) for b in bins)
    mce = max((abs(b["calibration_gap"]) for b in bins), default=0.0)
    # Random-scorer reference Brier = base_rate * (1 - base_rate). Lower is better.
    random_brier = base_rate * (1.0 - base_rate)
    # Brier skill score: positive = better than random.
    brier_skill = 1.0 - (brier / random_brier) if random_brier > 0 else 0.0
    return {
        "n_total": n,
        "n_positive": n_pos,
        "base_rate": round(base_rate, 4),
        "ece_10bin": round(ece, 4),
        "mce_10bin": round(mce, 4),
        "brier_score": round(brier, 4),
        "random_scorer_brier": round(random_brier, 4),
        "brier_skill_score": round(brier_skill, 4),
        "reliability_diagram_bins": bins,
    }


def main() -> None:
    out: OrderedDict[str, Any] = OrderedDict()
    print()
    for corpus_dir, label, judge_snap_rel in CORPORA:
        print(f"=== {label} (n=400) ===")
        labels, detectors = _load_detector_scores_on_subsample(corpus_dir, judge_snap_rel)
        per_detector: OrderedDict[str, Any] = OrderedDict()
        for name, scores in detectors.items():
            m = _calibration_metrics(scores, labels)
            per_detector[name] = m
            print(
                f"  {name:42s}  ECE={m['ece_10bin']:.3f}  MCE={m['mce_10bin']:.3f}  "
                f"Brier={m['brier_score']:.3f}  BSS={m['brier_skill_score']:+.3f}  "
                f"(random Brier={m['random_scorer_brier']:.3f})"
            )
        out[corpus_dir] = {
            "label": label,
            "n_subsample": len(labels),
            "n_positive": sum(labels),
            "n_bins": N_BINS,
            "per_detector": per_detector,
        }
        print()
    out_path = Path("benchmarks/external/calibration_metrics_n400_2026-05-18.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
