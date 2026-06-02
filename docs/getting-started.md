# Getting started

This guide covers installation, basic usage, and first measurements with the
`clarethium_touchstone` library.

> **Status:** v0.1 ships Section 5 measurement only. All eleven Section 5
> layers are implemented and tested; two internal regression benchmarks
> (EXP-081 and EXP-095) reproduce exactly from a clone. Section 6
> (Specification Compliance) is reserved for Standard 1.1; the `align()`
> API is not part of v0.1.

## Scope and locale

The reference implementation is calibrated and tested on English-language
Markdown analytical documents (financial summaries, product analyses,
research summaries). Behavior on other languages is undefined: the regex
patterns, stop-word list, syllable counter, and entity heuristics are
English-only and may silently produce uninformative results on non-English
input. Behavior on non-Markdown text (plain prose, JSON, code) is
implementation-defined and not part of v1.0's validated scope.

Empty or near-empty input does not raise: short documents return
all-zero metrics with the corresponding precision indicator set to
`"low"`. Treat `"low"`-precision results as not yet meaningful.

## Installation

```bash
pip install touchstone-mcp
```

This single package bundles the `clarethium_touchstone` reference
library and the MCP server. `from clarethium_touchstone import measure`
works after install. The library is dependency-free; `fastmcp` (used by
the MCP server) is the package's only third-party dependency. Layer 1a (heading defaultness)
accepts a caller-supplied LLM client via a `BaselineGenerator`
callable, so no provider SDK is required to install.

Optional extras:

```bash
pip install "touchstone-mcp[external]"           # external-corpus benchmark runners
```

See [`docs/mcp.md`](mcp.md) for MCP host wiring (Claude Desktop, Claude
Code, Cursor, custom).

For source install or development. On modern Debian/Ubuntu and
Mac-homebrew Pythons, the system Python is externally-managed
(PEP-668); install into a virtual environment:

```bash
git clone https://github.com/lluvr/touchstone.git
cd touchstone
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"                          # package + dev tooling
pytest -q                                        # full test suite (library + MCP server)
```

## First measurement

Profile an AI-generated output against source material:

```python
from clarethium_touchstone import measure

text = "Revenue grew 12% to $143M with 25% margins reported."
source = "Revenue grew 12% to $143M with 25% margins."

result = measure(text, source=source)

# Layer 4: number provenance
result["source_matching"]["unsourced_rate"]   # 0.0 - every number in source

# Layer 11: per-sentence Grounded / Framed / Projected decomposition
result["grounding_decomposition"]["proportions"]   # {"G": 1.0, "F": 0.0, "P": 0.0}
result["grounding_decomposition"]["has_projection"]  # False
```

The composite `quality_profile` (Layer 10) requires at least 10 numbers in
text for `source_fidelity` to qualify. For the
substance vs presentation gap signal, supply a longer document:

```python
text = (
    "Revenue grew 12% to $143M with 25% margins reported. "
    "Costs declined 8% across 5,000 employees over 18 months. "
    "Headcount reached 2,500 with $45,000 average compensation paid. "
    "Customer acquisition cost dropped to $1,200 from baseline. "
    "Retention improved 7.5% to 94.2% across all major segments."
)

result = measure(text, source=text)
result["quality_profile"]["substance_index"]    # 1.0 (self-source)
result["quality_profile"]["gap"]                # -0.54
```

## Layer 1a (heading defaultness)

Layer 1a is the only layer that requires an LLM. The library ships
vendor-neutral via a callable injection, so you supply your own client:

```python
def baseline_generator(prompt: str) -> str | None:
    # Your LLM call. Return generated text or None on failure.
    return your_llm_client.generate(prompt, temperature=1.0)

result = measure(
    text,
    source=source,
    topic="quarterly earnings analysis",
    baseline_generator=baseline_generator,
)
result["structural_profile"]["heading_defaultness"]
# {"jaccard_overlap": 0.33, "is_default": False, "n_baseline_documents": 3}
```

When `topic` or `baseline_generator` is missing, `heading_defaultness` is
`None` and the rest of `structural_profile` (mechanism ratio, assertion
ratio) runs normally on text alone.

### Baseline-generator quality guidance

Layer 1a's output depends on the baseline generator's quirks. To get
reproducible results across runs, fix these dimensions:

- **Model class and version.** Different models produce different
  default headings on the same topic. Document the model and version
  you used; treat a change in either as a calibration change.
- **Temperature.** The default prompt asks for a 600-800 word analysis;
  results are intended for sampling at temperature ≥ 1.0 so that
  multiple calls surface a representative spread of defaults rather
  than a single deterministic skeleton. Temperature 0 collapses the
  baseline to one document and inflates the overlap signal.
