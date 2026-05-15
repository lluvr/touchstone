# External validation: SummEval

Second external corpus comparison. Compares Touchstone's signals
against MiniCheck (Tang et al., EMNLP 2024) on the SummEval corpus
(Fabbri et al. TACL 2021), the CNN/DM-derived summary-evaluation
benchmark.

## Why SummEval (after RAGTruth)

The RAGTruth Summary run established that Touchstone's Layer 6
inverse vocabulary proximity is the surviving out-of-domain signal,
with Layer 10's composite gap falsified on short summary outputs.
SummEval adds:

- **Continuous-rating readout**, not just binary. SummEval ships
  per-summary consistency on a 1-5 Likert scale aggregated from
  three annotators, so the readout can be Spearman ρ vs the
  continuous rating in addition to AUC vs a binarized label.
- **A second model-family axis.** SummEval covers 16 different
  summarization systems per article (older neural and extractive
  systems); RAGTruth covers 6 modern instruction-tuned LLMs.
- **A different source domain.** CNN/DM news vs RAGTruth's mixed
  Summary/QA/Data2Txt RAG contexts.

## Corpus

- **Source**: `mteb/summeval` on HuggingFace Hub (MIT). 100 CNN/DM
  articles, each with 16 machine-generated summaries and per-summary
  consistency ratings.
- **Construct**: SummEval's consistency dimension measures factual
  consistency between summary and article ("does the summary state
  anything not entailed by the article?").
- **Total (article, summary) pairs**: 1,600.
- **Label distribution** (binarized at consistency < 4.0):
  - 161 / 1600 (10.1%) "not supported"
  - 1439 / 1600 (89.9%) "supported"
  - Continuous rating: mean 4.66, median 5.0, stdev 0.92
- **No corpus content is included in this repository.** The runner
  streams from HF Hub at runtime.

## Construct caveat: MiniCheck training-test leakage

**MiniCheck (Tang et al. EMNLP 2024) was trained on LLM-AggreFact,
which includes AggreFact-CNN derived from SummEval.** MiniCheck's
fact-checking model has therefore seen the SummEval source
distribution during training, though not necessarily the exact
(article, summary) pairs evaluated here. The absolute MiniCheck AUC
on this corpus is consequently not directly comparable to the
RAGTruth Summary run, where no such training overlap exists.
Touchstone has not been calibrated on any SummEval-derived data;
its AUC on SummEval is a fair test of substrate generalization.

This caveat is recorded explicitly in the runner output JSON and is
the reason this benchmark is presented as a *second* corpus rather
than a *replacement* for the RAGTruth comparison.

## Methodology

For each (article, summary) pair the runner computes:

- **Touchstone**: `clarethium_touchstone.measure(text=summary, source=article)`. Five signals, oriented "higher = more hallucinated":
  - `layer4_unsourced_rate` (gated on ≥1 digit-formatted number).
  - `layer5_entity_unsourced_rate` (gated on ≥5 entities).
  - `layer6_inverse_proximity` = `1 - mean_proximity`.
  - `layer10_gap`.
  - `layer11_p_proportion`.
- **MiniCheck Flan-T5-Large baseline**: `score(docs=[article], claims=[summary])`. AUC is computed on `1 - raw_prob` to match the "higher = not-supported" orientation; Spearman ρ is computed on the raw probability against the continuous consistency rating.

Two readouts:

- **AUC-ROC** on the binarized label (`consistency < 4` = not-supported = positive class).
- **Spearman ρ** between each signal and the continuous consistency rating.

The continuous readout is the primary signal-quality measure on this corpus because the 1-5 scale is heavily skewed toward "supported" (median = 5.0); binarization at any single threshold throws away rank information that Spearman preserves.

## Running

```bash
pip install -e ".[external]"
python -m benchmarks.external.summeval.run --output \
    benchmarks/external/summeval/results/$(date +%F).json
```

On CPU the full 1600-pair run takes ~100 min. MiniCheck weights are
reused from `./ckpts_minicheck/` if the RAGTruth runner ran first.
`--limit N` and `--threshold T` shorten / re-binarize.

## Results

`results/YYYY-MM-DD.json` snapshots are dated. The Touchstone runtime
is on the order of single-digit seconds for the full 1600; MiniCheck
on CPU takes the bulk of the wall-clock budget.

## Cross-corpus comparison with RAGTruth

When both runs have landed, the comparison shape is:

| Signal | RAGTruth Summary AUC | SummEval AUC |
|---|---|---|
| L6 inverse_proximity | 0.6723 | 0.7530 |
| L10 gap | 0.4981 | 0.5000 |
| MiniCheck Flan-T5-Large | 0.7125 | (recorded in results JSON; subject to training-test leakage caveat above) |

The consistency of the Layer 10 gap finding across both corpora
(approximately chance) is the load-bearing observation; it is
recorded as a partial out-of-domain falsification of the Layer 10
construct claim in Standard §3.5.

## Citations

```bibtex
@article{fabbri-etal-2021-summeval,
    title = "{S}umm{E}val: Re-evaluating Summarization Evaluation",
    author = "Fabbri, Alexander R. and Kry{\'s}ci{\'n}ski, Wojciech and McCann, Bryan and Xiong, Caiming and Socher, Richard and Radev, Dragomir",
    journal = "TACL",
    year = "2021",
    url = "https://aclanthology.org/2021.tacl-1.24"
}

@inproceedings{tang-etal-2024-minicheck,
    title = "{M}ini{C}heck: Efficient Fact-Checking of {LLM}s on Grounding Documents",
    author = "Tang, Liyan and Laban, Philippe and Durrett, Greg",
    booktitle = "Proceedings of EMNLP",
    year = "2024",
    url = "https://aclanthology.org/2024.emnlp-main.499"
}
```
