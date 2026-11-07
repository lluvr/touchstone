"""Sign-constrained refit of the substrate-only calibration.

The default ``substrate_only`` calibration in
``DEFAULT_CALIBRATION_2026_05_17`` carries a negative coefficient on
``l4_unsourced``: on its own, a higher share of unsourced numbers lowers
``prob_hallucinated``. This script asks whether a fit that forbids that
inversion costs any discrimination, and whether it moves the scores of
texts with swapped or fabricated numbers.

What it does:

1. Reproduces the original fit exactly. The RAGTruth Summary pair file
   (900 rows, the source of every RAGTruth snapshot here) is split per
   class: positive and negative row indices are each shuffled with
   ``numpy.random.default_rng(0)`` (positives first, same generator),
   the first ``int(0.7 * n)`` of each class go to train (n_train=629,
   n_test=271) and the rest to test. ``sklearn``'s
   ``LogisticRegression()`` with default settings on the train rows
   returns the shipped coefficients; the script checks this.
2. Fits the constrained alternative on the same rows: the four
   "more unsupported means more likely hallucinated" features
   (``l6_inv``, ``l4_unsourced``, ``l11_p``, ``l5_entity_unsourced``) are
   bounded at zero from below; the two count features are free. Only the
   ``l4_unsourced`` bound is active, so the bounded optimum is the refit
   without that feature. The shipped candidate is that refit, made with
   the same sklearn solver as the default; a bounded L-BFGS-B fit of the
   same objective is reported alongside as a check.
3. Reports AUC with the repo's stratified bootstrap 95% CI
   (``_bootstrap.bootstrap_auc_ci``) for both fits on: the true
   RAGTruth held-out rows (n=271), the RAGTruth / SummEval / HaluEval
   n=400 subsamples the published figures use, and the RAGTruth n=400
   eval half behind the published "out of sample" 0.633. Also a paired
   bootstrap on the AUC difference, the sign stability of the
   unconstrained ``l4_unsourced`` coefficient over bootstrap resamples
   of the training rows, and the scores on the five strict-xfail cases
   in ``tests/``.
4. Applies the decision rule: switch the default only if the
   constrained held-out AUC on every corpus is inside the current fit's
   95% CI or better, AND swapped and fabricated numbers raise the score
   above the verbatim copy.

Dependencies beyond the library: ``numpy``, ``scikit-learn`` and
``scipy`` (results recorded with scikit-learn 1.9.1).

Run::

    # Once, to extract the 900-row feature snapshot from the pinned pair file.
    python -m benchmarks.external.constrained_calibration extract \\
        --pairs /tmp/alignscore_corpora/ragtruth_summary.json

    # The evaluation reads only committed snapshots.
    python -m benchmarks.external.constrained_calibration

The pair file is ``[{"context", "output", "label"}]`` for the
``task_type == "Summary"`` rows of the ``wandb/RAGTruth-processed`` test
split in dataset order, label 1 when ``hallucination_labels`` is
non-empty, written with ``json.dumps`` defaults. Built that way it
matches the SHA-256 pinned in ``data_hashes_2026-05-19.json``;
``extract`` refuses any other file.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
from collections import OrderedDict
from pathlib import Path
from typing import Any

from benchmarks.external._bootstrap import auc_roc, bootstrap_auc_ci
from benchmarks.external._paired_tests import paired_bootstrap_auc_diff
from benchmarks.external.recalibrate_substrate import _stratified_interleave_indices

EXT = Path("benchmarks/external")
FEATURES_N900 = EXT / "ragtruth_summary/results/substrate_features_n900_2026-11-07.json"
OUT_PATH = EXT / "constrained_calibration_2026-11-07.json"
FEATURE_NAMES = [
    "l6_inv",
    "l4_unsourced",
    "l4_n_total_norm",
    "l11_p",
    "l5_entity_unsourced",
    "l5_n_entities_norm",
]
# Features where a higher value means more unsupported content.
NONNEGATIVE = {"l6_inv", "l4_unsourced", "l11_p", "l5_entity_unsourced"}
N400_CORPORA = [
    ("ragtruth_summary", "RAGTruth Summary"),
    ("summeval", "SummEval"),
    ("halueval_summarization", "HaluEval Summarization"),
]

# The five strict-xfail cases (tests/test_verifier.py and
# tests/test_grounding_decomposition.py), all against the same source.
NUMERIC_SOURCE = (
    "Apple reported Q1 fiscal 2026 revenue of $143 billion. The iPhone "
    "segment grew 8% year-over-year. Tim Cook commented on AI investments "
    "during the earnings call. Operating margins reached 32%."
)
NUMERIC_SWAPPED = NUMERIC_SOURCE.replace("$143", "$134").replace("32%", "23%")
NUMERIC_FABRICATED = (
    "Apple reported Q1 fiscal 2026 revenue of $197 billion. The iPhone "
    "segment grew 41% year-over-year. Tim Cook commented on AI investments "
    "during the earnings call. Operating margins reached 59%."
)
DIGIT_SWAP_SENTENCE = "Apple reported Q1 fiscal 2026 revenue of $134 billion."
SHORT_SENTENCE_TEXT = "Apple reported Q1 fiscal 2026 revenue of $143 billion. Margins reached 59%."
TABLE_TEXT = (
    "Apple reported Q1 fiscal 2026 revenue of $143 billion.\n\n"
    "| Metric | Value |\n"
    "|---|---|\n"
    "| Operating margin for the quarter | 59% |\n"
)


# --- extraction --------------------------------------------------------------


def extract(pairs_path: Path) -> None:
    from clarethium_touchstone import measure
    from clarethium_touchstone.verifier import _extract_substrate_features

    manifest = json.loads((EXT / "data_hashes_2026-05-19.json").read_text())
    pinned = manifest["source_pair_files"]["ragtruth_summary"]["sha256"]
    digest = hashlib.sha256(pairs_path.read_bytes()).hexdigest()
    if digest != pinned:
        raise SystemExit(f"{pairs_path}: sha256 {digest} does not match pinned {pinned}")
    pairs = json.loads(pairs_path.read_text())
    features = [
        _extract_substrate_features(measure(p["output"], source=p["context"])) for p in pairs
    ]
    labels = [int(p["label"]) for p in pairs]

    n400 = json.loads(
        (EXT / "ragtruth_summary/results/substrate_features_n400_2026-05-19.json").read_text()
    )
    if features[:400] != n400["per_example_features"]:
        raise SystemExit("first 400 rows differ from substrate_features_n400_2026-05-19.json")
    if labels[:400] != n400["per_example_label_hallucinated"]:
        raise SystemExit("first 400 labels differ from the n=400 snapshot")

    out: OrderedDict[str, Any] = OrderedDict()
    out["experiment"] = (
        "Per-pair substrate feature extraction on RAGTruth Summary (full test split)"
    )
    out["corpus"] = "ragtruth_summary"
    out["source_sha256"] = digest
    out["n_total_pairs"] = len(pairs)
    out["feature_names"] = FEATURE_NAMES
    out["per_example_features"] = features
    out["per_example_label_hallucinated"] = labels
    FEATURES_N900.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Wrote {FEATURES_N900} ({len(pairs)} rows; first 400 match the n=400 snapshot)")


# --- fitting -----------------------------------------------------------------


def original_split(labels: list[int]) -> tuple[list[int], list[int]]:
    """The 70/30 per-class split the default calibration was fit on."""
    import numpy as np

    y = np.array(labels)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    rng = np.random.default_rng(0)
    rng.shuffle(pos)
    rng.shuffle(neg)
    n_pos = int(0.7 * len(pos))
    n_neg = int(0.7 * len(neg))
    train = [int(i) for i in np.r_[pos[:n_pos], neg[:n_neg]]]
    test = [int(i) for i in np.r_[pos[n_pos:], neg[n_neg:]]]
    return train, test


def fit_sklearn(rows: list[dict[str, float]], y: list[int], names: list[str]) -> dict[str, Any]:
    from sklearn.linear_model import LogisticRegression

    model = LogisticRegression(max_iter=10000).fit([[r[f] for f in names] for r in rows], y)
    return {
        "intercept": float(model.intercept_[0]),
        "coef": {f: float(c) for f, c in zip(names, model.coef_[0], strict=True)},
    }


def fit_bounded(rows: list[dict[str, float]], y: list[int]) -> dict[str, Any]:
    """sklearn's objective (L2 with C=1, unpenalized intercept) under bounds."""
    import numpy as np
    from scipy.optimize import minimize

    x = np.array([[r[f] for f in FEATURE_NAMES] for r in rows])
    t = np.array(y, dtype=float)

    def objective(theta: Any) -> tuple[float, Any]:
        b, w = theta[0], theta[1:]
        z = b + x @ w
        p = 1.0 / (1.0 + np.exp(-z))
        loss = float(np.sum(np.logaddexp(0.0, z) - t * z) + 0.5 * w @ w)
        grad = np.r_[np.sum(p - t), x.T @ (p - t) + w]
        return loss, grad

    bounds = [(None, None)] + [
        (0.0, None) if f in NONNEGATIVE else (None, None) for f in FEATURE_NAMES
    ]
    res = minimize(
        objective,
        np.zeros(len(FEATURE_NAMES) + 1),
        jac=True,
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": 10000, "gtol": 1e-10, "ftol": 1e-15},
    )
    return {
        "intercept": float(res.x[0]),
        "coef": {f: float(c) for f, c in zip(FEATURE_NAMES, res.x[1:], strict=True)},
    }