- **n_baselines.** The default of 3 samples is a minimum for stable
  word-union estimation. Higher (5-10) gives a more stable baseline
  word set at the cost of more LLM calls.
- **Topic specificity.** Generic topics ("strategy") produce generic
  defaults; specific topics ("Q1 FY2026 earnings analysis for a
  consumer-goods company") produce more on-target defaults and a
  more discriminating overlap signal.
- **Recoverable failures.** The library tolerates raised exceptions
  and non-string returns from the generator (each is counted as a
  failed call). If every call across `n_baselines` fails,
  `heading_defaultness` is None; the layer does not crash the rest
  of `measure()`.

The Standard's §3.1 model-independence claim applies to the scoring
substrate (which does not invoke an LLM on the output being measured).
Layer 1a is the optional exception: it calls an LLM for baseline
generation only, not for output scoring.

## Layer 11 external entities

Layer 11's secondary P-signal matches sentences against a regex list of
external entities (drug names, products, indices) that are unlikely to
appear in a faithful analytical document on the source. The shipped
default list is empirically seeded from the three EXP-095 source
domains (Apple Q1 earnings, BLS labor, OASIS-4 / Wegovy clinical trial)
and is biased toward pharmaceuticals, tech products, and US labor
terms. On other domains the default list is largely silent.

Adopters extending to new domains supply their own list. Replace the
default entirely, or extend it via Python's iterable-unpacking syntax:

```python
from clarethium_touchstone import EXTERNAL_ENTITIES_DEFAULT, measure

# Replace entirely for a new domain
result = measure(
    text,
    source=source,
    external_entities=[
        r"\bcompetitor-product-name\b",
        r"\bdomain-specific-index\b",
    ],
)

# Extend the default with additional patterns
result = measure(
    text,
    source=source,
    external_entities=[*EXTERNAL_ENTITIES_DEFAULT, r"\bextra-pattern\b"],
)
```

Each pattern is case-insensitive Python regex. The Standard's §5.11
notes that on new domains adopters MUST document the entity set they
use; the public `EXTERNAL_ENTITIES_DEFAULT` constant is provided so
this is mechanical rather than requiring private-name access.

## Layer 11 scope assessment

Layer 11's derivation checker saturates as the source's unique-number count
grows. The `scope_assessment` field tells consumers which signal to trust:

```python
from clarethium_touchstone import assess_derivation_regime

assessment = assess_derivation_regime(source_num_count=14)
assessment["derivation_regime"]                      # "saturated"
assessment["cross_reference_layer_4_for_numbers"]    # True
assessment["note_user_facing"]                       # UX-safe explanation
```

Boundaries are validated against the EXP-095 Monte Carlo data:

| Source unique numbers | Regime | Primary P-signal |
|---|---|---|
| < 5 | diagnostic | Reliable |
| 5-9 | transition | Cross-reference Layer 4 |
| ≥ 10 | saturated | Trust Layer 4 for numerical fabrication |

The same dict is returned as `result["grounding_decomposition"]["scope_assessment"]`
on every Layer 11 call, so consumers don't need to compute it separately
unless they want a pre-measurement hint.

## Individual layer functions

When you only need one specific measurement:

```python
from clarethium_touchstone.measure import (
    source_matching,
    grounding_decomposition,
    structural_profile,
)

# Single layer use
sourcing = source_matching(text, source)
gfp = grounding_decomposition(text, source)
profile = structural_profile(text)
```

All eleven layer functions are accessible via `clarethium_touchstone.measure`.
See the [Touchstone Standard 1.0](../STANDARDS/touchstone-1.0.md) for the
specification of each layer.

## What measurements mean

Touchstone measures structural relationships, not subjective quality. For each layer, the table below states the construct, what a high value indicates, and what it explicitly does not assert.

| Layer | Construct | What "high" means | What it does not assert |
|-------|-----------|-------------------|-------------------------|
| 1a heading defaultness | Fraction of document headings matching LLM-generated baselines on the same topic | Document follows a default skeleton structure | Whether the headings are good or bad; whether the content is original |
| 1b mechanism ratio | Causal-language markers vs filler/buzzword markers | Reasoning-style prose dominates over buzzword-style | Whether the causal claims are correct |
| 1c assertion ratio | Fraction of epistemic-register markers in the ASSERTION category | High-confidence rhetorical stance | Whether the assertions are warranted |
| 2 claim density | Numerical and causal claims per 1,000 words | Information-dense prose | Whether the claims are correct |
| 3 temporal instability | Fraction of digit-formatted numbers unstable across regenerations of the same task | Numbers shift between regenerations (an upper bound on fabrication) | Direct fabrication detection (instability ≠ fabrication; stable fabrication is undetected) |
| 4 source matching (`unsourced_rate`) | Fraction of digit-formatted numbers in output not found in source via exact string search | Many numbers are not in the source | Whether the source is correct; whether unsourced numbers are wrong (could be derived) |
| 5 entity provenance | Fraction of named entities in output not found in source | External names introduced | Whether the entity references are appropriate |
| 6 vocabulary proximity | Per-sentence content-word overlap with source | Output paraphrases the source closely | Whether close paraphrase is desirable (could indicate either summary or copy) |
| 7 presentation features | Type-token ratio, FK grade, formatting density, assertiveness, named-concept count | Descriptive features of surface form | Anything evaluative; these are inputs to Layer 10's composite |
| 8 epistemic calibration | Fraction of assertion-bearing sentences with at least one grounding signal | Assertions tend to be grounded | Whether the groundings are real evidence (could be coincidental overlap) |
| 9 information novelty | Per-sentence lexical novelty (content words not seen earlier) | Vocabulary keeps expanding (less repetition) | Semantic information content (length-confounded by Heaps' law) |
| 10 quality profile (`gap`) | `presentation_index - substance_index` | Polished surface exceeds verifiable substance (overclaiming risk) | Whether the document is well-written or correct |
| 11 G/F/P decomposition (`P` proportion) | Fraction of sentences classified as Projected (external data, predictions, unsourced specifics) | Many sentences introduce material not in source | Whether the projected content is true or false |

Touchstone's pattern set is public regex, structural analysis, and string search. An actor aware of the patterns can construct outputs that evade the detector. The Standard explicitly excludes adversarial-intent detection (§1.3). Treat library output as one input to a quality decision, not the only input, especially in high-stakes settings.

The README §Limitations section names what this release does not yet demonstrate (external corpus validation, head-to-head baselines, small-N statistical caveats, Layer 11 domain bias). Standard §3.5 names the falsifiable claims and the evidence that would invalidate each.

## Threshold guidance

Default thresholds are calibrated against research-validated reference
distributions. See Standard Section 7 for specific values and the
`benchmarks/` directory for empirical validation evidence.

The most common interpretive defaults:

- `unsourced_rate > 0.30` indicates fabrication zone (source-absent or
  fabricated numbers)
- `unsourced_rate < 0.17` indicates grounded zone (source-present and
  well-cited)
- `quality_profile.gap > 0.0` indicates overclaiming risk (presentation
  exceeds substance)
- `scope_assessment.derivation_regime == "saturated"` indicates Layer 11's
  primary number-based P signal is unreliable on this source - trust Layer 4
  instead

Adjust thresholds for your domain with documented justification per
Section 7 of the Standard.

## Empirical validation

Two internal regression benchmarks plus three external corpus
comparisons plus one cross-task generalization analysis ship in
`benchmarks/`. The internal benchmarks reproduce the recorded numbers
exactly from a clone:

```bash
python -m benchmarks.exp_081_discrimination.run
python -m benchmarks.exp_095_grounding.run
```

EXP-081 records Cohen's d = -5.238 on a 12-document single-vendor
corpus against the recorded `detector_v031` baseline of d = -5.43.
EXP-095 records P-existence direction agreement (P>0 vs P=0) of
100% on 13 hand-classified outputs across three model families;
aggregate G/F/P MAE is 0.02-0.04 vs `detector_v031` and 0.12-0.13
vs full manual classification (n=7).

The external runners stream third-party corpora from the
HuggingFace Hub at runtime:

```bash
pip install -e ".[external]"
python -m benchmarks.external.ragtruth_summary.run --output \
    benchmarks/external/ragtruth_summary/results/$(date +%F).json
python -m benchmarks.external.summeval.run --output \
    benchmarks/external/summeval/results/$(date +%F).json
python -m benchmarks.external.halueval_summarization.run --output \
    benchmarks/external/halueval_summarization/results/$(date +%F).json
```

The cross-corpus and cross-task Touchstone signal pattern (Layer 6
generalizes; Layer 10 gap composite degenerates out-of-domain) is
documented in the main README §Empirical validation with 95% bootstrap
CIs. The external corpora are not in this repository; the runners
download them at runtime.

## Next steps

- Read the [Touchstone Standard 1.0](../STANDARDS/touchstone-1.0.md) for
  complete specifications
- Read [CONTRIBUTING.md](../.github/CONTRIBUTING.md) for how the project is maintained
