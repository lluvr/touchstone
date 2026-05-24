# Touchstone HANDOFF (fresh-agent context)

**Status as of 2026-05-24:** Touchstone is shipped at Standard 1.0.0-draft.15. Two PyPI distributions are live: [`clarethium-touchstone`](https://pypi.org/project/clarethium-touchstone/) v0.2.0 (the reference library) and [`touchstone-mcp`](https://pypi.org/project/touchstone-mcp/) v0.1.0 (the MCP server, depends on the library + `fastmcp`). The artifact does the ruthless self-assessment in README `§Empirical validation` and `Limitations`. This handoff doc tells a fresh agent picking up the project what is done, what is explicitly out of scope, and where to push if you continue.

## What is done

- **Standard text** at `STANDARDS/touchstone-1.0.md` — CC-BY 4.0. Eleven measurement layers specified with falsification criteria per layer.
- **Reference implementation** under `src/clarethium_touchstone/` (Apache 2.0), published as `clarethium-touchstone` v0.2.0 on PyPI. 452 library pytest tests pass; coverage at 97% with a 95% CI gate; ruff + mypy strict + Python 3.10 / 3.11 / 3.12 CI matrix green.
- **Touchstone MCP server** as its own PyPI distribution, [`touchstone-mcp`](https://pypi.org/project/touchstone-mcp/), under `touchstone-mcp/` in this repo (depends on `clarethium-touchstone` and `fastmcp`). Four MCP tools (`verify`, `measure`, `assess_derivation_regime`, `list_modes`) exposed via the `touchstone-mcp` console script for any Model Context Protocol host (Claude Desktop, Claude Code, Cursor, custom). Host-wiring docs at `docs/mcp.md`. Migration from the prior `clarethium-touchstone[mcp]` extra (last shipped under that path in `clarethium-touchstone==0.1.2`) documented in `CHANGELOG.md` v0.2.0 and `touchstone-mcp/CHANGELOG.md` v0.1.0.
- **Two internal regression benchmarks** (`benchmarks/exp_081_discrimination/`, `benchmarks/exp_095_grounding/`) with byte-pinned snapshots.
- **Three external corpus comparisons** (`benchmarks/external/{ragtruth_summary, summeval, halueval_summarization}/`) against MiniCheck Flan-T5-Large, AlignScore-base, and three trivial lexical baselines. All numbers with 95% bootstrap CIs.
- **Cross-task generalization analysis** within RAGTruth (Summary / QA / Data2Txt) at `benchmarks/external/ragtruth_task_type_generalization.py`.
- **Methodology document** at `docs/methodology.md` and **production-readiness analysis** at `docs/production_readiness.md` (128 KB, the operational deep-dive that includes the 16-case stress test, label-noise floor probe, FactScore-class baseline, within-cluster substrate mechanism check, BH / Bonferroni multi-comparison correction).
- **Canon audit + discipline gates** under `scripts/canon_audit.sh`, `AGENTS.md`, `.pre-commit-config.yaml`, `.gitleaks.toml`, and `.github/workflows/canon-audit.yml`.
- **Reference test suite** at `tests/reference/cases/` — language-agnostic JSON cases for second-party implementations.

## What is explicitly NOT done (open work)

Carried in README §Limitations and Standard §3 falsification criteria; surfacing here as a fresh-agent checklist.

### Corpora not yet validated against
- **TRUE** (Honovich et al. 2022)
- **LLM-AggreFact held-out** (Tang et al. 2024) — important because MiniCheck was trained on AggreFact-CNN, which is SummEval-derived; a held-out evaluation removes that leakage
- **HaluBench / Lynx** (Patronus 2024)

### Baselines not yet compared against
- **Bespoke-MiniCheck-7B** — requires GPU
- **GPT-4-as-judge** (or GPT-5, Claude 4.7, Gemini 3 etc.) — frontier-LLM judges that would score higher than the budget-tier MiniCheck / AlignScore in the current panel
- **HHEM 2.1** (Vectara) — currently blocked by a `trust_remote_code` API rename in `transformers`
- **SelfCheckGPT** (Manakul et al. 2023)
- **G-Eval** (Liu et al. 2023)
- **AlignScore on RAGTruth QA / Data2Txt** (only on the three summarization corpora currently)

### Domains out of validated scope
- Non-English text
- Legal documents
- Medical documents
- Code (output language is code, not natural language)
- Non-summarization output tasks (the cross-task evidence within RAGTruth is Summary / QA / Data2Txt only)

### Standard-side open work
- **§11 editor body is not yet constituted.** Conformance today is self-certification by passing the reference test suite. A formal editor body would enable third-party certification.
- **The Standard 1.1 `align()` / `profile()` APIs** are reserved but not specified.
- **Standard versioning** has been thought through (§10) but a published roadmap of upcoming changes is not yet shipped.

### Layer-level open work
- **Layer 11 entity list is domain-biased.** Hardcoded entity P-markers in `_GFP_EXTERNAL_ENTITIES` cover GLP-1 drugs, Apple products, BLS labor terms (the three EXP-095 source domains). On new domains, the secondary P-signal goes silent. Open work: domain-extension methodology for adopters.
- **Layer 10 gap is input-regime-conditional.** Holds on long-form analytical Markdown (EXP-081 internal); does NOT hold on short summary outputs (chance on all three external corpora). The §3.5 scope statement is updated; the Standard documents the regime. Open work: a regime-classifier that auto-selects which signals to trust on a given input.
- **EXP-081 corpus is single-vendor (xAI Grok 4.20).** Cross-vendor generalization within the fast tier and to flagship-tier model outputs is open research.

### Production-readiness open work
- **Substrate alone is NOT a standalone production hallucination detector** (README banner + production_readiness.md). Production use is two-stage: substrate as cheap-screen + LLM-based judge as primary discriminator. The `Verifier(mode="substrate_plus_judge")` API is wired and documented; observability-platform integration (Langfuse / Phoenix / Datadog / Helicone) is open work.
- **Adversarial robustness** — the regex / arithmetic substrate is public; an adversary aware of the patterns can evade. Not addressed in the current release; documented as a non-use-case in README §Use cases.

## Where the work compounds (if you continue)

The honest self-assessment in the README §Empirical validation already names the bind: simple lexical features capture ~70% of the discriminative signal at this signal-strength tier, and Touchstone Layer 6 is statistically indistinguishable from a 3-line word-overlap baseline. The methodology habits (bootstrap CIs everywhere, BH / Bonferroni correction, trivial-baseline anchor, holdout discipline, calibrated falsification protocol with status updates landing in the Standard text) are the durable contribution; the AUC itself is not.

That points to four directions where Touchstone's methodology compounds further, in priority order if AGI-compounding eval methodology is the goal.

### Direction 1: validate against an LLM-AggreFact held-out subset
Resolves the SummEval training-test leakage caveat that makes MiniCheck's 0.8978 AUC non-comparable. Single-corpus integration; estimated 1-2 days of work to write the adapter + run the panel. Highest-leverage single move because it cleans up the most-cited number in the README.

### Direction 2: frontier-LLM judge in the panel
Add GPT-4 / Claude 4.7 / Gemini 3 as the SOTA upper-bound for hallucination detection. The current panel's LLM-baseline ceiling is MiniCheck Flan-T5-Large (770M parameters). Adopters reading the panel cannot tell whether the 0.71-0.76 AUC band is "the problem is hard" or "we tested cheap baselines." A frontier-judge column resolves that. Estimated 2-3 days work + $50-100 in API calls.

### Direction 3: non-summarization domain validation
Run Touchstone on at least one (code, code review) or (legal text, legal source) or (medical text, medical source) corpus. Two outcomes are publishable: (a) the regex/arithmetic substrate generalizes → broader claim, (b) it does not → substrate is summarization-specific by construction. Estimated 1-2 weeks per domain.

### Direction 4: companion artifact
The Touchstone methodology habits (Standard + reference impl + bootstrap-CI empirical validation + adversarial falsification + multi-corpus consistency + honest trivial-baseline anchor) are reusable. Apply them to an evaluation problem that compounds with AGI capability scale: multi-modal verification, long-horizon agent outcome verification, adversarial-robust verification, mechanistic interpretability eval primitives, capability-under-deception measurement. The `Clarethium/agent-grounding` repo is the first companion attempt; see its own HANDOFF.md for status and caveats.

## What to NOT do (anti-patterns)

These are the patterns that wasted iteration cycles in prior sessions; surfaced here so a fresh agent recognizes them.

1. **More methodology-primitive refinement on the same corpora.** BH correction, Platt recalibration, strict falsifier, multi-comparison correction — these were all added once each. Adding a sixth or seventh measurement primitive on the same three external corpora is the converging-on-topics failure mode. Each is defensible in isolation; collectively they orbit the artifact without moving it. If you are about to add another measurement primitive without a corresponding new corpus or new domain, stop and pick an item from §"Where the work compounds" instead.

2. **More commentary on the trivial-baseline finding.** The README §Empirical validation already says the right thing in load-bearing-honesty paragraphs. Restating it longer or with more hedge words does not improve the artifact. If you have new data (a corpus where Touchstone L6 substantially beats word-overlap), update the table; otherwise leave the finding alone.

3. **More §-numbered subsections in production_readiness.md.** The doc is 128 KB / 804 lines and itself acknowledges this in the table of contents. New §4.2.X subsections without new empirical work are scope-creep. New section requires new measurement; otherwise the discipline is honest framing of what is already there.

4. **More draft files in `docs/` parallel to the main docs.** The `production_readiness_4_2_9_draft.md` and `production_readiness_4_2_10_draft.md` pattern (draft alongside merged) is a process bug. If you draft a new subsection, draft it in-place under a `[DRAFT]` heading or in a feature branch; do not ship parallel draft files.

5. **Restoration of intentionally-removed files** without running the canon-audit verification protocol (§3d of `~/.claude/clarethium-internal/PUBLIC_CANON_DISCIPLINE.md`). If a file is missing from a wheel-content declaration, conformance test, or extract include-list, the default reading is "intentional leak-cleanup mid-progress"; the restoration verification protocol applies before restoring.

## Operating notes for the fresh agent

### Local-machine reproducibility
- Install with `pip install clarethium-touchstone` (base library, ~71 KB wheel, no runtime dependencies). Add `[dev]` for the lint/type/test tooling or `[external]` for the benchmark runners. The Touchstone MCP server lives in its own PyPI distribution: `pip install touchstone-mcp`.
- Working-tree development: clone, `pip install -e ".[dev]" && pip install -e ./touchstone-mcp`, then `pytest -q && pytest -q touchstone-mcp/tests`. The library suite plus the MCP suite together exercise the full surface.
- `bash scripts/canon_audit.sh --self-test` runs the audit's own self-test. `bash scripts/canon_audit.sh` runs the audit on the working tree. Cumulative cleanup through v0.2.0 (PRs #1-#10) keeps a clean clone (no `.claude/`) auditing with zero hits: `--exclude-dir=results` and `--exclude-dir=.claude` handle the byte-pinned benchmark snapshots and any local Claude Code artifacts; the benchmark Python scripts and `docs/production_readiness.md` reproduction commands use generic environment-variable loading instructions rather than naming specific proxy URLs or maintainer credential tools.
- Internal benchmarks (`exp_081_discrimination`, `exp_095_grounding`) reproduce exactly from clone via pytest snapshot assertions.
- External benchmarks stream from HuggingFace at runtime; require network. Per-corpus runtimes are recorded in the README (Touchstone CPU 2-3 seconds; MiniCheck CPU 69-100 minutes per 900-1600 pair corpus).

### Public-canon discipline
- `~/.claude/clarethium-internal/PUBLIC_CANON_DISCIPLINE.md` is the load-bearing reference. Read before any commit touching public-facing prose.
- `scripts/canon_audit.sh` is a byte-identical copy of `~/.claude/clarethium-internal/canon_audit.sh`. Drift is a process bug; sync per §5e.
- Pre-commit hooks (`pre-commit install`) run gitleaks + canon audit on staged content.
- CI (`.github/workflows/canon-audit.yml`) runs the audit on every PR + push; zero non-allowlisted hits is the green-build threshold.

### Cited companions
- **Lodestone** (`Clarethium/lodestone`) — methodology canon; first-person practice pair.
- **cma** (`Clarethium/cma`) — executable compound-practice loop.
- **Sealstone** (`Clarethium/sealstone`) — publish-class verification methodology.
- **agent-grounding** (`Clarethium/agent-grounding`, currently not public) — methodology iteration tree applying Touchstone-class measurement discipline to a different problem (agent-trace narrative-vs-tool-log faithfulness). First companion attempt at Direction 4 above. See its own `OPERATOR_NOTES.md` and `docs/HANDOFF.md` for status, caveats, and the converging-on-topics anti-pattern that surfaced during its iteration.

### Frame Check application
Touchstone is the substrate underneath [Frame Check](https://frame.clarethium.com); changes to Layer 6 / Layer 10 / Layer 11 should consider downstream impact on Frame Check before shipping.