def predict(rows: list[dict[str, float]], calib: dict[str, Any]) -> list[float]:
    out = []
    for r in rows:
        z = calib["intercept"] + sum(c * r[f] for f, c in calib["coef"].items())
        out.append(1.0 / (1.0 + math.exp(-z)))
    return out


def _rounded(calib: dict[str, Any]) -> dict[str, Any]:
    return {
        "intercept": round(calib["intercept"], 6),
        "coef": {f: round(c, 6) for f, c in calib["coef"].items()},
    }


# --- evaluation --------------------------------------------------------------


def _xfail_cases(current: dict[str, Any], constrained: dict[str, Any]) -> dict[str, Any]:
    from clarethium_touchstone import Verifier
    from clarethium_touchstone._calibration import DEFAULT_CALIBRATION_2026_05_17
    from clarethium_touchstone.measure import grounding_decomposition

    alt = copy.deepcopy(DEFAULT_CALIBRATION_2026_05_17)
    alt["substrate_only"] = constrained
    verifiers = {"current": Verifier(), "constrained": Verifier(calibration=alt)}
    assert DEFAULT_CALIBRATION_2026_05_17["substrate_only"] == current

    texts = {
        "verbatim_copy": NUMERIC_SOURCE,
        "swapped": NUMERIC_SWAPPED,
        "fabricated": NUMERIC_FABRICATED,
        "digit_swap_sentence": DIGIT_SWAP_SENTENCE,
        "short_sentence": SHORT_SENTENCE_TEXT,
        "table_row": TABLE_TEXT,
    }
    probs: dict[str, dict[str, float]] = {}
    flags: dict[str, dict[str, bool]] = {}
    for name, v in verifiers.items():
        probs[name] = {}
        flags[name] = {}
        for label, text in texts.items():
            r = v.score(text, source=NUMERIC_SOURCE)
            probs[name][label] = round(r.prob_hallucinated, 4)
            flags[name][label] = r.should_flag()

    def l11_sentences(text: str) -> list[dict[str, Any]]:
        return list(grounding_decomposition(text, NUMERIC_SOURCE)["sentence_classifications"])

    digit = l11_sentences(DIGIT_SWAP_SENTENCE)
    cases: OrderedDict[str, Any] = OrderedDict()
    for name in verifiers:
        p = probs[name]
        cases[name] = OrderedDict(
            [
                (
                    "test_swapped_numbers_score_above_verbatim_copy",
                    {
                        "swapped": p["swapped"],
                        "verbatim_copy": p["verbatim_copy"],
                        "passes": p["swapped"] > p["verbatim_copy"],
                    },
                ),
                (
                    "test_fabricated_numbers_flag_at_default_threshold",
                    {"fabricated": p["fabricated"], "passes": flags[name]["fabricated"]},
                ),
                (
                    "test_digit_swapped_number_is_not_grounded",
                    {
                        "verifier_prob": p["digit_swap_sentence"],
                        "passes": len(digit) == 1 and digit[0]["primary"] != "G",
                        "calibration_dependent": False,
                    },
                ),
                (
                    "test_short_sentence_with_fabricated_number_is_classified",
                    {
                        "verifier_prob": p["short_sentence"],
                        "passes": any(
                            "59%" in s.get("sentence", "")
                            for s in l11_sentences(SHORT_SENTENCE_TEXT)
                        ),
                        "calibration_dependent": False,
                    },
                ),
                (
                    "test_markdown_table_row_with_fabricated_number_is_classified",
                    {
                        "verifier_prob": p["table_row"],
                        "passes": any(
                            "59%" in s.get("sentence", "") for s in l11_sentences(TABLE_TEXT)
                        ),
                        "calibration_dependent": False,
                    },
                ),
            ]
        )
    return cases


