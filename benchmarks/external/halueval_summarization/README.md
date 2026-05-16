# External validation: HaluEval summarization

Third external corpus comparison. Compares Touchstone's signals
against MiniCheck (Tang et al., EMNLP 2024) on the HaluEval
summarization corpus (Li et al., EMNLP 2023).

## Why HaluEval (after RAGTruth + SummEval)

RAGTruth Summary and SummEval established the in-domain pattern:
Touchstone's Layer 6 inverse vocabulary proximity carries the
substrate-generalization signal at AUC 0.67-0.75; Layer 10 gap is
identically near-chance because the substance-side components do
not fire on short summary outputs.

HaluEval adds a third independent corpus with:

- **Paired construction.** Each example pairs a CNN/DM article with
  TWO summaries: a real `right_summary` and a ChatGPT-synthesized
  `hallucinated_summary` on the same article. The natural readout
  is **paired-ranking accuracy** (within each document pair, does
  the signal rank the hallucinated summary higher than the right
  one?). This bypasses any population-level distributional confound
  that absolute AUC would inherit.
- **Perfect 50/50 class balance** when both outputs of every
  document are included.
- **Apache-2.0 license**, no HF access gate.

## Construct caveat: adversarial construction

**HaluEval was built by sampling real CNN/DM summaries and using
ChatGPT to synthesize hallucinated variants.** This is an
adversarially-constructed corpus, not in-the-wild hallucination
data. Touchstone's signal may capture synthetic-vs-real
distributional differences in addition to the construct of interest
(e.g., ChatGPT-synthesized text may use different vocabulary
patterns from real CNN/DM summaries even before hallucinations are
introduced). The paired-ranking accuracy readout (within-document
right vs hallucinated) is the natural metric for this construction
and is the primary reported figure; AUC is reported alongside for
cross-corpus comparison.

## Corpus

- **Source**: `pminervini/HaluEval` on HuggingFace Hub
  (Apache-2.0). Summarization subset, `data` split.
- **Full corpus**: 10000 (article, right_summary,
  hallucinated_summary) triplets sampled from CNN/DM.
- **This run's subset**: 500 documents sampled with seed=0 →
  1000 (article, summary) pairs (500 right + 500 hallucinated).
- **Article context**: median ~3.5 KB, max ~12 KB (full CNN/DM
  articles).
- **Summary outputs**: right_summary median ~285 chars,
  hallucinated_summary median ~427 chars (both multi-sentence).
- **No corpus content is included in this repository.** The runner
  streams from HF Hub at runtime.

## Methodology

For each (article, summary) pair the runner computes:

- **Touchstone**: `clarethium_touchstone.measure(text=summary, source=article)`. Five signals, oriented "higher = more hallucinated":
  - `layer4_unsourced_rate` (gated on ≥1 digit-formatted number).
  - `layer5_entity_unsourced_rate` (gated on ≥5 entities).
  - `layer6_inverse_proximity` = `1 - mean_proximity`.
  - `layer10_gap`.
  - `layer11_p_proportion`.
- **MiniCheck Flan-T5-Large baseline**: `score(docs=[article], claims=[summary])`. AUC computed on `1 - raw_prob`.

Two readouts:

- **AUC-ROC** on the binary label (1 = hallucinated).
- **Paired-ranking accuracy**: for each of the 500 documents, score the right_summary and the hallucinated_summary. The signal is correct on that document if it ranks the hallucinated summary higher (more hallucinated) than the right summary. Ties contribute 0.5. Reported as a single accuracy figure across the 500 document pairs.

## Running

```bash
pip install -e ".[external]"
python -m benchmarks.external.halueval_summarization.run --output \
    benchmarks/external/halueval_summarization/results/$(date +%F).json
```

On CPU the default 500-document / 1000-pair run takes ~100 min.
MiniCheck weights are reused from `./ckpts_minicheck/` if a prior
external runner ran first. `--n-documents N` adjusts the subset
size; `--seed S` changes the sampling seed.

## Results

`results/YYYY-MM-DD.json` snapshots are dated. The Touchstone
runtime is on the order of single-digit seconds for 1000 pairs;
MiniCheck on CPU takes the bulk of the wall-clock budget on this
corpus (CNN/DM articles are larger than RAGTruth contexts).

## Cross-corpus and cross-task comparison

The HaluEval result anchors the Layer 6 generalization finding on a
third corpus and adds a paired-ranking readout that the prior corpora's
construction did not support. With this round, Touchstone has been
evaluated on five (corpus, task) cells: RAGTruth Summary / QA /
Data2Txt, SummEval, and HaluEval summarization. The full cross-corpus
and cross-task tables with 95% bootstrap CIs live in the main README's
§Empirical validation "Headline finding" subsection.

Headline pattern across the five cells:

- Touchstone Layer 6 inverse_proximity: AUC 0.64-0.76, all 95% CIs disjoint from chance.
- Touchstone Layer 10 gap composite: AUC 0.498-0.513, all 95% CIs include 0.5000.
- Touchstone Layer 4 unsourced_rate: AUC 0.7603 [0.6907, 0.8260] on RAGTruth QA (where output number density is high enough to gate it in); near-chance on the other four cells.

## Citations

```bibtex
@inproceedings{li-etal-2023-halueval,
    title = "{H}alu{E}val: A Large-Scale Hallucination Evaluation Benchmark for Large Language Models",
    author = "Li, Junyi and Cheng, Xiaoxue and Zhao, Wayne Xin and Nie, Jian-Yun and Wen, Ji-Rong",
    booktitle = "Proceedings of EMNLP",
    year = "2023",
    url = "https://aclanthology.org/2023.emnlp-main.397"
}

@inproceedings{tang-etal-2024-minicheck,
    title = "{M}ini{C}heck: Efficient Fact-Checking of {LLM}s on Grounding Documents",
    author = "Tang, Liyan and Laban, Philippe and Durrett, Greg",
    booktitle = "Proceedings of EMNLP",
    year = "2024",
    url = "https://aclanthology.org/2024.emnlp-main.499"
}
```
