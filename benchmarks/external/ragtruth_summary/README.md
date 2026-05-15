# External validation: RAGTruth Summary

First external corpus comparison for Touchstone. Compares Touchstone's
signals against MiniCheck (Tang et al., EMNLP 2024) on the RAGTruth
Summary test split (Wu et al., ACL 2024). Per the Standard's §3.5
falsifiable construct claim, this run speaks to whether the Touchstone
substrate generalizes beyond the project-authored internal corpora.

## Why RAGTruth

This corpus was chosen against three alternatives after a verified
comparison of license, schema, and construct match. Detail:

| Candidate | License | Output shape | Outcome |
|-----------|---------|--------------|---------|
| HaluBench (Patronus) | CC-BY-NC-2.0 | passage / question / answer / label | Rejected: non-commercial license is incompatible with the project's Apache-2.0 / CC-BY-4.0 surface |
| LLM-AggreFact (Tang 2024) | CC-BY-ND-4.0 + HF access gate | atomic claim (1-2 sentences) | Rejected: the corpus's atomic-claim decomposition leaves outputs too short for Touchstone's per-sentence layers (L11) and substance-side composite (L10) to fire meaningfully |
| TRUE (Honovich 2022) | Apache-2.0 | mixed; requires constituent fetch | Held in reserve as a second-corpus check once RAGTruth lands |
| **RAGTruth-processed** (wandb mirror) | **MIT** | **multi-sentence summaries (median 626 chars) against ~2500-char source contexts; per-output binary hallucination label** | **Picked.** Matches Touchstone's design domain (multi-sentence analytical text over a longer source). |

## Corpus

- **Source**: `wandb/RAGTruth-processed` on HuggingFace Hub. Mirror of
  the Salesforce RAGTruth dataset (Wu, Y. et al., "RAGTruth: A
  Hallucination Corpus for Developing Trustworthy Retrieval-Augmented
  Language Models", ACL 2024) released under MIT.
- **Split used**: `test`, filtered to `task_type == 'Summary'`. n = 900.
- **Models in the corpus** (150 each): gpt-3.5-turbo-0613, gpt-4-0613,
  llama-2-7b-chat, llama-2-13b-chat, llama-2-70b-chat, mistral-7B-instruct.
- **Label balance**: 204/900 (22.7%) examples annotated as containing
  at least one hallucination span. Per-model hallucination rate is
  highly uneven: gpt-3.5/gpt-4 ~3-4%; llama-2 16-34%; mistral-7B 57%.
- **No corpus content is included in this repository.** The runner
  streams the dataset from HF at runtime.

## Methodology

For each example the runner computes:

- **Touchstone**: `clarethium_touchstone.measure(text=row.output, source=row.context)`. Five signals are extracted, each oriented so that **higher = more likely hallucinated**:
  - `layer4_unsourced_rate`: source_matching unsourced rate (skipped when the output has zero digit-formatted numbers).
  - `layer5_entity_unsourced_rate`: entity provenance rate (gated on `n_entities >= 5` per the Layer 5 precision threshold).
  - `layer6_inverse_proximity`: `1 - mean_proximity`.
  - `layer10_gap`: `quality_profile.gap` (positive gap = presentation exceeds substance).
  - `layer11_p_proportion`: `grounding_decomposition.proportions.P`.
- **MiniCheck baseline**: `MiniCheck(model_name='flan-t5-large').score(docs=[context], claims=[output])`. The runner uses `1 - raw_prob` so the direction matches Touchstone (higher = less supported).

Aggregate metric: **AUC-ROC** computed via Mann-Whitney U. AUC-ROC is
prevalence-invariant, which matters here because the corpus is 22.7%
hallucinated overall but ranges 3-57% by model.

Also reported: balanced accuracy at MiniCheck's native binary threshold
(used because MiniCheck ships a calibrated decision rule; Touchstone's
signals do not have a natural binary cutoff for this task).

## Interpretation bands

| AUC range | Reading | Standard §3.5 status |
|-----------|---------|----------------------|
| ≥ 0.75 | Substantive generalization | §3.1 substrate claim strengthened on this corpus; §Limitations shrinks |
| 0.65 - 0.75 | Partial generalization | Calibrated claim about scope; signal exists, ceiling acknowledged |
| 0.55 - 0.65 | Weak signal above chance | Substrate has SOME generalization but is dominated by MiniCheck-class baselines |
| < 0.55 | Construct is domain-specific | §3.1 holds only within the validated internal-corpus domain; honest scope statement required |

The expected outcome on this corpus: **MiniCheck dominates Touchstone
on AUC.** MiniCheck is a fine-tuned discriminator on LLM-AggreFact (a
superset of RAGTruth claim-level data); Touchstone is a regex /
arithmetic substrate. The headline is not "Touchstone matches MiniCheck";
it is **how much signal a substrate without an LLM call retains against
a tuned LLM-based fact-checker**, and which Touchstone layers carry that
signal on a corpus the substrate was not calibrated on.

## Running

The corpus and the MiniCheck model weights are external dependencies;
install via the `external` extra:

```bash
pip install -e ".[external]"
python -m benchmarks.external.ragtruth_summary.run --output \
    benchmarks/external/ragtruth_summary/results/$(date +%F).json
```

On the first invocation MiniCheck downloads ~3 GB to `./ckpts_minicheck/`
(gitignored). The runner is **CPU-only by default** (`CUDA_VISIBLE_DEVICES=-1`)
for cross-machine determinism; comment out that line at the top of
`run.py` to use CUDA if available. Expected CPU runtime on a workstation
class machine: ~100-110 minutes for the full Summary test split.

For smoke testing, `--limit N` caps the example count.

## Construct caveats

- **Touchstone was not calibrated on RAGTruth.** Threshold defaults in
  Standard §7 were validated on the internal EXP-081 / EXP-095 corpora.
  Layer 10's substance side requires precision-adequate Layer 4 / 5 / 8
  inputs; on the short Summary outputs in RAGTruth, several substance
  components do not fire (`components_available` often contains only
  presentation-side signals). This degrades `gap` as a predictor.
- **RAGTruth's hallucinations include classes Touchstone is not designed
  for.** RAGTruth annotates "evident_conflict" and "baseless_info" spans;
  the former includes entity / event swaps that Touchstone's structural
  signal does not directly target.
- **Single annotator origin.** RAGTruth's labels are from the original
  paper; this run does not re-annotate. Construct validity of the labels
  themselves is the original authors' claim, not ours.

## Results

`results/YYYY-MM-DD.json` snapshots are dated and committed alongside
substantive runs. The README is updated when a snapshot lands with the
headline AUCs and any change in interpretation bands.

## Citations

```bibtex
@inproceedings{wu-etal-2024-ragtruth,
    title = "{RAGT}ruth: A Hallucination Corpus for Developing Trustworthy Retrieval-Augmented Language Models",
    author = "Wu, Yuanhao and Hu, Juno and Wang, Yujia and Gao, Yifei and Schwartz, Roy and others",
    booktitle = "Proceedings of the 62nd Annual Meeting of the ACL",
    year = "2024",
    url = "https://aclanthology.org/2024.acl-long.585"
}

@inproceedings{tang-etal-2024-minicheck,
    title = "{M}ini{C}heck: Efficient Fact-Checking of {LLM}s on Grounding Documents",
    author = "Tang, Liyan and Laban, Philippe and Durrett, Greg",
    booktitle = "Proceedings of EMNLP",
    year = "2024",
    url = "https://aclanthology.org/2024.emnlp-main.499"
}
```
