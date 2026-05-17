"""Default calibration coefficients for the production Verifier.

Trained on RAGTruth Summary test split (70/30 stratified, seed=0; n_train=629, n_test=271).
See docs/methodology.md for the training procedure and the honest accuracy
envelope these coefficients deliver on held-out corpora.
"""

from __future__ import annotations

DEFAULT_CALIBRATION_2026_05_17 = {
    "substrate_only": {
        "intercept": -2.198240986904518,
        "coef": {
            "l6_inv": 3.3999678821435695,
            "l4_unsourced": -0.1598380138762396,
            "l4_n_total_norm": 0.5473668848196062,
            "l11_p": 0.9320942026983345,
            "l5_entity_unsourced": 0.1160596999539715,
            "l5_n_entities_norm": 0.47359005929625325,
        },
    },
    "substrate_plus_minicheck": {
        "intercept": -2.6514917303761782,
        "coef": {
            "l6_inv": 2.8794141136132874,
            "l4_unsourced": -0.29794319936985986,
            "l4_n_total_norm": 0.4995453465206627,
            "l11_p": 0.6664123234833331,
            "l5_entity_unsourced": 0.13189450123418212,
            "l5_n_entities_norm": 0.20387721800947559,
            "minicheck_neg": 2.0154702656701513,
        },
    },
    "substrate_plus_minicheck_alignscore": {
        "intercept": -3.061787936315566,
        "coef": {
            "l6_inv": 2.3189740852690286,
            "l4_unsourced": -0.5370860153540684,
            "l4_n_total_norm": 0.6661363467971484,
            "l11_p": 0.6050298817063453,
            "l5_entity_unsourced": 0.12204196606947018,
            "l5_n_entities_norm": 0.07108437003479028,
            "minicheck_neg": 1.6370136236714423,
            "alignscore_neg": 2.5529401397914167,
        },
    },
    "training_corpus": "RAGTruth Summary (test split, 70/30 stratified, seed=0)",
    "n_train": 629,
    "n_test": 271,
}
