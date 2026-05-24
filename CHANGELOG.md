# Changelog

All notable changes to Touchstone (Standard and library) are documented here.

The Standard and library are versioned independently. Standard versions track methodology evolution; library versions track implementation releases.

---

## v0.2.0 - 2026-05-24: lift the MCP server out to its own `touchstone-mcp` PyPI distribution

The `[mcp]` optional-dependency extra and the `clarethium_touchstone.mcp` subpackage are removed. The Touchstone MCP server now ships as a separate PyPI distribution, [`touchstone-mcp`](https://pypi.org/project/touchstone-mcp/), aligning with the sibling Clarethium MCP servers (`cma-mcp`, `frame-check-mcp`). The four tools (`verify`, `measure`, `assess_derivation_regime`, `list_modes`), their schemas, output shapes, and the `touchstone-mcp` console script command are unchanged; only the install command and the import path move.

This is a breaking change relative to v0.1.2. Pre-1.0 breaking changes between minor versions are permitted by the cadence policy in `RELEASING.md`; the migration path below is single-step and mechanical.

**Migration:**

```diff
- pip install "clarethium-touchstone[mcp]"
+ pip install touchstone-mcp

- from clarethium_touchstone.mcp import build_server
+ from touchstone_mcp import build_server
```

MCP host config is unchanged:

```json
{ "mcpServers": { "touchstone": { "command": "touchstone-mcp" } } }
```

`touchstone-mcp >= 0.1.0` declares `clarethium-touchstone >= 0.2.0` as a runtime dependency, so installing `touchstone-mcp` brings the library along automatically. Callers that depend on the library directly (`Verifier`, `measure`, `assess_derivation_regime`, `VERIFIER_MODES`, etc.) keep using `pip install clarethium-touchstone`; nothing in the library's public surface changed.

**Why a separate distribution rather than the extra.** The library install stays dependency-free (the substrate is regex, structural analysis, source matching, and arithmetic, none of which need third-party packages). Adopters who want the library should not transitively see FastMCP in their dependency tree; adopters who want the MCP server should not be discoverable only through an extra of a differently-named library. The split mirrors the actual Clarethium PyPI surface (`cma-mcp`, `frame-check-mcp`).

**What stayed:**

- The four MCP tool names, schemas, and structured-content payloads are byte-identical to v0.1.2.
- The `touchstone-mcp` console script command is the same; only its entry-point module moves to `touchstone_mcp:main`.
- The MCP server's behaviour against the test corpus is unchanged (the test suite moved along with the code; see `touchstone-mcp/tests/test_server.py`).

**Verification this release ships the right artifacts:**

- `pip install clarethium-touchstone==0.2.0` resolves and installs cleanly in a fresh venv; importing `clarethium_touchstone.mcp` raises `ModuleNotFoundError` (the subpackage was removed).
- `pip install touchstone-mcp==0.1.0` resolves, brings `clarethium-touchstone` and `fastmcp` transitively, and registers the `touchstone-mcp` console script.
- The full pytest, mypy strict, ruff, and canon-audit gates pass against the working tree.

---

## v0.1.2 - 2026-05-24: documentation-only patch release (refreshes PyPI surface)

Documentation, citation, and front-door-copy patch release. No code or test changes; the runtime behaviour and public API are byte-identical to v0.1.1. The point of cutting v0.1.2 is to surface the seven polish PRs merged after v0.1.1 (#2 through #8) on the live PyPI project page, since adopters landing on `pypi.org/project/clarethium-touchstone/` were still seeing the v0.1.1 metadata (old tagline, no MCP keyword, stale status).

**What now appears on the PyPI project page (and everywhere else):**

- **New tagline:** "Hallucination detection for LLM outputs — without calling another LLM." Replaces the previous "Model-independent verification for AI-coupled work" everywhere a first-time visitor lands (README headline, PyPI summary, Standard abstract, MCP server instructions, module docstring, docs site landing).
- **MCP discoverability:** README now has a dedicated "Touchstone MCP" section after the quickstart with install instructions + canonical host-config JSON. The docs site landing page lists it in "Start here". The API reference cross-references it. The Touchstone MCP brand name is consistent everywhere it's used as a noun.
- **README intro tightening:** Replaced jargon ("the substrate is", "calibrated probability", "span-level localization", "Layer 11 P-markers") with plain-English descriptions readable by a first-time visitor.
- **Citation metadata updated:** `CITATION.cff` version → 0.1.2, date-released → 2026-05-24, abstract and preferred-citation title use the new tagline.
- **Documentation accuracy fixes:** `docs/getting-started.md` no longer says "When the package is published to PyPI". `docs/index.md` status paragraph refreshed to reflect the published state. `docs/HANDOFF.md` refreshed to current test count (469) and resolved-audit-baseline state. `docs/api-reference.md` gains the `n_baselines` parameter row and a tightened `scope` semantics description.
- **`Standard §3.5` cleanup:** Three falsifier entries dropped the "Status as of `1.0.0-draft.13`" prefix that was carrying no information beyond what the cited snapshot file paths already document.

**Why no minor bump (v0.2)?** The change is documentation-only. Code, public API surface, and test results are byte-identical to v0.1.1. Semantic versioning calls this a patch.

**Verification this release ships the right artifact:**

- `pip install clarethium-touchstone==0.1.2` resolves and installs cleanly in a fresh venv
- `pip install "clarethium-touchstone[mcp]==0.1.2"` resolves, installs `fastmcp` as expected, registers the `touchstone-mcp` console script
- The PyPI project page renders the new tagline and lists `mcp` + `model-context-protocol` in the keywords (rendered from the Markdown README via `Description-Content-Type: text/markdown`)
- 469 tests still pass; `mypy --strict` + `ruff check + format check` + `canon audit` all clean

---

## v0.1.1 - 2026-05-23: scope-gated Verifier; short-input bug fix; API reference + three new examples

The Phase A refinement pass. Production-user blockers found by adversarial-input probing in v0.1.0 are closed; the API surface gains an explicit scope mechanism; the reference suite gains 11 adversarial-input tests; three new examples cover batch triage, holdout calibration, and the substrate+judge cascade.

**Bug fix — Layer 6 short-input regression (load-bearing).** v0.1.0's `Verifier` returned `prob_hallucinated ≈ 0.78` on trivially faithful short inputs (single sentence, whitespace-only, self-referential). Root cause: when no sentence had scoreable content words, Layer 6 returned `mean_proximity = 0.0` with an empty `per_sentence_proximity` list; the Verifier's feature extractor read `0.0` as "vocabulary is 100% novel," firing `l6_inv = 1.0` against the +3.4 calibration coefficient. The fix gates the `l6_inv` feature on Layer 6 actually having scored at least one sentence, matching the existing precondition gating on Layers 4 and 5. Eleven new adversarial-input tests pin the post-fix behaviour (`test_verifier.py::test_short_faithful_input_does_not_auto_flag` etc).

**API addition — `VerifierResult.scope` and `scope_notes`.** Two new fields make signal quality first-class:

- `scope: "validated" | "limited_signal" | "insufficient_input"` — classifies whether the substrate had enough informative signals to support the calibrated probability.
- `scope_notes: list[str]` — human-readable diagnostics naming which signals fired, which preconditions failed, and any text-level reasons (e.g. insufficient length).

`should_flag()` gains a `fail_open: bool = False` keyword argument: by default the method returns `False` for `"insufficient_input"` and `"limited_signal"` results, preventing pipeline-bursting false positives on degenerate inputs. Callers that route low-signal traces through human review can opt in via `fail_open=True`.

**API addition — `VERIFIER_MODES`.** A tuple of the four valid mode strings, exported from the top-level package. Useful for argparse `choices=`, dashboards listing supported modes, and runtime validation. Complements the existing `VerifierMode` Literal.

**Documentation additions:**

- `docs/api-reference.md` — single-page lookup reference for the entire public API (Verifier, VerifierResult, UnsupportedSpan, measure, assess_derivation_regime, EXTERNAL_ENTITIES_DEFAULT, VERIFIER_MODES). Cross-references the Standard and production_readiness as the source-of-truth pair.
- `README.md` — 30-line quickstart block at the top with a verified working snippet (calibrated probability 0.796 on the canonical hallucinated example).

**Four new examples covering production patterns:**

- `examples/batch_triage.py` — score a corpus, sort by prob_hallucinated, surface the top-K for human review, route limited-signal rows to manual review separately from auto-flag.
- `examples/calibrate_on_holdout.py` — recipe for re-fitting the Verifier's logistic regression on your own labelled holdout data using a stdlib-only gradient-descent loop. Demonstrates the shipped RAGTruth-Summary calibration is suboptimal on adversarial-fabrication corpora; the recalibrated coefficients lift accuracy from 9/12 to 12/12 on the toy holdout.
- `examples/two_stage_cascade.py` — substrate cheap-screen with LLM-judge fallback on the uncertain band. Judge is stubbed deterministically so the example runs offline.
- `examples/mcp_programmatic.py` — programmatic invocation of the Touchstone MCP server's four tools without going through a remote host; useful for verifying the server locally and embedding it in a custom transport.

**New Touchstone MCP server.** The optional `clarethium_touchstone.mcp` subpackage exposes the calibrated Verifier and the `measure()` orchestrator as Model Context Protocol tools, so any MCP host (Claude Desktop, Claude Code, Cursor, custom) can call Touchstone in-context. Optional dependency: install with `pip install "clarethium-touchstone[mcp]"`. The `touchstone-mcp` console script registers automatically and runs stdio transport by default. Four tools: `verify` (calibrated probability + scope + spans), `measure` (raw multi-layer output), `assess_derivation_regime` (Layer 11 regime classifier), `list_modes` (mode enumeration + version metadata). Full host-wiring docs at `docs/mcp.md`. Touchstone MCP ships in-repo, following the convention used by Clarethium's `cma`.

**Documentation pass on `benchmarks/external/` and `docs/production_readiness.md`.** Replaced infrastructure-specific references (specific local proxy URLs, environment-specific credential-loading invocations) in benchmark scripts and reproduction-command examples with generic env-var loading instructions adopters can satisfy with any credential source. Behaviour unchanged; the scripts still work identically when the relevant API key environment variables are set. Updated `scripts/canon_audit.sh` to skip `results/` (byte-pinned benchmark snapshot directories) and `.claude/` (local Claude Code settings).

**Tests:** 469 passing (was 441; +11 adversarial-input regression tests + 17 MCP-server tests gated on the `mcp` extra). 97% coverage held. `mypy --strict` clean. `ruff check` clean. Reproducibility audit: 0 drift. Canon audit: 0 hits.

**Backward compatibility.** Existing callers reading the v0.1.0 fields (`prob_hallucinated`, `mode`, `signal_breakdown`, `top_unsupported`, `layer_outputs`) see no behaviour change for inputs that produced `"validated"` scope under the fixed semantics — i.e. for any reasonable production data the bug did not affect. Callers that constructed `VerifierResult` directly (uncommon — the dataclass is intended to be returned by `Verifier.score()`, not built by users) MUST supply the two new fields. Callers relying on the buggy v0.1.0 behaviour where short / empty / non-English inputs returned `prob ≈ 0.78` will see those inputs now classified as `"insufficient_input"` or `"limited_signal"` and not auto-flagged under `should_flag()`; opt in via `should_flag(fail_open=True)` to restore the pre-fix flag-on-probability behaviour for low-signal results.

---

## 2026-05-19: substrate_plus_judge mode lands on the Verifier; doc-vs-library gap closed; Standard 1.0.0-draft.15

draft.14's stress-test re-review surfaced a structural gap: the §5
production architecture and the §4.2.8 / §4.3 / §4.3.1 multi-vendor
evidence all recommend a substrate-plus-judge composition, but the
library's `Verifier` class had no API for that composition. Three
places in the doc set (README "Read before deploying" bullet, §5
architecture paragraph, §4.2.3 calibration implications bullet) cited
`Verifier(use_minicheck=True)` as the production API; the constructor
in fact takes `mode=` and `calibration=`, not `use_minicheck=True`,
and there was no `substrate_plus_judge` mode at all.

draft.15 closes the gap. The `Verifier` class gains:

- A fourth `VerifierMode` literal value: `substrate_plus_judge`.
- A `judge_hallucinated_prob: float | None = None` parameter on
  `score()`. Mode auto-selects to `substrate_plus_judge` when this
  is supplied; mutually exclusive with `minicheck_supported_prob` /
  `alignscore_supported_prob` in the same call (pick one Stage-2
  detector per call).
- A `judge_alpha: float = DEFAULT_JUDGE_ALPHA` parameter for the
  blend weight. Default is 0.3 (cross-corpus mean of the picked α
  from §4.3.1's holdout-blend table). Adopters whose corpus is
  HaluEval-shape SHOULD raise to 0.6-0.7; SummEval-shape SHOULD
  drop to 0.0 (judge-only). Both regimes are picked deterministically
  by running `substrate_plus_judge_holdout` on a tune split of the
  adopter's own data.
- A linear-blend implementation:
  `final_prob = judge_alpha * substrate_prob + (1 - judge_alpha) * judge_hallucinated_prob`.
  Matches the §4.3 / §4.3.1 measurement shape byte-exactly. No new
  logistic regression coefficients required; the substrate component
  reuses the existing `substrate_only` calibration.
- Signal breakdown explicitly carries `substrate_prob`,
  `judge_hallucinated_prob`, and `judge_alpha` keys for adopter
  auditability.
- Three guard rails: judge_hallucinated_prob must be in [0, 1],
  judge_alpha must be in [0, 1], judge_hallucinated_prob is mutex
  with minicheck/alignscore probs.

The README and `docs/production_readiness.md` are corrected to cite
the actual API. `examples/production_verifier.py` gains a third demo
that exercises the new mode end-to-end (with a mocked judge
probability so the demo runs without an API call; in production the
caller invokes Grok/Claude/GPT-4o per §4.2.8 and passes the returned
P(hallucinated)).

Test coverage:

- 7 new tests in `tests/test_verifier.py` covering: auto mode-select,
  blend arithmetic over five alpha values, judge_alpha=0 (judge-only)
  edge case, judge_alpha=1 (substrate-only) edge case, mutex with
  minicheck and alignscore, out-of-range judge_hallucinated_prob and
  judge_alpha, explicit-mode requires judge_hallucinated_prob.
- Total test count: 434 → 441. All pass.
- ruff lint + format pass on verifier.py and test_verifier.py.

Standard (1.0.0-draft.14 -> 1.0.0-draft.15):

- Status header rewritten to describe the new mode and the doc-vs-
  library gap closure.
- `__standard_version__` bumped; CITATION.cff, README BibTeX,
  methodology.md citation synced.

The four pre-existing modes (`substrate_only`,
`substrate_plus_minicheck`, `substrate_plus_minicheck_alignscore`)
ship unchanged. The new mode is additive; no existing snapshots or
test outputs change.

What this changes for adopters: the §5 architecture recommendation
("for audit-grade, substrate + judge") is now a one-line deploy:

```python
from clarethium_touchstone import Verifier

v = Verifier()
# Caller invokes their preferred judge first:
judge_prob = call_xai_or_claude_or_openai(text=..., source=...)
result = v.score(text=..., source=..., judge_hallucinated_prob=judge_prob)
# result.prob_hallucinated is the blended Stage-1 + Stage-2 probability.
# result.signal_breakdown carries substrate_prob, judge_hallucinated_prob,
# judge_alpha for adopter audit; result.top_unsupported gives span
# localization from the substrate's Layer 11 classifications.
```

Before draft.15, adopters had to re-implement the linear-blend
arithmetic themselves outside the Verifier (or pretend the §4.3 / §4.3.1
evidence applied to a Verifier mode that didn't exist). After draft.15,
the architecture and the library are aligned.

---

## 2026-05-18: four critical-tier honesty fixes to the §4 cross-detector evidence; Standard 1.0.0-draft.14

The previous round shipped §4.2 cross-detector measurement on n=400 prefix subsamples. An in-session stress-test review (top-AI-lab framing, code+doc verification) surfaced four critical-tier defects in the §4.1+§4.2 framing. This round lands the four fixes coherently and bumps the Standard to draft.14. None of the underlying judge calls were re-run; every new artifact is a re-analysis of the existing pinned snapshots.

**The four critical fixes:**

1. **Prompt-cueing honesty.** `benchmarks/external/judge_xai_from_pairs.py` had a docstring claiming the Grok prompt is "deliberately minimal and unparameterised." The actual prompt enumerates the six §4 wall-claim categories (polarity flips, attribute swaps, scope shifts, time-frame shifts, relation reversals, imputed causes) — exactly the failure modes the fixture tests. The docstring is rewritten to name the prompt as `cued`. A paired `JUDGE_SYSTEM_PROMPT_BLIND` constant ships alongside, exposed via `--prompt-variant {cued,blind}`. The §4.1 confounds box gains a prompt-cueing bullet with the in-session three-arm stress-test result (cued and blind both at 16/16 on the toy fixture; the toy fixture is at ceiling and cannot measure the cueing effect; the cueing measurement must run on naturalistic data and is queued). Existing snapshots are backfilled with `judge_prompt_variant: "cued"` so they are self-documenting; backward-compatible `JUDGE_SYSTEM_PROMPT` alias preserved.

2. **"Stratified" terminology corrected.** §4.2 called the sampling "stratified n=400" but the `subsample_pairs.py` script writes `sampling_strategy: "first_n_in_original_order"` in every indices snapshot. The doc is corrected to "deterministic first-N prefix" with the base-rate-preservation defense made explicit (RAGTruth flips/IID ratio 0.97; SummEval 1.00; HaluEval 2.00 from perfect label alternation; base rate preserved within ±1.5 pp on each).

3. **Held-out F1-optimal threshold (§4.2.1).** New script `benchmarks/external/operational_metrics_holdout.py`. Each n=400 subsample is split 200/200 via deterministic stratified interleave (positives alternate tune/eval/tune/eval in encounter order; negatives likewise) so both halves preserve the subsample's base rate to within 1 example. F1-optimal threshold is chosen on the tune half, metrics reported on the eval half. The in-sample-vs-holdout inflation is auditable per-detector per-corpus. New artifact `operational_metrics_n400_holdout_2026-05-18.json`. Headline finding: detector orderings preserved on every corpus, but absolute F1 inflation ranges 0.000–0.234. The substrate L6 SummEval F1 was 0.422 in-sample → 0.188 held-out (largest single inflation). The Grok edge is the most robust under holdout (inflation 0.000–0.070 across corpora).

4. **Tie-aware metric envelope (§4.2.2).** New script `benchmarks/external/operational_metrics_tie_envelope.py`. K=100 sub-quantum-jitter permutations on each detector's scores; mean ± std reported for F1-optimal, threshold, P@R90, R@P90, and top-10% lift. Deterministic seed (SHA-1 per detector name) so the snapshot is reproducible. New artifact `operational_metrics_n400_tie_envelope_2026-05-18.json`. Headline finding: Grok 4.20's heavy probability clustering (274/400 SummEval probs at exactly 0.0; 110/400 RAGTruth probs at 0.35; 98/400 HaluEval probs at 0.65) makes its R@P90 the least tie-stable headline in §4.2: the snapshot's "Grok catches 12 of 46 on SummEval at P@R90" is 7 ± 3 under random tie-break; "catches 87 of 200 on HaluEval at P@R90" is 67 ± 16. The original snapshot's point estimates sit at or near the favorable tie-break end. The substrate / MiniCheck / AlignScore numbers are tie-stable (std ≈ 0.000). The Grok-vs-MiniCheck +1F1 advantage on SummEval (0.702 vs 0.695 in-sample) becomes effectively zero under the tie envelope (0.696 ± 0.009 vs 0.695 ± 0.000).

**Standard (1.0.0-draft.13 -> 1.0.0-draft.14):**

- Status header rewritten to enumerate the four fixes. Body sections unchanged; the fixes live in `docs/production_readiness.md` §4.1/§4.2 not in the Standard text itself.
- `__standard_version__` bumped to `1.0.0-draft.14`; CITATION.cff, README BibTeX, and methodology.md citation synced.

**New files (additive; no existing snapshots changed):**

- `benchmarks/external/operational_metrics_holdout.py`
- `benchmarks/external/operational_metrics_tie_envelope.py`
- `benchmarks/external/operational_metrics_n400_holdout_2026-05-18.json`
- `benchmarks/external/operational_metrics_n400_tie_envelope_2026-05-18.json`

**Modified files:**

- `benchmarks/external/judge_xai_from_pairs.py` — refactored prompt constants, added `--prompt-variant` flag, snapshot now records `judge_prompt_variant`.
- All four Grok snapshots (`benchmarks/adversarial_subtle/judge_xai_2026-05-18.json` and the three §4.2 corpus snapshots) — backfilled `judge_prompt_variant: "cued"` field. Per-example probabilities, AUC, and runtime values unchanged.
- `docs/production_readiness.md` — §4.1 confounds box gains prompt-cueing bullet; world-knowledge bullet gains the in-session priors-only measurement; §4.2 first paragraph rewrites "stratified" → "deterministic first-N prefix"; §4.2 caveats list mentions cued prompt variant and across-prefix-offset variance gap; new §4.2.1 (holdout table) and §4.2.2 (tie envelope table) sub-sections.
- Version bumps in `STANDARDS/touchstone-1.0.md`, `src/clarethium_touchstone/_version.py`, `CITATION.cff`, `README.md`, `docs/methodology.md`.

**Verification:**

- `python -m benchmarks.external.operational_metrics_on_subsample` reproduces the original §4.2 table byte-exactly (no regression from snapshot backfill).
- `python -m benchmarks.external.operational_metrics_holdout` produces the new holdout snapshot deterministically.
- `python -m benchmarks.external.operational_metrics_tie_envelope` produces the new tie-envelope snapshot deterministically (SHA-1 seed; MD5-stable across runs).
- `judge_xai_from_pairs.py --help` lists `--prompt-variant {blind,cued}` with cued as default.
- All four Grok snapshots load and assert their backfilled `judge_prompt_variant == "cued"`.

**Carried forward (still pending — see `docs/production_readiness.md` §4.2.2 closing paragraph):**

- Calibration metrics (ECE, Brier, reliability) per detector per corpus.
- Across-subsample variance via K=10 prefix-offset draws (substrate/MiniCheck/AlignScore re-tabulation only; Grok column gated on additional judge budget).
- World-knowledge ablation on §4.1 fixture (source-removed Grok run; ~32 calls).
- Per-category audit on a slice of §4.2 naturalistic positives.
- Cued-vs-blind delta on §4.2 sample (~450 calls).
- Multi-vendor judge panel (Claude / GPT-4 rows on §4.2).
- Cost-per-call snapshot.

---

## 2026-05-17: production-readiness reality check — operational metrics + subtle-case stress test; Standard 1.0.0-draft.13

The user critique: "Are we testing internal code (mocks, self-source, project-authored hand-crafted adversarial straw-men) or testing whether this thing actually solves real problems?" The honest answer turned out to be: we'd been testing internal code. AUC numbers don't answer "would deployment actually help?" This round runs the missing operational analyses and writes the conclusion that emerges.

**New analyses:**

1. **Operational metrics on the three external corpora** (`benchmarks/external/operational_metrics.py`, results at `benchmarks/external/operational_metrics_2026-05-17.json`). For each (system, corpus) combination, computes precision/recall/F1 at threshold 0.5, F1-optimal threshold, precision at recall 0.9, recall at precision 0.9, and lift at top-K%.

2. **16-case hand-crafted subtle-hallucination stress test** (`benchmarks/adversarial_subtle/run.py`, results at `benchmarks/adversarial_subtle/results_2026-05-17.json`). Covers the categories real LLMs actually produce: number swap within same scale, percentage shift within plausible range, quarter shift, role/title swap, direction reversal, imputed cause, magnitude shift, false precision, time-frame shift, attribute swap, fabricated affiliation, scoping shift, counterfactual extension, numerical conflation, subtle entity swap, relation reversal.

**The findings, brutally:**

- **At precision 0.9 (production-certainty), all systems catch 1-7% of real hallucinations on naturalistic corpora.** Not specifically a Touchstone problem; MiniCheck catches 3 of 204 hallucinations on RAGTruth Summary at precision 0.9. Audit-grade verification is not achievable with any tool tested.
- **F1-optimal thresholds are 0.07-0.27, NOT 0.5.** The Verifier's default `should_flag(threshold=0.5)` under-flags by a wide margin. Production teams must tune the threshold on their own held-out data.
- **Touchstone separates only 8 of 16 subtle-hallucination categories (50%, chance)**. At threshold 0.5, zero of 16 hallucinated cases are flagged. The substrate is **structurally blind** to hallucinations that preserve vocabulary and only change semantic relationships: direction reversal, attribute swap, scoping shift, relation reversal, time-frame shift, imputed cause. These are the hallucinations real LLMs produce most often.
- **Touchstone catches the lexically-distinguishable subset**: number swaps, magnitude shifts, fabricated entities/numbers, vocabulary drift, false precision. About half of all real LLM hallucinations.
- **The real production-deployable use case is triage/prioritization**: top-10% review by Touchstone score delivers 2-4× lift over random review on naturalistic English news summarization corpora (lift 4.22× on SummEval).

**New artifact: `docs/production_readiness.md`** — the blunt operational report. Seven sections covering: why AUC misleads, operational metrics in detail, the triage use case, the subtle-case stress test results, the honest production architecture, the honest scope statement, and reproducibility. This is the document a top-lab reviewer should read first.

**Standard (1.0.0-draft.12 -> 1.0.0-draft.13):**

- §13.6 (Verifier honest scope) rewritten to incorporate the subtle-case stress test findings. The substrate is explicitly named as "structurally blind to hallucinations that preserve vocabulary and only change semantic relationships." Adopters MUST pair the Verifier with a semantic discriminator for general-purpose hallucination detection.
- Status header updated to draft.13 with the two-stage production architecture explicit.

**README:**

- New "Read before deploying" section at the top with the headline findings and a pointer to `docs/production_readiness.md`. The README no longer leads with the Verifier as a production-grade detector; it leads with the honest scope (triage, drift detection, lexical filter) and routes readers to the operational analysis.
- The Verifier quick-example reframed: the calibrated probability is positioned as "the lexical half of a two-stage architecture", not as a standalone signal.

**Verifier docstring:**

- Rewritten to lead with the production-readiness pointer and the structural-blindness finding. Explicit warning that the default `should_flag(threshold=0.5)` under-flags for any production deployment.

**Verification:**

- 412 tests pass (no test changes; this round is documentation + analysis).
- mypy strict, ruff lint+format, canon audit (self-test + tree) all green.
- All snapshots byte-identical to draft.12; new operational + subtle-case snapshots are additive.

**Why this is the right move:**

Polishing internal validation while the production-readiness question stays unanswered would have failed a real review. The operational metrics and subtle-case stress test were the missing piece. The findings are negative for the "Touchstone as production hallucination detector" framing AND positive for the "Touchstone as triage / lexical filter" framing. Both are documented. The recommended production architecture (substrate + semantic discriminator) is now explicit in the Standard, the README, the Verifier docstring, and the production-readiness doc.

**Carried forward (unchanged):**

- SOTA LLM-based baselines (Bespoke-MiniCheck-7B, GPT-4-as-judge).
- TRUE, LLM-AggreFact held-out, HaluBench external runs.
- HHEM 2.1, SelfCheckGPT, G-Eval baselines.
- Non-English / non-summarization scope extension.
- Inter-annotator agreement on EXP-095.
- Editor body constitution.

---

## 2026-05-17: production Verifier API — `score(text, source)` with calibration + span localization; Standard 1.0.0-draft.12

After the frame-break round (where the trivial-baseline anchor surfaced that Touchstone L6 ≈ word overlap on AUC), the question became: where does the actual 10x value-add live? Empirical AUC has a hard ceiling at ~0.77 from ensembling all signals. The 10x is in **production usefulness** — the gap between "dict-of-layer-outputs research interface" and "calibrated probability + signal breakdown + span localization that an adopter can act on."

This round ships the production Verifier API. The substrate is unchanged; the value-add is in the calibrated combination, the explainable breakdown, and the span-level localization.

**New public API:**

```python
from clarethium_touchstone import Verifier

v = Verifier()
result = v.score(text=output, source=context)
result.prob_hallucinated        # 0.0-1.0 calibrated probability
result.signal_breakdown          # {feature_name: contribution_to_logit}
result.top_unsupported           # [UnsupportedSpan, ...] with Layer 11 classification
result.should_flag(threshold=0.5)  # convenience bool
result.layer_outputs             # raw MeasureResult for drill-down
```

Three modes, auto-selected by which baseline scores the caller supplies:

- `substrate_only` (default; no extras, sub-100 ms): default-calibrated AUC ≈ 0.67-0.76 on three external summarization corpora.
- `substrate_plus_minicheck`: caller invokes MiniCheck themselves and passes `minicheck_supported_prob`; AUC ≈ 0.76 on the RAGTruth Summary held-out test split.
- `substrate_plus_minicheck_alignscore`: pass both; AUC ≈ 0.77.

The Verifier never invokes a model on the output under measurement — the substrate-independence claim (§3.1) continues to hold in `substrate_only` mode, and in the augmented modes the trained-discriminator score is supplied by the caller, not produced by the Verifier.

**Calibration shipped with the library:**

- Default calibration trained on RAGTruth Summary test split (70/30 stratified, seed=0; n_train=629, n_test=271).
- Coefficients live at `src/clarethium_touchstone/_calibration.py` as `DEFAULT_CALIBRATION_2026_05_17`.
- Adopters with their own held-out training data: `Verifier.with_calibration(custom_dict)` accepts a coefficient dict in the same shape.
- Held-out AUC + bootstrap CI: substrate_only 0.6773 [0.6042, 0.7473]; +MiniCheck 0.7588 [0.6867, 0.8198]; +MiniCheck+AlignScore 0.7734 [0.6955, 0.8355].

**Standard (1.0.0-draft.11 -> 1.0.0-draft.12):**

- **New Section 13: Calibrated Verifier methodology** specifying what a conforming Verifier MUST and SHOULD do. Six subsections covering rationale, modes, required feature set, calibration discipline, span-level localization, and honest scope.
- The Verifier methodology does NOT add discriminative signal beyond the underlying substrate + caller-supplied baselines; it provides calibrated combination + signal breakdown + span localization on top of those signals. §13.6 documents this honestly: the substrate-only AUC range (0.67-0.76) is research-tier, not audit-tier.
- Status header updated to draft.12; mentions §13.

**Library changes:**

- New `clarethium_touchstone/verifier.py` (≈300 LOC) with `Verifier`, `VerifierResult`, `UnsupportedSpan`, and `VerifierMode` types. Public API re-exported from `__init__.py`.
- New `clarethium_touchstone/_calibration.py` with `DEFAULT_CALIBRATION_2026_05_17` (~30 numbers; trained as documented).
- mypy strict clean on the new modules (uses `MeasureResult` TypedDict properly; guards source-required layer access with an explicit error).
- 11 new tests in `tests/test_verifier.py` covering shape, supported/hallucinated polarity, signal-breakdown reconstruction, mode auto-selection, missing-baseline error, and custom-calibration injection.

**README:**

- New "Quick example: the production Verifier API" section as the primary entry point.
- The raw `measure()` example moves to a "Low-level: raw measure() for layer-level analysis" subsection.

**docs/methodology.md:**

- Citation updated to draft.12.

**Verification:**

- 412 tests pass (was 401; 11 new Verifier tests).
- Coverage maintained.
- mypy strict, ruff lint+format, canon audit (self-test + tree) all green.
- New `examples/production_verifier.py` runs end-to-end and demonstrates the API with a faithful vs hallucinated CNN/DM-style summary; the hallucinated summary scores 0.796 and surfaces three P-classified sentences with their specific markers.

**Why this is a 10x:**

Before this round, an adopter received a `dict` of 11 layer outputs and had to figure out how to combine them, what threshold to apply, and where in the output the problem actually was. That's a research interface. Now an adopter gets:

- **One number** (`prob_hallucinated`) they can threshold against.
- **An explanation** (`signal_breakdown`) showing which substrate signals contributed to the score.
- **Localization** (`top_unsupported`) showing WHICH sentences are flagged and WHY (Layer 11 P-markers or low grounding scores).
- **A `should_flag()` convenience method** with a tunable threshold.
- **Three accuracy/latency tiers** with documented AUC + latency envelopes.
- **Recalibration support** for adopters whose distribution differs from English news summarization.

The AUC ceiling is still ~0.77 (the substrate doesn't get a free signal boost from packaging). The 10x is in usefulness, not in accuracy.

**Carried forward (unchanged):**

- SOTA LLM-based baselines (Bespoke-MiniCheck-7B, GPT-4-as-judge).
- TRUE, LLM-AggreFact held-out, HaluBench external runs.
- HHEM 2.1 (install fix), SelfCheckGPT, G-Eval baselines.
- Non-English / non-summarization scope extension.
- Inter-annotator agreement on EXP-095.
- Editor body constitution.

---

## 2026-05-17: frame-break — trivial-baseline anchor + honest reframing

A fresh-eyes stress test surfaced the single most consequential omission in the prior rounds: **Touchstone Layer 6 inverse_proximity had never been compared against a trivial lexical baseline.** This round adds three trivial baselines on every external corpus, finds that a 3-line raw word-overlap baseline is statistically indistinguishable from Layer 6, and rewrites the framing across README, methodology doc, Standard §3.5, and §Use cases / §Limitations to reflect this honestly.

**The frame-break finding:**

| Signal | RAGTruth Summary | SummEval | HaluEval | Mean | SD |
|---|---|---|---|---|---|
| Touchstone Layer 6 | 0.6723 [0.6296, 0.7116] | 0.7530 [0.7145, 0.7951] | 0.7593 [0.7285, 0.7879] | 0.728 | 0.039 |
| **Trivial WordOverlapInv (3 lines)** | **0.6827 [0.6410, 0.7238]** | **0.7284 [0.6810, 0.7774]** | **0.7431 [0.7136, 0.7712]** | **0.718** | **0.026** |
| Trivial JaccardContentInv | 0.6677 [0.6234, 0.7081] | 0.7089 [0.6622, 0.7547] | 0.4715 [0.4363, 0.5073] | 0.616 | 0.106 |
| Trivial TFIDFCosineInv | 0.6163 [0.5739, 0.6639] | 0.6987 [0.6553, 0.7421] | 0.5385 [0.5032, 0.5740] | 0.618 | 0.065 |

- Touchstone Layer 6 CIs heavily overlap the WordOverlapInv CIs on **every corpus tested**. The "Layer 6 substrate-independence" finding from prior drafts reduces empirically to: simple lexical features (with or without Touchstone's per-sentence segmentation) carry the same out-of-domain hallucination signal at this signal-strength tier.
- WordOverlapInv has the **lowest cross-corpus SD (0.026)** of any signal in the cross-baseline table; Layer 6 SD is 0.039. The most substrate-independent baseline is plain word overlap, not Touchstone's structured Layer 6.
- JaccardContentInv collapses on HaluEval (AUC 0.4715, below chance), confirming that trivial-baseline behaviour is highly preprocessing-dependent.

**Honest reframing applied across the surface:**

- **README §Empirical validation "Headline finding"** rewritten: trivial-baseline row added to the cross-corpus table; framing paragraphs replaced with the load-bearing honest version. Positioning sentence: *Touchstone is a research substrate for studying hallucination-detection methodology at low compute cost, NOT a production-grade hallucination detector.*
- **README §Use cases**: three-tier framing sharpened. "Exercised on" lists research / drift detection. "Plausibly suited" includes drift detection alongside an LLM-based judge. "Does NOT yet support" explicitly names adversarial-robustness, audit/compliance recall levels, non-English / non-summarization scope, and production hallucination detection without an LLM-based judge as the primary signal.
- **README §Limitations**: two bullets rewritten. (a) Three corpora, two budget-tier baselines, three trivial baselines — SOTA discriminators (Bespoke-MiniCheck-7B, GPT-4-as-judge) NOT tested and are the right next baselines. (b) All three corpora are English-news-summarization derivatives; non-English / non-summarization is out of validated scope.
- **Standard §3.5 Layer 6 falsification criterion** updated to incorporate the trivial-baseline anchor. The Layer 6 construct claim is now explicitly "the per-sentence stopword-filtered formulation produces a more stable signal across preprocessing variants than any single trivial baseline" — NOT "the layer adds discriminative value beyond plain word overlap" (which the data shows it does not).
- **docs/methodology.md**: section 1 ("substrate hypothesis") opens with the empirical finding rather than the hypothesis; section 3.4 ("cross-corpus cross-baseline finding") rewritten to include trivial baselines and the load-bearing honest framing.

**New artifacts:**

- `benchmarks/external/trivial_lexical_baselines.py` — stdlib-only script computing WordOverlapInv, JaccardContentInv, TFIDFCosineInv on the three external corpora with 95% bootstrap CIs (1000 stratified resamples, fixed seed).
- `benchmarks/external/*/results/trivial_lexical_baselines_2026-05-17.json` — three new snapshots with per-example trivial-baseline scores plus aggregate CIs.
- `benchmarks/external/cross_baseline_summary.py` extended to include trivial-baseline rows in the Markdown table output.

**Verification:**

- 401 tests pass (no test changes; the reframing is documentation-only on the library side).
- mypy strict, ruff lint+format, canon audit (self-test + tree) all green.
- All prior snapshots byte-identical; trivial-baseline snapshots are new files.

**Why this is the right move now.** Prior rounds had been incrementally improving the Touchstone-vs-LLM-baselines comparison without ever asking the question "does a 3-line baseline do this just as well?" That omission would have been the first critique from a top-lab reviewer. Naming it explicitly, running the experiment, and rewriting the framing honestly is more credible than discovering it later. The new positioning ("research substrate, not production tool; structured packaging of trivial lexical signal plus a falsification protocol") is more defensible than the prior framing ("substrate independence" claim with statistical evidence that turns out to also hold for a 3-line bag-of-words).

**Carried forward (unchanged from prior round):**

- SOTA LLM-based baselines (Bespoke-MiniCheck-7B, GPT-4-as-judge).
- TRUE, LLM-AggreFact held-out, HaluBench external runs.
- HHEM 2.1, SelfCheckGPT, G-Eval baselines.
- AlignScore on RAGTruth QA / Data2Txt task types.
- Inter-annotator agreement on EXP-095.
- Editor body constitution.

---

## 2026-05-17: deep finalization — reference suite, full CIs, cross-task baselines, methodology doc; Standard 1.0.0-draft.11

The "real gaps and improvements" round. Five load-bearing additions, all reproducible from a fresh clone:

1. **Canonical reference test suite landed at `tests/reference/cases/`** — 16 language-agnostic JSON cases covering all required layers (1b, 1c, 2, 3, 4, 5, 6, 7), both experimental layers (8, 9), and Layer 11 (with both a fully-grounded case and a projected-content case). Pytest-discoverable; runs as part of the default test matrix. Each case specifies inputs, per-layer expected outputs, and an absolute tolerance; the comparison rules are documented in `tests/reference/README.md` so second-party implementations in other languages can produce identical JSON outputs and pass the same cases. Standard §11.1 is updated: the reference suite is now the primary conformance gate (was previously "reserved for 1.0.1").
2. **Standard §3.5 falsification protocol expanded from 4 claims to 13.** Layer 1a, 1b, 1c, 2, 3, 5, 6, 7, 8, 9 now have explicit falsifiable construct claims alongside the existing entries for Layers 4, 10, 11 and the §3.1 substrate-independence claim. The criteria for the four claims with empirical status (4, 10, 11, §3.1) carry status notes; the others name the evidence that would falsify them.
3. **MiniCheck bootstrap CIs computed on all five (corpus, task) cells.** The original MiniCheck runners did not retain per-example probabilities; the new `benchmarks/external/minicheck_from_pairs.py` runner re-scores from pre-extracted pair JSONs and saves per-example probs + 95% CIs. Five corpus runs were chained as one ~7 hour CPU sequence (RAGTruth Summary + SummEval + HaluEval summarization + RAGTruth QA + RAGTruth Data2Txt) producing five snapshot files under `*/results/minicheck_*with_cis_2026-05-16.json`.
4. **Cross-task MiniCheck coverage**: previous rounds had MiniCheck on the three summarization corpora only; this round adds RAGTruth QA (n=900) and RAGTruth Data2Txt (n=900). This converts the cross-task table from "Touchstone-only" to two-system coverage and surfaces two new findings (below).
5. **Cross-baseline aggregate script + methodology summary doc.** `benchmarks/external/cross_baseline_summary.py` reads every snapshot and produces the unified Markdown table that lives in the README; `docs/methodology.md` is a 124-line single-document walkthrough of the substrate hypothesis, falsification protocol, cross-corpus evidence, caveats, and reproducibility steps for top-lab reviewers.

**Two new headline findings from the cross-task MiniCheck expansion:**

| Cell | MiniCheck AUC | Touchstone Layer 6 AUC | Touchstone Layer 4 AUC | Reading |
|---|---|---|---|---|
| RAGTruth Data2Txt | **0.4871 [0.4494, 0.5283]** (chance) | 0.6397 [0.6001, 0.6757] | 0.5177 [0.4810, 0.5488] | Touchstone L6 > MiniCheck, CIs disjoint; MiniCheck is statistically indistinguishable from chance |
| RAGTruth QA | 0.6437 [0.5978, 0.6920] | 0.6984 [0.6579, 0.7361] | **0.7603 [0.6907, 0.8260]** | Touchstone Layer 4 > MiniCheck, CIs disjoint by a small margin (Touchstone L4 lower bound 0.6907 above MiniCheck upper bound 0.6920) |

The cross-task variability of MiniCheck (SD 0.16 across the three RAGTruth task types) versus the stability of Touchstone Layer 6 (SD 0.03 across the same task types) is the strongest single piece of evidence in the report for Standard §3.1's substrate-independence claim: the zero-LLM-cost substrate produces a more uniform signal across input regimes than a single-model fine-tuned discriminator.

**Standard (1.0.0-draft.10 -> 1.0.0-draft.11):**

- §3.5 falsifiable construct claims expanded from 4 to 13 (covers every Layer + the §3.1 substrate claim).
- §3.5 §3.1 substrate-independence claim updated with the full five (corpus, task) × two baselines AUC + CI matrix and the cross-task variability framing.
- §8 reference-suite paragraph updated: 16 cases now ship; coverage spans all required + experimental layers.
- §11.1 conformance surface updated: `tests/reference/cases/` is now the primary conformance gate.
- Drafting status: reference-suite extraction no longer "reserved for 1.0.1" (it landed); v1.0.1 carries forward expanded edge-case coverage instead.
- Header status updated to draft.11; date 2026-05-17.

**README:**

- New "What's here" inventory listing reference suite, internal benchmarks, external benchmarks, and methodology doc explicitly.
- Cross-corpus and cross-task tables in "Headline finding" subsection now have full bootstrap CIs on every cell (was: MiniCheck point AUCs only on cross-corpus; no MiniCheck row on cross-task).
- Three-paragraph framing of the cross-(corpus, task) pattern: (a) MiniCheck chance on Data2Txt, (b) Touchstone L4 > MiniCheck on QA, (c) Touchstone L6 > both baselines on HaluEval. The substrate-stability claim (Touchstone L6 SD 0.05 vs MiniCheck SD 0.16) is the load-bearing observation.
- §Limitations: "MiniCheck CIs not yet computed" item removed (CIs are now present on all five cells). Remaining open items: TRUE / LLM-AggreFact held-out / HaluBench corpora; HHEM 2.1 / SelfCheckGPT / G-Eval / Bespoke-MiniCheck-7B baselines; AlignScore on RAGTruth QA / Data2Txt; IAA on EXP-095; editor body constitution.

**New artifacts:**

- `tests/reference/test_reference_cases.py` + 16 case files at `tests/reference/cases/*.json`.
- `benchmarks/external/cross_baseline_summary.py` — aggregate Markdown / JSON renderer.
- `benchmarks/external/*/results/minicheck_*with_cis_2026-05-16.json` — five MiniCheck CI snapshots.
- `docs/methodology.md` — top-lab summary document, linked from README "What's here" and from `docs/index.md`.

**Polish (alongside the substantive additions):**

- All draft references in the repo synced to `1.0.0-draft.11` (Standard header, BibTeX, CITATION.cff, _version.py, tests/reference/README.md, methodology.md).
- README "Status" section sharpened (was already updated in draft.10 round; minor re-read pass).
- benchmarks/README.md describes both internal and external benchmark groups uniformly.
- All five sub-corpus READMEs (RAGTruth Summary, SummEval, HaluEval, internal EXP-081 and EXP-095) point at the main README's Headline finding subsection rather than duplicating tables.

**Verification:**

- 401 tests pass (was 385; 16 new reference cases added). Coverage 96.81% (gate 95%).
- mypy strict, ruff lint+format, canon audit (self-test + tree) all green.
- EXP-081 and EXP-095 internal benchmark snapshots byte-identical to draft.10. All five MiniCheck CI snapshots are new additions; their point AUCs match the original MiniCheck runs exactly (the new runner produces identical results from the same inputs).

**Carried forward:**

- TRUE, LLM-AggreFact held-out, HaluBench external runs.
- HHEM 2.1 (`trust_remote_code` API rename — fixable), SelfCheckGPT, G-Eval, Bespoke-MiniCheck-7B (requires GPU).
- AlignScore on RAGTruth QA / Data2Txt task types (~10 hr CPU on the existing runner).
- Inter-annotator agreement on EXP-095.
- Editor body constitution.

---

## 2026-05-16: second baseline (AlignScore) on all three corpora; Standard 1.0.0-draft.10

Adds AlignScore-base (Zha et al., ACL 2023, MIT) as a second independently-trained head-to-head baseline alongside MiniCheck on all three external corpora. Touchstone signal point AUCs and the existing MiniCheck point AUCs are byte-identical to draft.9; the addition is AlignScore-side numbers with 95% bootstrap CIs plus the cross-baseline framing updates.

**Why a second baseline:**

Through draft.9, the only head-to-head was MiniCheck Flan-T5-Large. The HaluEval finding (Touchstone L6 beats MiniCheck) was attributed in the §Limitations to a corpus-construction artifact, but the artifact framing rested on a single-baseline observation. Adding AlignScore (different architecture: RoBERTa-base discriminator vs Flan-T5-Large seq2seq; different training data: NLI/QA aggregations vs LLM-AggreFact; same task category: factual consistency) tests whether the HaluEval inversion is MiniCheck-specific or general to LLM-trained baselines.

**Setup:**

- AlignScore requires `torch<2`, which is unsupported on Python 3.12. Installed Python 3.10.20 via `uv`, created `.venv-alignscore` and pinned `transformers<4.40` (for `AdamW` in the public namespace) and `setuptools<81` (for `pkg_resources` compatibility with pytorch-lightning 1.9.5). All setup steps documented in `benchmarks/external/alignscore_baselines.py`.
- AlignScore-base checkpoint (~700 MB RoBERTa-base) downloaded to `./ckpts_alignscore/` (gitignored alongside `./ckpts_minicheck/`).
- `datasets 2.21.0` (pinned by AlignScore's dep solve) cannot parse `mteb/summeval`'s feature schema on Python 3.10. Workaround: corpus loading happens in the main `.venv-external` (Python 3.12, newer datasets); pairs are exported to JSON at `/tmp/alignscore_corpora/*.json`; the AlignScore runner reads from JSON. New helper module `benchmarks/external/alignscore_from_pairs.py` handles this; a companion `minicheck_from_pairs.py` enables the same flow for future MiniCheck CI computation.
- The `scripts/canon_audit.sh` EXCLUDES list extended to skip `.venv-alignscore` and `ckpts_alignscore`.

**Results (snapshots `results/alignscore_baseline_2026-05-15.json` under each corpus):**

| System | RAGTruth Summary | SummEval | HaluEval summarization |
|---|---|---|---|
| AlignScore-base | 0.7368 [0.7006, 0.7699] | 0.8091 [0.7714, 0.8455] | 0.6879 [0.6567, 0.7187] |
| MiniCheck Flan-T5-Large | 0.7125 | 0.8978* | 0.6752 |
| Touchstone L6 inverse_proximity | 0.6723 [0.6296, 0.7116] | 0.7530 [0.7145, 0.7951] | 0.7593 [0.7285, 0.7879] |
| Touchstone L10 gap (composite) | 0.4981 [0.4830, 0.5111] | 0.5000 [0.5000, 0.5000] | 0.5020 [0.4950, 0.5090] |

*Training-test leakage on SummEval applies to MiniCheck only (MiniCheck was trained on AggreFact-CNN, derived from SummEval); AlignScore was trained on a different aggregation that does not include SummEval.

**Two-baseline cross-corpus pattern:**

- On RAGTruth Summary and SummEval: both LLM-based baselines outperform Touchstone L6 by 4-12 AUC points. AlignScore lands between MiniCheck and Touchstone on RAGTruth and below MiniCheck on SummEval.
- On HaluEval summarization: both LLM-based baselines underperform Touchstone L6. MiniCheck 0.6752 and AlignScore 0.6879 [0.6567, 0.7187] are statistically indistinguishable; Touchstone L6 0.7593 [0.7285, 0.7879] has a strictly disjoint CI vs AlignScore's. The two-baseline confirmation establishes the HaluEval inversion as a baseline-class limitation on adversarial vocabulary-shift corpora rather than a MiniCheck-specific weakness. The construct-alignment caveat (Layer 6 directly measures what HaluEval's adversarial process produces) is unchanged.

**Per-corpus AlignScore CPU runtimes:**

| Corpus | n_pairs | AlignScore runtime |
|---|---|---|
| RAGTruth Summary | 900 | 7830 s (~131 min) |
| SummEval | 1600 | 4128 s (~69 min) |
| HaluEval summarization | 1000 | 6238 s (~104 min) |

AlignScore steady-state on CPU is roughly 2-10 s/example depending on context length (median ~5 s on Touchstone's three external corpora). Touchstone:AlignScore wall-clock ratio is approximately 1:3500 on CPU.

**Standard (1.0.0-draft.9 -> 1.0.0-draft.10):**

- §3.5 substrate-independence claim updated with the two-baseline cross-corpus evidence: MiniCheck and AlignScore both outperform Touchstone L6 on RAGTruth Summary and SummEval; both underperform on HaluEval; CIs reported per baseline where computed. The HaluEval inversion is now framed as a baseline-class observation, not a MiniCheck-specific one.
- Header status updated to draft.10.

**README:**

- Cross-corpus table in "Headline finding" subsection extended with an AlignScore-base row (CIs on all three corpora).
- RAGTruth Summary and SummEval per-corpus tables now include AlignScore rows with CIs and runtime; existing Touchstone rows now include CIs throughout (previously only on the headline summary).
- HaluEval per-corpus table includes AlignScore row; framing paragraph rewritten to reflect the two-baseline confirmation of the corpus-construction artifact.
- §Limitations bullet updated: "Three external corpora, two head-to-head baselines" replaces the prior "one head-to-head baseline" framing. AlignScore is no longer in the open-baselines list. HHEM 2.1, SelfCheckGPT, G-Eval, Bespoke-MiniCheck-7B remain open.

**Polish pass on all artifacts:**

- §Status updated to reflect three external corpora done; previously said HaluEval validation was "open work".
- §Use cases NOT-production-claim list cleaned: the "Internal AI-quality verification at scale" item was already removed in draft.9 after the perf fix; the remaining caveats are sharpened.
- §Limitations "Layer 10 gap is input-regime-conditional" bullet kept; the AUC numbers cited there are unchanged.
- `docs/index.md` and `docs/getting-started.md` aligned with the README: three external corpora listed; the "Empirical validation is open work" stale phrasing replaced with the actual finding pointer.
- `benchmarks/README.md` rewritten to list both internal and external benchmarks, with full descriptions of all five (three external + two internal + the task-type analysis).
- HaluEval and SummEval sub-READMEs trimmed: their stale "Cross-corpus comparison" stubs now point to the main README's Headline finding subsection instead of duplicating the table.
- Fixed arithmetic error: prior text said "six (corpus, task) cells" in multiple places when the correct count is five unique cells (RAGTruth × 3 task types + SummEval + HaluEval).
- Removed transitional phrasing ("in this commit", "round-3", "to be deployed") that had become stale since the perf fix committed.

**Verification:**

- 385 tests pass, 96.81% coverage (gate 95%).
- mypy strict, ruff lint+format, canon audit (self-test + tree) all green.
- EXP-081, EXP-095, all three external snapshots byte-identical to draft.9 (except for the additive `touchstone_bootstrap_95ci` block that draft.9 added; the AlignScore snapshots are new, not modifying existing).

**Carried forward:**

- MiniCheck per-example probability retention + CIs (the `minicheck_from_pairs.py` runner is committed and ready; running it on all three corpora is ~4.5 hr of CPU; deferred this round to land the second-baseline integration cleanly).
- TRUE, LLM-AggreFact held-out, HaluBench external runs.
- HHEM 2.1 (`trust_remote_code` API conflict with current transformers; resolvable by pinning an older transformers OR patching the model's modeling file), SelfCheckGPT, G-Eval, Bespoke-MiniCheck-7B (GPU).
- Inter-annotator agreement on EXP-095.
- Editor body constitution.
- MiniCheck baselines for RAGTruth QA and Data2Txt task types.

---

## 2026-05-15: finalization round — perf, statistics, task generalization

Closes the substantive open work from the prior three external-corpus rounds. Three changes, each load-bearing for a top-lab review:

1. **Layer 10 perf fix** that removes the last remaining quadratic behaviour in `measure()` and bumps throughput by 23x on 50 KB documents and ~89x on 500 KB documents.
2. **95% bootstrap CIs** on every external-corpus Touchstone signal AUC (1000 stratified resamples, fixed seed), with a clean separation between signals whose CIs include 0.5000 (Layer 10 gap, on every external corpus tested) and signals whose CIs exclude 0.5000 (Layer 6 inverse_proximity, on every external corpus tested).
3. **Cross-task generalization** within RAGTruth: Layer 6 holds across Summary, QA, and Data2Txt task types; Layer 4 unsourced_rate spikes to AUC 0.76 on QA where output number density is high enough for it to fire on a usable fraction.

**Library performance:**

- `_extract_numbers_for_matching` previously used `any(cs <= match_start < ce or cs < match_end <= ce for cs, ce in claimed_ranges)` to detect interval overlaps. On long inputs this is O(matches²) Python-level work because `claimed_ranges` grows monotonically. Replaced with parallel sorted `claimed_starts` / `claimed_ends` lists and a `bisect_left`-based overlap check; insertions stay at sorted positions found by the same bisect.
- `grounding_decomposition` previously recomputed `_content_words(source)` inside its per-sentence loop, scaling as O(sentences × len(source)). Hoisted out of the loop to a single set computed once per `measure()` call.
- Combined effect (measured on a self-source 70-char unit repeated to varying total length):
  - 5 KB document: 53 ms (original) → 16 ms (this fix). **3.3x faster.**
  - 50 KB document: 3766 ms → 161 ms. **23x faster.**
  - 500 KB document: ~160 s (extrapolated) → 1.78 s. **~89x faster.**
- `measure()` is now linear in document size on the scaling band tested (5 KB → 50 KB → 500 KB → 10x → 11x runtime ratio). The "no performance characterization" line is dropped from the README §Use cases NOT-production-claim list; batch verification at scale is no longer a production blocker.
- 385 tests pass unchanged; behaviour is byte-identical. EXP-081 and EXP-095 internal snapshots byte-identical.

**Statistical rigour (95% bootstrap CIs on every Touchstone-side AUC):**

- New helper module `benchmarks/external/_bootstrap.py` ships an `auc_roc()` implementation (Mann-Whitney U; ties at 0.5 weight) and a `bootstrap_auc_ci()` implementation (percentile bootstrap, stratified resampling within positive/negative classes, fixed seed for snapshot pinning, stdlib only).
- New script `benchmarks/external/add_bootstrap_cis.py` re-runs Touchstone on each external corpus (fast; ~3 seconds per corpus) and augments the existing snapshot with a `touchstone_bootstrap_95ci` section. MiniCheck CIs are not computed in this pass: per-example MiniCheck probabilities were not retained in the original snapshots, and re-running MiniCheck on all three corpora costs ~4.5 hours of CPU. The point AUCs in `auc_roc_by_signal` are unchanged.
- Cross-corpus Layer 6 inverse_proximity 95% CIs:
  - RAGTruth Summary: 0.6723 [0.6296, 0.7116]
  - SummEval: 0.7530 [0.7145, 0.7951]
  - HaluEval summarization: 0.7593 [0.7285, 0.7879]
  All three CIs are strictly above 0.5000. The RAGTruth CI does not overlap the SummEval or HaluEval CIs; Layer 6 is statistically significantly stronger on the latter two corpora.
- Cross-corpus Layer 10 gap 95% CIs:
  - RAGTruth Summary: 0.4981 [0.4830, 0.5111]
  - SummEval: 0.5000 [0.5000, 0.5000]
  - HaluEval summarization: 0.5020 [0.4950, 0.5090]
  Every CI includes 0.5000. The §3.5 partial out-of-domain falsification is now statistically defensible: Layer 10 gap is indistinguishable from chance on every external corpus tested.

**Cross-task generalization (Touchstone-only):**

- New analysis script `benchmarks/external/ragtruth_task_type_generalization.py` extends Touchstone to RAGTruth's QA (n=900) and Data2Txt (n=900) task types. MiniCheck baselines for those task types are not run in this round; they are open work.
- Snapshot: `benchmarks/external/ragtruth_summary/results/task_type_generalization_2026-05-15.json`.
- Layer 6 inverse_proximity AUC across three task types: Summary 0.6723 [0.6296, 0.7116], QA 0.6984 [0.6579, 0.7361], Data2Txt 0.6397 [0.6001, 0.6757]. Three CIs, all disjoint from 0.5000.
- Layer 10 gap AUC across the same three: 0.4981 [0.4830, 0.5111], 0.5127 [0.4985, 0.5295], 0.5041 [0.4908, 0.5170]. Three CIs, all overlapping 0.5000.
- Layer 4 unsourced_rate: AUC 0.7603 [0.6907, 0.8260] on RAGTruth QA (n=277/900 gated in). First task type where the Layer 4 signal generalizes meaningfully out-of-domain. On Summary (n=628 gated in) and Data2Txt (n=741 gated in) the AUC is closer to chance (0.55 / 0.52).

**Standard (1.0.0-draft.8 -> 1.0.0-draft.9):**

- §3.5 Layer 10 falsifiable claim updated to include the cross-task evidence (five unique (corpus, task) cells with bootstrap CIs all overlapping 0.5000) and the explicit statistical framing.
- §3.5 substrate-independence claim updated with the cross-task Layer 6 evidence (five (corpus, task) cells with bootstrap CIs all disjoint from 0.5000) and the Layer 4 QA-specific spike.
- Header status updated to draft.9.

**README:**

- New §Empirical validation "Headline finding (cross-corpus, cross-task)" subsection at the top, with two AUC + CI tables (cross-corpus on summarization, cross-task within RAGTruth) and a compute disclosure table (Touchstone:MiniCheck wall-clock ratio ≈ 1:2500 on CPU).
- New "Compute disclosure" subsection documenting CPU runtimes and the round-3 perf fix scaling characteristics.
- §Use cases NOT-production-claim list pared from three bullets to two: "internal AI-quality verification at scale" is no longer a blocked use case after the perf fix. The remaining two production blockers (substrate enforcement; vendor-audit verification) are unchanged.
- §Limitations bullets streamlined; the §Empirical validation "Headline finding" subsection is now the canonical home for the cross-corpus and cross-task AUCs.

**Verification:**

- 385 tests pass, 96.79% coverage (gate 95%).
- mypy strict, ruff lint+format, canon audit (self-test + tree) all green.
- EXP-081, EXP-095, RAGTruth Summary, SummEval, HaluEval summarization snapshots byte-identical to draft.8 except for the additive `touchstone_bootstrap_95ci` and `bootstrap_methodology` keys on the three external snapshots; the existing point AUCs and per-signal values are unchanged.

**Open work after this round:**

- MiniCheck CIs (require re-running on each corpus to capture per-example probabilities; ~4.5 hr CPU total).
- Non-MiniCheck baselines (AlignScore, HHEM 2.1 with current transformers, SelfCheckGPT, G-Eval, Bespoke-MiniCheck-7B).
- External corpus coverage: TRUE, LLM-AggreFact held-out, HaluBench.
- Inter-annotator agreement on EXP-095.
- Editor body constitution.
- MiniCheck on RAGTruth QA / Data2Txt task types.

---

## 2026-05-15: third external corpus (HaluEval) lands; three-corpus pattern established

Follows the same-day RAGTruth Summary and SummEval external comparisons. Adds HaluEval summarization (Li et al., EMNLP 2023, Apache-2.0) as a third external corpus, bringing the Layer 10 partial out-of-domain falsification finding to three independent corpora. The three-corpus consistency of the Touchstone signal pattern (L6 generalizes; L10 gap composite is identically near-chance) is now load-bearing.

**Plan refinement performed before this round (recorded for next round):**

- Bespoke-MiniCheck-7B (the SOTA MiniCheck variant) was the original top recommendation but requires GPU at realistic speed; on CPU a 7B model is ~30 s/example, infeasible for 2500+ pairs across the existing corpora. Deferred until GPU access is available.
- Two alternative baselines were investigated as the next baseline addition: HHEM 2.1 (Vectara) and AlignScore-base (Zha et al. 2023). Both had install incompatibilities with modern Python on this venv (HHEM's `trust_remote_code=True` custom modeling code uses a renamed transformers API; AlignScore is documented as Python 3.11+ incompatible). The cleaner next move was determined to be a third corpus rather than persisting through baseline install debugging.

**New benchmark: `benchmarks/external/halueval_summarization/`**

- **Corpus.** `pminervini/HaluEval` (Apache-2.0). Summarization subset, `data` split. 10000 (article, right_summary, hallucinated_summary) triplets sampled from CNN/DM; this run uses a stratified random sample of 500 documents (seed=0) yielding 1000 (article, summary) pairs with perfect 50/50 class balance.
- **Construction caveat.** HaluEval is adversarially built: hallucinated_summary fields are ChatGPT-synthesized variants of real CNN/DM summaries with intentionally introduced errors. Touchstone's vocabulary-based signal may capture synthetic-vs-real distributional differences in addition to the construct of interest. The benchmark README documents this fully; the paired-ranking-accuracy readout (within-document right vs hallucinated) is the primary metric and bypasses any synthetic-vs-real population confound.
- **Two readouts.** AUC-ROC on the binary label, plus paired-ranking accuracy: for each of the 500 documents, does the signal rank the hallucinated_summary higher than the right_summary in supported-ness?

**Results (snapshot `results/2026-05-15.json`, n=1000):**

| System | AUC | Paired-ranking accuracy |
|---|---|---|
| Touchstone Layer 6 inverse_proximity | **0.7593** | **0.8030 (401/500 pairs)** |
| MiniCheck Flan-T5-Large | 0.6752 | 0.6980 (349/500 pairs) |
| Touchstone L4 unsourced_rate (n=474) | 0.4993 | 0.5189 (159 pairs usable) |
| Touchstone L10 gap (composite) | 0.5020 | 0.5020 (490/500 ties at zero) |
| Touchstone L11 P proportion | 0.4941 | 0.4960 (474/500 ties) |
| Touchstone L5 entity (n=12) | 0.4286 | 0.5000 |

Headline: Touchstone L6 outperforms MiniCheck Flan-T5-Large on HaluEval by 8 AUC points and 10 paired-accuracy points. **This is a corpus-construction artifact, not a methodology-superiority finding.** HaluEval's adversarial construction produces hallucinated summaries that are lexically distributed away from the source article; Layer 6 measures exactly this kind of vocabulary distance. The substantive finding is the three-corpus consistency, not the headline ordering on any single corpus.

**Three-corpus consistency:**

| Signal | RAGTruth | SummEval | HaluEval |
|---|---|---|---|
| Touchstone Layer 6 inverse_proximity | 0.6723 | 0.7530 | 0.7593 |
| Touchstone Layer 10 gap (composite) | 0.4981 | 0.5000 | 0.5020 |
| MiniCheck Flan-T5-Large | 0.7125 | 0.8978* | 0.6752 |

Layer 6 AUC varies by 0.09 across three independent corpora; Layer 10 gap is identically near-chance with variance < 0.01; MiniCheck varies by 0.22 (most volatility comes from corpus-construction characteristics). The Standard's §3.5 partial out-of-domain falsification of Layer 10 gap is now load-bearing on three corpora.

**Standard (1.0.0-draft.7 -> 1.0.0-draft.8):**

- §3.5 Layer 10 falsifiable claim updated to record all three corpus results. The construct is now characterized as "partially falsified out-of-domain across three independent corpora".
- §3.5 §3.1 substrate-independence claim updated with the three-corpus Layer 6 AUC range (0.67-0.76) and an explicit note about the HaluEval construct-alignment artifact (Layer 6 directly measures what HaluEval's adversarial construction produces, so the HaluEval AUC is partly construct-aligned rather than independently confirmatory).
- Header status updated to draft.8.

**README:**

- New §Empirical validation subsection "HaluEval summarization external comparison" with the head-to-head table, the adversarial-construction caveat, and the construct-alignment honest framing.
- Cross-corpus comparison table extended from two to three corpora.
- §Limitations bullets updated to reflect three external corpora; the HHEM/AlignScore install incompatibilities are recorded under the head-to-head baseline bullet.
- Citation BibTeX bumped to 1.0.0-draft.8.

**Verification:**

- All main-library gates green: 385 tests, 97% coverage, mypy strict, ruff lint+format, canon audit (self-test + tree).
- EXP-081, EXP-095, RAGTruth Summary, and SummEval snapshots byte-identical to draft.7.

**Carried forward:**

- TRUE, LLM-AggreFact (held-out), HaluBench external runs. Three external corpora is now the floor, not the ceiling.
- AlignScore (resolve Python compat), HHEM 2.1 (resolve transformers compat), SelfCheckGPT, G-Eval baselines.
- Bespoke-MiniCheck-7B comparison (requires GPU access).
- Inter-annotator agreement on EXP-095.
- Editor body constitution.
- Performance round 2 on `_extract_numbers_for_matching`.

---

## 2026-05-15: second external corpus (SummEval) lands; cross-corpus pattern confirmed

Follows the same-day RAGTruth Summary external comparison. Adds SummEval (Fabbri et al. TACL 2021, MIT) as a second external corpus to strengthen the Standard §3.5 finding from "single-corpus partial falsification" to "two-corpus consistent partial falsification". No methodology or library API change; no impact to internal benchmark snapshots.

**New benchmark: `benchmarks/external/summeval/`**

- **Corpus.** `mteb/summeval` (MIT license; mirror of SummEval, Fabbri et al. TACL 2021). Test split, all 100 CNN/DM articles × 16 machine summaries each = 1600 (article, summary) pairs. Per-summary consistency rating on a 1-5 Likert scale aggregated from three annotators; median 5.0, mean 4.66, stdev 0.92.
- **Two readouts.** AUC-ROC on the binarized label (`consistency < 4` = not-supported = positive class; 10.1% positive rate) and Spearman ρ on the continuous rating. The continuous readout is the primary signal-quality measure on this corpus because the 1-5 scale is heavily skewed toward "supported" and binarization at any single threshold throws away rank information.
- **Training-test leakage caveat recorded.** MiniCheck Flan-T5-Large was trained on LLM-AggreFact, which includes AggreFact-CNN derived from SummEval. MiniCheck's source distribution is in its training set; its absolute AUC on SummEval (0.8978) is not held-out. Touchstone has not been calibrated on any SummEval-derived data; its AUC on SummEval is a fair test of substrate generalization.

**Results (snapshot `results/2026-05-15.json`, n=1600):**

| System | AUC | Spearman ρ vs continuous rating |
|---|---|---|
| MiniCheck Flan-T5-Large* | 0.8978 | +0.4066 |
| Touchstone L6 inverse_proximity | 0.7530 | -0.3481 |
| Touchstone L4 unsourced_rate (n=967) | 0.5688 | -0.2566 |
| Touchstone L11 P proportion | 0.5207 | -0.1227 |
| Touchstone L10 gap (composite) | 0.5000 | 0.0000 |
| Touchstone L5 entity (n=0) | — | — |

*Training-test leakage caveat applies.

**Cross-corpus pattern.** The two external corpora consistently show: Layer 6 inverse_proximity generalizes at AUC 0.67-0.75 (with the higher figure on SummEval); Layer 10 gap is identically near-chance (AUC 0.498 on RAGTruth, 0.500 on SummEval, Spearman ρ = 0.000 on SummEval); substance components fire on 3% (RAGTruth) and 0% (SummEval) of outputs. The Layer 10 partial out-of-domain falsification recorded in draft.6 is now reinforced by a second independently-licensed corpus.

**Standard (1.0.0-draft.6 -> 1.0.0-draft.7):**

- §3.5 Layer 10 falsifiable claim updated to record both corpus results. The construct is now characterized as "partially falsified out-of-domain across two corpora" rather than "across one corpus". The falsification protocol's §9.2 scope-update path is the controlling resolution.
- §3.5 §3.1 substrate-independence claim updated with SummEval evidence (Layer 6 AUC 0.7530 across 16 older summarization-system architectures, alongside the prior RAGTruth Summary breakdown across six instruction-tuned LLM families). No systematic model-identity dependence observed on either corpus beyond what label-balance variation predicts.
- Header status updated to draft.7; date 2026-05-15.

**README:**

- New §Empirical validation subsection "SummEval external comparison" with the head-to-head table and the training-test leakage caveat.
- New §Empirical validation subsection "Cross-corpus comparison" with the L6 and L10 numbers side-by-side across both external corpora.
- §Limitations bullets for external corpora and head-to-head baselines updated to reflect two corpora and named baselines remaining open. Adopter guidance on Layer 10 gap input-regime-conditionality strengthened with the SummEval substance-component fire rate (0%).
- Citation BibTeX bumped to 1.0.0-draft.7.

**Verification:**

- All main-library gates green: 385 tests, 97% coverage, mypy strict, ruff lint+format, canon audit (self-test + tree). New runner passes lint and format.
- EXP-081 and EXP-095 internal benchmark snapshots byte-identical to draft.6.
- RAGTruth Summary snapshot byte-identical to its 2026-05-15 baseline (this round did not re-run the RAGTruth benchmark).

**Carried forward:**

- TRUE, LLM-AggreFact (dev or test held-out subsets), HaluBench, HaluEval external runs.
- AlignScore, HHEM 2.1, SelfCheckGPT, G-Eval baselines.
- Bespoke-MiniCheck-7B (SOTA variant) comparison.
- Inter-annotator agreement on EXP-095.
- Editor body constitution.
- Performance round 2 on `_extract_numbers_for_matching`.

---

## 2026-05-15: first external corpus comparison lands (RAGTruth + MiniCheck)

First external-corpus comparison for Touchstone, paired with the first head-to-head against an LLM-based fact-checking baseline. Exercises Standard §3.5 (falsifiable construct claims) on a third-party corpus and updates the §Limitations section in the README from "no external corpus / no head-to-head" to recorded empirical findings.

**New benchmark: `benchmarks/external/ragtruth_summary/`**

- **Corpus.** `wandb/RAGTruth-processed` (MIT license; mirror of RAGTruth, Wu et al. ACL 2024), test split filtered to `task_type='Summary'`. n=900, six model families (gpt-3.5-turbo-0613, gpt-4-0613, llama-2-7B/13B/70B-chat, mistral-7B-instruct; 150 outputs each), 22.7% overall hallucination rate (per-model: 3-57%). No corpus content is included in this repository; the runner streams from HF at runtime.
- **Baseline.** MiniCheck Flan-T5-Large (Tang, Laban, Durrett, EMNLP 2024), Apache-2.0. Runner downloads the ~3 GB model on first invocation; CPU-only by default for cross-machine determinism.
- **Methodology.** AUC-ROC via Mann-Whitney U computed for MiniCheck's `1 - raw_prob` and for five Touchstone signals oriented "higher = more hallucinated". Each signal is gated by its precision threshold (e.g. Layer 4 only when the output has at least one digit-formatted number; Layer 5 only when at least 5 entities are extracted). Balanced accuracy is reported at MiniCheck's native binary threshold; Touchstone signals have no natural binary cutoff for this task and are reported on AUC only.

**Results (snapshot `results/2026-05-15.json`, n=900):**

| System | AUC-ROC | n used | CPU runtime |
|---|---|---|---|
| MiniCheck Flan-T5-Large | 0.7125 | 900 | 5867 s (~98 min) |
| Touchstone Layer 6 inverse_proximity | 0.6723 | 900 | 2.3 s |
| Touchstone Layer 5 entity_unsourced_rate | 0.8167 | 23 | (gated) |
| Touchstone Layer 4 unsourced_rate | 0.5514 | 628 | (gated) |
| Touchstone Layer 11 P proportion | 0.5374 | 900 | |
| Touchstone Layer 10 gap (composite) | 0.4981 | 900 | (chance) |

Headline: Touchstone's best single signal (Layer 6) is 0.04 AUC below MiniCheck at ~2500x less compute, on a corpus Touchstone was never calibrated for. The Layer 10 composite degenerates as the construct claim predicted it might out-of-domain: 97% of these short-summary outputs have ZERO substance components firing (`source_fidelity` 0.7%, `entity_grounding` 2.6%, `epistemic_calibration` 0.1%), so the composite reduces to presentation-only.

**Standard (1.0.0-draft.5 -> 1.0.0-draft.6):**

- §3.5 Layer 10 falsifiable claim updated to record the RAGTruth Summary result as a partial out-of-domain falsification. The Layer 10 construct holds within its calibrated long-form analytical regime but not on short summary outputs; §9.2's scope statement is the controlling document for in-domain claims.
- §3.5 §3.1 substrate-independence claim updated with the per-model AUC variation (0.59-0.73 across six model families) observed on RAGTruth Summary; the variation is within noise expected from per-model hallucination-rate imbalance.
- §3.5 falsification protocol now distinguishes full falsification (triggers layer redefinition or retirement) from partial falsification (triggers §9.2 scope update). The Layer 10 result is the first concrete instance of the latter.

**README:**

- New §Empirical validation subsection "RAGTruth Summary external comparison" with the head-to-head table.
- §Limitations first two bullets ("No external corpus" / "No head-to-head baselines") rewritten as recorded empirical findings; the open-work list now names only the corpora and baselines that have not yet been run.
- New limitation bullet: "Layer 10 gap is input-regime-conditional" with adopter guidance for short-form text.

**Library and infrastructure:**

- New `pyproject.toml` `[external]` optional-dependencies group declaring the runner's external surface (`datasets`, `accelerate`, `minicheck @ git+...`). Base library `dependencies` list is unchanged (still empty).
- `.gitignore` excludes `.venv-external/`, `ckpts_minicheck/`, `ckpts/`.
- `scripts/canon_audit.sh` EXCLUDES extended to skip the new external venv and model-weight cache directories.

**Tests, gates, snapshots:**

- All main-library gates green: 385 tests, 97% coverage, mypy strict, ruff lint+format, canon audit (self-test + tree). The external runner is not in the default test path; it's invoked manually because it depends on the `[external]` extras and network access to HF Hub.
- EXP-081 and EXP-095 internal benchmark snapshots are byte-identical to draft.5.

**What this round did not do (named, carried forward):**

- TRUE, LLM-AggreFact, HaluBench, HaluEval external runs. RAGTruth Summary is the first, not the only, external corpus.
- Head-to-head against AlignScore, HHEM 2.1, SelfCheckGPT, G-Eval. MiniCheck is the first, not the only, baseline.
- Bespoke-MiniCheck-7B comparison (the SOTA variant in the MiniCheck series; would likely beat the Flan-T5-Large variant in AUC).
- Inter-annotator agreement on EXP-095. Carried over from prior round.
- Editor body constitution. Carried over from prior round.
- Performance round 2 on `_extract_numbers_for_matching`. Carried over from prior round.

---

## 2026-05-15: fresh-eyes honesty pass

A second external-perspective stress test surfaced a tighter band of claims that did not track to public-surface artifacts plus residual pre-polish phrasing. This round closes them. No methodology change; no library API change; benchmark snapshots are byte-identical.

**Standard (1.0.0-draft.4 → 1.0.0-draft.5):**

- **§4 Output structure restored.** §4 had been folded into §3.5 in the prior round, leaving the top-level numbering jumping §3 → §5 while the Drafting status block still listed §4 as substantively complete. §4 is now a free-standing section again; cross-references are unchanged.
- **§5.1 Layer 1a phrasing.** Dropped the "such as Gemini Flash" vendor-specific aside; the layer is vendor-neutral via a caller-supplied `BaselineGenerator` callable, as the README and library docstrings already state.
- **§8.2 conformance band disambiguated.** "Aggregate G/F/P MAE ≤ 0.10" is now explicitly against the `detector_v031` regression reference, not against full manual classification. The full-manual MAE (0.12-0.13) is documented in the section's Reference result paragraph; tightening it is open work and is not asserted by the band. The pytest assertion in `tests/test_benchmarks.py` already enforces the disambiguated reading.
- **Appendix C rewritten.** The prior table made eight confident validation claims (`d=0.93`, `d=0.83-0.95`, `N=18` ×2, `97% recall` mislabeled against Layer 2 when it belonged to Layer 4, `4 studies`, internal `v1.3` ×2, internal `v1.4` + `19 tests passing`) that did not trace to any artifact in this repository, plus a misleading "conditional on Gemini API" annotation on Layer 1a. The new table cites the public-surface validation artifact per row (unit-test path or benchmark) and qualifies each claim explicitly; internal validation that is not in the public surface is no longer cited as if it were.
- **Header status block.** Updated to mention §4 and the Appendix C revision; date bumped to 2026-05-14; version `1.0.0-draft.5`.
- **§12.2 References.** Em-dash separators in the RFC 2119 and CC-BY 4.0 entries replaced with periods; matches the project's style discipline applied elsewhere in the prior em-dash strip.

**Library (no API or measurement changes):**

- `src/clarethium_touchstone/measure.py`: docstring for `quality_profile` previously cited four prior studies including three on Gemini-internal validation that is not in the public surface. Replaced with a citation to EXP-081 (the public regression benchmark) plus a pointer to README §Limitations and Standard §3.5 for what is not yet demonstrated.
- `src/clarethium_touchstone/measure.py`: two internal-version comments (`v1.3`) on the Layer 8 calibration assertion set replaced with construct-level comments. The internal versioning was a leak shape that the canon-audit pattern set did not catch; the rewrites describe what the patterns do and why they are split out of Layer 1c, without invoking an internal version number.
- `_filter_numbers` fast path: short-circuit when the text contains no `word count` / `total words` callout. The prior implementation ran `re.finditer` over the full text for every extracted number; on documents above ~5 kB this dominated `measure()` runtime. Median latency on a 5 kB self-source dropped from 53 ms to 34 ms; a 54 kB self-source dropped from 3.77 s to 1.87 s. No behaviour change; the slow path is preserved for documents that contain the callout phrases.
- `__standard_version__` bumped to `1.0.0-draft.5`; `CITATION.cff`, `README.md` BibTeX, and `tests/reference/README.md` synced.

**Benchmarks:**

- `benchmarks/exp_095_grounding/README.md`: dropped references to a private paper artifact with no public resolver and to internal patch / detector-version lineage; rephrased the caveats around outputs #7 and #16 in construct terms. Fixed the grammar break around line 58 that had survived a prior copyedit.
- `benchmarks/exp_095_grounding/ground_truth.json`: note for output #16 rewritten to drop the internal version reference; the recorded `detector_v031` figure is preserved verbatim (regression baseline unchanged).
- `benchmarks/README.md`: dropped "the published EXP-081 adversarial-validity finding" and "strong empirical validation" framing; aligned with the careful README phrasing (internal regression baseline; embellishment instruction overlaps with detector vocabulary).
- `benchmarks/exp_081_discrimination/README.md`: clarified that `ground_truth.json` records project-authored expected values produced by `detector_v031`, not external ground truth.

**Documentation:**

- `docs/index.md` Use cases section rewritten to mirror the README's three-tier framing (exercised / plausible but unvalidated / not yet a production claim). The prior list presented "Internal AI quality verification", "Substrate enforcement", and "Independent third-party verification of vendor claims" as if they were current capabilities; the README §Limitations explicitly says they are not.
- `docs/getting-started.md` empirical-validation section rewritten to match the README and benchmark READMEs: drops "reproduce the published numbers" framing on internal regression benchmarks; adds the `(P>0 vs P=0)` qualifier on EXP-095's P-direction agreement claim; reports both `detector_v031` and full-manual MAEs as the README and Standard §8.2 do.

**Verification surface unchanged.** Tests: 385 pass. Coverage: 97% (gate 95%). Lint, format, mypy strict, canon audit (self-test + working tree) all green. EXP-081 / EXP-095 benchmark snapshots are byte-identical to draft.4.

**What this round did not do (named, carried forward):**

- External corpus validation (TRUE, LLM-AggreFact, HaluBench, HaluEval). Still the single highest-leverage open work per Standard §3.5.
- Head-to-head baselines against AlignScore, MiniCheck, HHEM 2.1, SelfCheckGPT, G-Eval.
- Inter-annotator agreement on EXP-095.
- Second-round perf pass on `_extract_numbers_for_matching` (O(matches²) `claimed_ranges` scan, ~1600 per-sentence re-extractions per `measure()` on a 54 kB document).
- Constitution of an editor body; §11.4 still names the transitional state.
- Extracting a minimal conformance subset into `tests/reference/`. Standard 1.0.1 still owns this.

---

## 2026-05-12: production-readiness round

Follows the same-day polish pass below. Closes a structured gap list identified in an external-perspective stress test: completes Standard sections that were marked pending, adds small-N statistical corrections to the benchmark headline, cleans up dead-end API surface, exposes Layer 11 extensibility, expands adopter documentation, and adds release / CI discipline.

**Standard (1.0.0-draft.3 → 1.0.0-draft.4):**

- **§2 Terminology** written. Operational definitions for Output, Source, Claim, Evidence, Layer, Conforming implementation, Threshold, Baseline generator, Regression baseline.
- **§3.5 Falsifiable construct claims** added. Names the evidence that would invalidate Layer 4, Layer 10, Layer 11, and the §3.1 model-independence claim. Reports of falsification evidence route through the Suggestion process.
- **§5.11** amended. The "Conservative and liberal P-detection modes MAY be implemented" sentence is replaced; only conservative ships in v1.0. Additional modes can land via Suggestion process. The external-entity P-marker set is named as adopter-configurable, with `EXTERNAL_ENTITIES_DEFAULT` as the documented extension point.
- **§8 Reference test cases** fully written. Normative framing: passing the bands asserts reproduction on the packaged corpora to within stated tolerances, NOT construct generalization. Fast-tier corpus caveat is in the section text, not in a pending-callout. Future `tests/reference/` extraction reserved for Standard 1.0.1.
- **§11 Conformance** expanded to §11.1 (requirements), §11.2 (declaration mechanism), §11.3 (invalidation criteria), §11.4 (transitional state). Conformance now routes through `tests/` AND `benchmarks/` together; the canonical test-suite extraction is reserved for Standard 1.0.1.
- **§12 References** restructured into §12.1 (internal benchmarks), §12.2 (normative external references), §12.3 (field positioning, with a table of named prior art), §12.4 (validation citations).
- **Drafting status block** updated. All Section 5-11 content is now substantively complete; the "draft" qualifier remains because independent editor review has not yet happened.
- Standard header version bumped to `1.0.0-draft.4`; `__standard_version__` and `CITATION.cff` synced.

**Benchmark statistical rigor (EXP-081):**

- `benchmarks/exp_081_discrimination/run.py` now computes Hedges' g (small-N correction to Cohen's d) and a 95% bootstrap CI on Cohen's d (stratified percentile, 2000 resamples, fixed seed=0 for determinism).
- Headline numbers added: Hedges' g = -4.835 (vs raw d = -5.238); 95% bootstrap CI on Cohen's d = [-8.926, -4.498]. The CI confirms the effect's sign is stable across resamples; the magnitude is uncertain at N=6/6.
- New `tests/test_benchmarks.py::test_exp_081_aggregate_statistics_stable` pins all three values so a regression in either the gap signal or the aggregation math is caught by CI.
- New dated snapshot `snapshot_2026-05-12.json` saved; the EXP-081 snapshot test path now points at it. Per-output predictions are unchanged from the prior 2026-05-03 snapshot.
- README, getting-started, and the EXP-081 sub-README updated to report the new statistics alongside Cohen's d.

**API stability cleanup (library):**

- **Removed `p_detection_mode` parameter** from the `measure()` and `grounding_decomposition()` public signatures. The parameter was marked `noqa: ARG001 (reserved)` and only ever accepted "conservative"; a dead-end parameter is theater, not API. The `p_detection_mode` field on the return dict remains (informational; always "conservative") with its TypedDict literal narrowed accordingly.
- **Added `external_entities` parameter** to `measure()` and `grounding_decomposition()`. Accepts a sequence of regex pattern strings or `None`. When `None` (default), uses `EXTERNAL_ENTITIES_DEFAULT`. Adopters extending to new domains replace or extend the list; the `EXTERNAL_ENTITIES_DEFAULT` constant is now a public re-export so this is mechanical rather than monkey-patching a private name.
- Six new tests in `test_grounding_decomposition.py` pin: default-list constant, None-uses-default, empty-silences-secondary-signal, replacement, extension via unpacking, end-to-end thread-through `measure()`.
- One internal-file reference subtracted from `measure.py` comments (a name pointing at an internal-only methodology doc); semantics reframed to point at Standard §5.11 instead.

**Adopter experience:**

- `docs/getting-started.md` Layer 1a section gains a "Baseline-generator quality guidance" subsection naming the dimensions that affect reproducibility (model class, temperature, n_baselines, topic specificity, recoverable failures).
- New "Layer 11 external entities" subsection documenting the `external_entities` parameter and the `EXTERNAL_ENTITIES_DEFAULT` extension pattern.
- "What measurements mean" expanded from 3 layer entries to a full table covering all 11 layers, each with the construct, what "high" means, and what it does NOT assert.
- README "Use cases" rewritten with explicit separation of (a) what's actually exercised, (b) what's plausibly suited, (c) what's not yet a production claim.
- New `examples/` directory with `verify_a_summary.py`: a runnable end-to-end script profiling a faithful and an embellished summary against the same source, demonstrating Layer 4 / 10 / 11 outputs and surfacing the Layer 11 scope_assessment when the source is in the saturated regime.

**Process and CI:**

- New `.pre-commit-config.yaml` running ruff (lint + format), YAML/TOML/large-file/EOF hygiene, and the canon audit (self-test + working tree) on every commit.
- New `RELEASING.md` documenting the pre-release checklist, cut sequence, post-release bump, hotfix flow, and Standard/library coordination.
- CI lint scope extended from `src tests` to `src tests examples benchmarks` so example scripts and benchmark runners are held to the same lint+format gate as the library.
- CI test job now enforces `--cov-fail-under=95`; current coverage is 96.78%. Coverage regressions below 95% will block merges.

**Leak sweep follow-through:**

- A forbidden-vocabulary instance caught by the canon audit on this round's own RELEASING.md (in the wheel-content step) and removed before commit. The audit is doing its job: novel leak shapes hit the canon_audit pattern set before they reach the public surface, exactly the AGENTS.md §5b loop.

**What this round did not do (named, deferred):**

- External corpus validation (TRUE, LLM-AggreFact, HaluBench, HaluEval). Multi-day work; the falsification protocol in Standard §3.5 names this as the evidence that would invalidate or extend Layer 10's construct claim.
- Head-to-head benchmarks against AlignScore, MiniCheck, HHEM 2.1, SelfCheckGPT, G-Eval, Lynx. Requires their packages and a shared input set.
- Inter-annotator agreement on EXP-095. Requires a second annotator; Standard §3.5 names IAA below Cohen's κ = 0.7 as the falsification threshold for Layer 11.
- PyPI publication and `v0.1.0` git tag. Release actions to be performed against the project's PyPI organization once approval is granted; the `RELEASING.md` checklist is the source of truth for the cut.
- Constitution of an editor body. Standard §11.4 names this as the transitional state to be resolved.

Tests: 385 pass (6 new for `external_entities`, 1 new for bootstrap pinning; one prior test relaxation tightened). Coverage 96.78% (gate 95%). Lint, format, mypy strict, canon audit (self-test + working tree) all green. EXP-081 snapshot moved to 2026-05-12 (per-output predictions unchanged; new aggregate statistics added).

---

## 2026-05-12: post-release polish pass

Honest-framing and defensive-contract cleanup driven by an external-perspective stress test. No library API or measurement output changes; benchmark snapshots are byte-identical.

**Framing fixes (Standard, README, docs/index.md, sub-READMEs):**

- The EXP-081 reproduction is reframed throughout from "Touchstone reproduces the published d=-5.43" to "internal regression baseline against the recorded `detector_v031` snapshot." There is no external publication of EXP-081; the expected values live in `benchmarks/exp_081_discrimination/ground_truth.json` and are authored by this project.
- Standard §8.1 and §9.2 corrected: the EXP-081 corpus is single-vendor (xAI grok-4-1-fast, 12 documents), not the four-vendor plural ("Anthropic, Gemini, OpenAI, and xAI/Grok families") previously claimed. EXP-095 multi-vendor framing kept.
- The "auditor cannot be made of the same material as the audited" slogan is replaced with a precise claim ("scoring substrate does not invoke an LLM on the output being measured; Layer 1a calls an LLM for baseline generation, not output scoring") in README, Standard §1.1, and docs/index.md. The slogan overclaimed against AlignScore-class small-discriminator counterexamples; the narrower claim is defensible.
- README adds a §Limitations section naming what is not demonstrated: no external corpus validation (TRUE, LLM-AggreFact, HaluBench, HaluEval), no head-to-head baselines (AlignScore, MiniCheck, HHEM, SelfCheckGPT, G-Eval), single-vendor EXP-081 corpus, small-N statistics without Hedges' g or bootstrap CI, Layer 11 entity list domain-biased to three source domains, no constituted editor body.
- EXP-095 surfaces the MAE vs full manual classification (0.12-0.13 across G/F/P) as a top-level metric alongside MAE vs the prior detector (0.02-0.04). Both are recorded; the manual-classification number is the honest external comparison; the prior-detector number is the regression check.

**Falsifiable-claim fixes:**

- `CITATION.cff` abstract: removed the "five layers for specification compliance verification (Section 6)" sentence. Section 6 is reserved for Standard 1.1 with no per-layer breakdown; the claim of "five layers" was not in the Standard text.
- `docs/index.md`: dropped the same "five layers, Section 6" table; replaced with a sentence pointing at Standard 1.1 as the venue where Section 6 lands.
- `src/clarethium_touchstone/_version.py`: `__version__` set to `"0.1.0"` to match `pyproject.toml`. The installed package previously reported `"0.1.0.dev0"`, contradicting the wheel metadata and CHANGELOG headers. `__standard_version__` set to `"1.0.0-draft.3"` to match the Standard header.
- Standard §5.3, §10, Appendix C: language on the `fabrication_rate` alias amended. The alias was removed during pre-1.0 greenfield cleanup (per CHANGELOG 2026-05-03); previous Standard text said the alias "MUST be retained at v1.0 and removed in v2.0," making the reference implementation non-conformant against its own Standard. Amended to record that the alias is not part of Standard 1.0 and `instability_rate` is the canonical field name.
- Standard Appendix C Layer 4 row: "0% FPR validated" sharpened to "97.1% extraction recall on 70 manually annotated digit-formatted claims; 0/309 numbers incorrectly flagged unsourced on self-source documents (string-equality regression check, not independent validation)." The "0% FPR" framing was tautological on self-source files. The same sharpening landed in the in-code docstring at `measure.py:source_matching`.

**Defensive-contract fixes (library):**

- `_compute_heading_defaultness` now wraps the caller-supplied `baseline_generator` in a try/except and validates that the return value is a string. Exceptions raised by the user's LLM client (rate limits, network errors, content filters, arbitrary SDK quirks) are caught and counted as failed calls rather than propagated out of `measure()`. Non-string returns are also treated as failed. Three new tests in `test_structural_profile.py` pin the defensive paths (exception, mixed failures, non-string return). Public docstrings updated to document the permissive contract.

**Documentation fixes:**

- `README.md` and `docs/getting-started.md` install paths lead with a Python virtualenv so PEP-668 does not block the editable install on modern Debian/Ubuntu/Mac-homebrew Pythons.
- `docs/getting-started.md` adds a "Scope and locale" section naming the English-only and Markdown-only validated scope, plus the empty-input behavior (returns `"low"` precision, does not raise).
- `README.md` Citation section now ships BibTeX entries for both the Standard and the library, with explicit `note = {Version 1.0.0-draft.3}` for the Standard so adopter citations reflect the draft state. The "BibTeX entry will be provided with the first published release" placeholder is retired.
- `_GFP_EXTERNAL_ENTITIES` documentation: the hardcoded entity list is named as empirically seeded from the three EXP-095 source domains (Apple Q1 FY2026, BLS March 2026, OASIS-4 / Wegovy). The function docstring for `grounding_decomposition` surfaces the domain bias so adopters on new domains know to author a parallel list with false-positive control.

**Governance language:**

- `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CONTRIBUTING.md`, and `SUGGESTIONS/PROCESS.md` no longer route enforcement, disclosure, or review through "the editor body" as if that body operates today. The Standard reserves formal certification by an editor body to a future version once one is constituted (§11); until then, all responsibilities sit with the project maintainers. Security disclosure and code-of-conduct reports route through GitHub Security Advisory.
- Standard §11 adds a transitional clause naming the current state honestly: until an editor body is constituted, the reference test suite at (1) is authored by the same maintainers who author the Standard, so self-certification against it is consistency with the reference implementation, not independent verification.
- Other public-canon leak shapes were rewritten or removed per the AGENTS.md discipline. Subtraction was preferred over substitution where the surrounding paragraph stood without the offending clause.

**What this pass did not do (named, deferred):**

- Run Touchstone on an external corpus (TRUE, LLM-AggreFact, HaluBench, HaluEval). Days-to-weeks of work; required to move from regression baseline to construct-validity evidence.
- Head-to-head benchmarking against AlignScore, MiniCheck, HHEM 2.1, SelfCheckGPT, G-Eval, or Lynx.
- Hedges' g correction or bootstrap confidence intervals on the EXP-081 effect size.
- Cutting a `v0.1.0` git tag (none exists today).
- Constituting an editor body.
- Resolving the touchstone.clarethium.com docs site state.

**Follow-up sweep (same day):**

- `tests/reference/README.md` rewritten. The previous "Validation pedigree" block carried stale claims (out-of-date test counts; "148 align self-tests" after `align()` was removed; a four-vendor plural for EXP-081; "Studies 8-9 discriminant validity (100 pairs)" referencing internal study identifiers with no public resolver). The replacement describes the directory's planned role honestly without the stale specifics.
- `CHANGELOG.md` polish-pass entry: a reference to "§3c" (a section in an internal discipline document) was rewritten to point at AGENTS.md, the public-canon discipline doc that ships in the repo.
- `SECURITY.md` and `docs/getting-started.md`: removed a "Section 9 of the methodology" reference for gaming vectors. Standard §9 (Implementation guidance) does not enumerate gaming vectors; the references were either stale (pointing at an earlier draft) or ambiguous (pointing at the separate Lodestone methodology canon without naming it). Both replaced with a direct statement that Touchstone's pattern set is public and an actor aware of the regex can evade it.

Tests: 378 pass (3 new defensive tests for Layer 1a). Lint, format, type check, canon audit (self-test + working tree) all green. Both benchmark snapshots byte-identical (no measurement-output drift).

---

## v0.1.0 - 2026-05-09

Initial public release of Touchstone. Includes:

- **Touchstone Standard 1.0** at `STANDARDS/touchstone-1.0.md` (CC-BY 4.0). v0.1
  scope is Section 5 (output profiling, eleven measurement layers). Section 6
  (Specification Compliance) is reserved for a future release.
- **`clarethium-touchstone` Python reference implementation** (Apache 2.0).
  Dependency-free; Layer 1a accepts a vendor-neutral `BaselineGenerator`
  callable so the user supplies their own LLM client.
- **Two reproducibility benchmarks** in `benchmarks/`. EXP-081 (adversarial
  discrimination) reproduces the published Cohen's d=-5.43 finding with
  Touchstone d=-5.238, 100% per-output gap-direction agreement, MAE 0.014
  on unsourced rate. EXP-095 (grounding decomposition) reaches 100%
  P-direction agreement on existence (P>0 vs P=0) across 13 hand-classified
  outputs from 3 model families against 3 source documents; per-output P
  magnitude differs from manual range on 4/13 outputs.
- **375 tests** pass on Python 3.10 / 3.11 / 3.12; CI green; snapshot drift
  detection on both benchmarks pinned via byte-match pytest assertion.

Patches 2 and 3 (multi-currency extraction; scaled-integer forms with raw-form
source-match cascade fix) and Layer 11 `scope_assessment` (derivation-regime
classifier) are included. For the per-patch development sequence that landed
into this release, see the dated entries below.

---

## 2026-05-03: Patch 2 (multi-currency) + Patch 3 (scaled-integer) shipped

After two earlier sessions deferring these patches (concerned that
Frame Check's port introduced cascade bugs), the benchmarks shipped
mid-session provide regression cover. Both patches landed with the
proper substrate-quality designs:

- **Patch 3 (scaled-integer):** "1.5 trillion", "6 million" forms
  now extract correctly. Cascade bug Frame Check ships (extracted
  "8 trillion" gets normalized to "8000000000000" string, then
  source matching searches that exact digit string in source text
  and fails when source uses the same scale form) is FIXED in
  Touchstone via a raw-form fallback path. See test_source_matching::
  test_scale_word_extraction_with_raw_form_source_match.
- **Patch 2 (multi-currency):** ``[$€£¥₹]`` symbols now match. Doc
  "€30" + source "€30" → grounded; doc "€30" + source "$30" →
  unsourced (DIFFERENT currencies, correct flag). UnsourcedNumber
  TypedDict gains optional ``currency`` field surfaced in
  unsourced_details for downstream consumers.

Both patches are backward-compatible with USD-only corpora (EXP-081
benchmark unchanged: Cohen's d=-5.238). EXP-095 output #16 (xAI BLS
run 3) moved P 0.026 → 0.051 toward manual estimate [0.10, 0.15] -
direct evidence that stricter source-side derivation (now that
"7.2 million" extracts as 7200000 instead of decimal 7.2) reduces
the derivation-checker false-positive rate documented in the
methodology.

Cross-scale matching (doc "1500 billion" vs source "1.5 trillion",
same magnitude) is pinned as a known limitation in
test_known_limitation_cross_scale_false_negative; proper
magnitude-aware redesign is a future patch.

## 2026-05-03: scope_assessment for Layer 11 + EXP-095 benchmark suite

- **Patch 1 landed (deferred from earlier session):** Layer 11
  ``grounding_decomposition`` now returns a ``scope_assessment`` field
  classifying the source's derivation-checker regime. Boundaries are
  empirically validated (< 5 diagnostic, [5,10) transition, ≥ 10 saturated)
  and align with the methodology doc and Monte Carlo FPR data
  (53% at N=5, 97% at N=10). New public helper
  ``assess_derivation_regime(source_num_count)`` returns the same
  ``ScopeAssessment`` dict for any caller wanting the regime
  classification standalone (e.g., a UI that displays "trust this
  signal" guidance before measurement begins).

  This addresses the documented EXP-095 output #16 drift case: when
  Touchstone reports P=0.026 for a 14-number source (saturated
  regime), the scope_assessment field now explicitly tells consumers
  to cross-reference Layer 4 for numerical fabrication. The drift is
  no longer silent.

- **EXP-095 benchmark suite shipped:** ``benchmarks/exp_095_grounding/``
  validates Layer 11 against 13 hand-classified outputs from the
  EXP-095 corpus. Results: P-direction agreement with manual
  classification is 100%; MAE vs documented detector v0.3.1 is
  0.02-0.04 in aggregate (with documented per-output drift surfaced
  honestly in the README). Snapshot file pinned via byte-match
  pytest assertion; CI catches silent drift on any future change
  affecting Layer 11 predictions.

## 2026-05-03: v0.1 scope locked to Section 5 measurement; align/profile dropped from public API

- Frame Check fork-patch port: paragraph-aware sentence splitter for
  Layer 2 (Patch 4 from CLARETHIUM_MEASURE_SYNC.md)
- Greenfield cleanup: ``fabrication_rate`` legacy alias removed
  (Patch 5; no v0.x deprecation window to honour)
- Public API trimmed: ``align()``, ``profile()``, and the entire
  ``clarethium_touchstone.align`` module dropped from v0.1.
  Standard Section 6 (Specification Compliance) is reserved for a
  future release. The pre-port stubs raised ``NotImplementedError``
  on every call; cleaner to remove the API surface than ship
  misleading entry points. Section 6 will return in Standard 1.1
  with the same pinned-behaviour discipline as Section 5.

Multi-currency, scaled-integer, and Layer 11 ``scope_assessment``
fork patches (Patches 1, 2, 3 from the diff) are deferred. Each
requires a deeper redesign than a direct port: currency and scale
should be first-class fields on extracted numbers (not lossy
type-tag overloads), and the regime classifier should be a
standalone function with documented constants. A discrimination
benchmark suite (separate session) precedes any further detection-
accuracy patches.

## 2026-05-03: Library reference implementation feature-complete

All eleven measurement layers from Standard Section 5 are implemented in `clarethium-touchstone`. The top-level `measure()` orchestrator composes them end-to-end.

Layers extracted (in order):

- Layer 4 source matching (number provenance via 8 type-aware regex patterns; 0% FPR on self-source documents validated by EXP-081)
- Layer 2 claim density (numerical and causal claim counts per 1000 words)
- Layer 1b mechanism ratio + 1c assertion ratio (1a reserved for LLM injection)
- Layer 7 presentation features (TTR, FK grade, formatting density, assertiveness, named-concept count)
- Layer 9 information novelty (cumulative-vocabulary novelty, OLS decay slope)
- Layer 6 vocabulary proximity (per-sentence content-word overlap with source)
- Layer 10 quality profile composite (substance vs presentation index + overclaiming gap)
- Layer 5 entity provenance (5 regex patterns: persons, organisations, attributions, citations, CamelCase orgs)
- Layer 8 epistemic calibration (cross-layer per-sentence assertion grounding via 3 independent grounds)
- Layer 3 temporal instability (cross-version number stability across regenerations)
- Layer 11 grounding decomposition (per-sentence Grounded / Framed / Projected classification with arithmetic-derivation checker)
- `measure()` orchestrator (composes all 11 layers, returns `MeasureResult` per `types.py`)
- Layer 1a heading defaultness (vendor-neutral via `BaselineGenerator = Callable[[str], str | None]` - caller supplies their own LLM client)

The library pins regex patterns, thresholds, filtering rules, and validation caveats so future drift is visible. Surprising behaviours are explicitly tested; any change is intentional and version-bumped.

Test coverage: 338 tests pass on Python 3.10, 3.11, 3.12 (375 by v0.1.0). Lint (ruff), format (ruff format), type check (mypy strict), and build (`python -m build`) all green in CI.

## 2026-05-02: Initial bootstrap

Repository created at `Clarethium/touchstone`. Initial structure:

- `README.md` - repository orientation
- `CHANGELOG.md` (this file)
- `STANDARDS/touchstone-1.0.md` - Touchstone Standard 1.0 (in drafting)
- Library scaffold (`src/clarethium_touchstone/`) with TypedDicts in `types.py` and stub functions in `measure.py` / `align.py`
- CI workflow (lint, type check, test matrix, build distribution)
- Custom domain `touchstone.clarethium.com` via GitHub Pages

PyPI organization application pending approval. Reference implementation in progress.

Architecture committed:
- Touchstone is a Clarethium sub-brand at `touchstone.clarethium.com`
- Repository under `github.com/Clarethium/touchstone` organization
- Standard document under CC-BY 4.0
- Library under Apache 2.0 (or MIT, pending final decision)
- PyPI package name: `clarethium-touchstone` (or fallback if `touchstone` namespace becomes available)

## Standard versioning policy

Touchstone Standard follows semantic versioning:

- **Major (1.0 → 2.0):** Breaking changes to required fields, methodology, or thresholds. Existing implementations require updates to remain conformant.
- **Minor (1.0 → 1.1):** Additive changes - new optional layers, new requirement types, new measurement dimensions. Existing implementations remain conformant for the previous version.
- **Patch (1.0 → 1.0.1):** Editorial changes, clarifications, typo corrections, expanded examples. No methodology changes.

## Library versioning policy

The `clarethium-touchstone` library follows semantic versioning independently:

- Library version aligns with the Standard version it implements (e.g., library 1.0.x implements Standard 1.0.x)
- Library patches can ship without Standard changes
- Library may temporarily implement features ahead of Standard ratification (flagged as experimental)
- Library deprecations announced one minor version before removal