def _l4_sign_stability(
    rows: list[dict[str, float]], y: list[int], n_resamples: int = 200
) -> dict[str, Any]:
    rng = random.Random(0)
    pos = [i for i, lab in enumerate(y) if lab == 1]
    neg = [i for i, lab in enumerate(y) if lab == 0]
    coefs = []
    for _ in range(n_resamples):
        idx = [pos[rng.randrange(len(pos))] for _ in pos] + [
            neg[rng.randrange(len(neg))] for _ in neg
        ]
        fit = fit_sklearn([rows[i] for i in idx], [y[i] for i in idx], FEATURE_NAMES)
        coefs.append(fit["coef"]["l4_unsourced"])
    coefs.sort()
    return {
        "n_resamples": n_resamples,
        "fraction_negative": round(sum(1 for c in coefs if c < 0) / n_resamples, 4),
        "median": round(coefs[n_resamples // 2], 4),
        "p2_5": round(coefs[int(0.025 * n_resamples)], 4),
        "p97_5": round(coefs[int(0.975 * n_resamples) - 1], 4),
    }


def evaluate() -> dict[str, Any]:
    from clarethium_touchstone._calibration import DEFAULT_CALIBRATION_2026_05_17

    doc = json.loads(FEATURES_N900.read_text())
    rows: list[dict[str, float]] = doc["per_example_features"]
    labels: list[int] = doc["per_example_label_hallucinated"]
    train, test = original_split(labels)
    train_rows = [rows[i] for i in train]
    train_y = [labels[i] for i in train]

    shipped = DEFAULT_CALIBRATION_2026_05_17["substrate_only"]
    refit = fit_sklearn(train_rows, train_y, FEATURE_NAMES)
    repro_diff = max(
        [abs(refit["intercept"] - shipped["intercept"])]
        + [abs(refit["coef"][f] - shipped["coef"][f]) for f in FEATURE_NAMES]
    )
    if repro_diff > 1e-6:
        raise SystemExit(f"could not reproduce the shipped coefficients (max diff {repro_diff})")

    constrained = fit_sklearn(
        train_rows, train_y, [f for f in FEATURE_NAMES if f != "l4_unsourced"]
    )
    bounded = fit_bounded(train_rows, train_y)
    current = shipped

    eval_sets: list[tuple[str, list[dict[str, float]], list[int], str]] = [
        (
            "ragtruth_summary_heldout_n271",
            [rows[i] for i in test],
            [labels[i] for i in test],
            "true held-out rows of the 70/30 split",
        )
    ]
    for corpus, label in N400_CORPORA:
        snap = json.loads(
            (EXT / corpus / "results/substrate_features_n400_2026-05-19.json").read_text()
        )
        r400 = snap["per_example_features"]
        y400 = snap["per_example_label_hallucinated"]
        note = "out of distribution"
        if corpus == "ragtruth_summary":
            note = "first 400 rows; overlaps the training rows"
        eval_sets.append((f"{corpus}_n400", r400, y400, f"{label} n=400 subsample, {note}"))
        if corpus == "ragtruth_summary":
            _, eval_half = _stratified_interleave_indices(y400)
            in_train = len(set(eval_half) & set(train))
            eval_sets.append(
                (
                    "ragtruth_summary_n400_eval_half",
                    [r400[i] for i in eval_half],
                    [y400[i] for i in eval_half],
                    f"published 'out of sample' eval half; {in_train} of "
                    f"{len(eval_half)} rows are training rows of the 70/30 split",
                )
            )

    results: OrderedDict[str, Any] = OrderedDict()
    passes_auc_rule = True
    for name, r, y, note in eval_sets:
        cur_p = predict(r, current)
        con_p = predict(r, constrained)
        cur = bootstrap_auc_ci(cur_p, y)
        con = bootstrap_auc_ci(con_p, y)
        within = con["auc"] >= cur["ci_low"]
        if name != "ragtruth_summary_n400" and name != "ragtruth_summary_n400_eval_half":
            passes_auc_rule = passes_auc_rule and within
        results[name] = {
            "note": note,
            "n": len(y),
            "n_positive": sum(y),
            "current": cur,
            "constrained": con,
            "constrained_within_current_ci_or_better": within,
            "paired_diff_constrained_minus_current": paired_bootstrap_auc_diff(con_p, cur_p, y),
            "l4_unsourced_univariate_auc": round(auc_roc([x["l4_unsourced"] for x in r], y), 4),
        }

    cases = _xfail_cases(current, constrained)
    con_cases = cases["constrained"]
    cur_cases = cases["current"]
    swapped = con_cases["test_swapped_numbers_score_above_verbatim_copy"]
    fabricated = con_cases["test_fabricated_numbers_flag_at_default_threshold"]
    raises_vs_copy = (
        swapped["swapped"] > swapped["verbatim_copy"]
        and fabricated["fabricated"] > swapped["verbatim_copy"]
    )
    raises_vs_current = (
        swapped["swapped"] > cur_cases["test_swapped_numbers_score_above_verbatim_copy"]["swapped"]
        and fabricated["fabricated"]
        > cur_cases["test_fabricated_numbers_flag_at_default_threshold"]["fabricated"]
    )
    switch = passes_auc_rule and raises_vs_copy

    out: OrderedDict[str, Any] = OrderedDict()
    out["experiment"] = "Sign-constrained refit of the substrate_only calibration"
    out["training"] = {
        "corpus": "RAGTruth Summary test split (900 rows)",
        "split": "per class, numpy default_rng(0) shuffle (positives then negatives), "
        "first int(0.7 * n) of each class to train",
        "n_train": len(train),
        "n_test": len(test),
        "fitter": "sklearn LogisticRegression() defaults (L2, C=1.0, lbfgs)",
        "shipped_coefficients_reproduced_max_abs_diff": repro_diff,
    }
    out["calibrations"] = {
        "current": _rounded(current),
        "constrained": _rounded(constrained),
        "constrained_bounded_lbfgsb_check": _rounded(bounded),
        "nonnegative_features": sorted(NONNEGATIVE),
    }
    out["l4_unsourced_coefficient_bootstrap_unconstrained"] = _l4_sign_stability(
        train_rows, train_y
    )
    out["auc"] = results
    out["xfail_cases"] = cases
    out["decision"] = {
        "auc_rule_heldout_ragtruth_summeval_halueval": passes_auc_rule,
        "swapped_and_fabricated_raise_score_above_verbatim_copy": raises_vs_copy,
        "swapped_and_fabricated_score_higher_than_under_current": raises_vs_current,
        "switch_default": switch,
    }
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd")
    ex = sub.add_parser("extract", help="Extract the 900-row RAGTruth feature snapshot.")
    ex.add_argument("--pairs", default="/tmp/alignscore_corpora/ragtruth_summary.json")
    args = p.parse_args()
    if args.cmd == "extract":
        extract(Path(args.pairs))
        return

    out = evaluate()
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out["calibrations"], indent=2))
    for name, r in out["auc"].items():
        cur, con = r["current"], r["constrained"]
        print(
            f"{name:34s} current {cur['auc']:.3f} [{cur['ci_low']:.3f}, {cur['ci_high']:.3f}]"
            f"  constrained {con['auc']:.3f} [{con['ci_low']:.3f}, {con['ci_high']:.3f}]"
        )
    print(json.dumps(out["xfail_cases"], indent=2))
    print(json.dumps(out["decision"], indent=2))
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
