# Examples

End-to-end usage examples for the `clarethium-touchstone` library. Each example is a standalone script that runs against `clarethium_touchstone` installed from the repo (`pip install -e .`).

## Available examples

| File | What it shows | Source data |
|------|----------------|-------------|
| `verify_a_summary.py` | Profile a short analytical summary against the source it was derived from. Reports Layer 4 (source matching), Layer 10 (quality_profile.gap), and Layer 11 (G/F/P decomposition). Demonstrates the typical adopter call shape, the precision indicators, and how to interpret a low-N scope_assessment. | Inline sample text |
| `production_verifier.py` | End-to-end `Verifier` demo across substrate-only and substrate+baseline modes; shows calibrated probabilities, signal breakdowns, and span-level localization. | Inline sample text |
| `batch_triage.py` | Batch-score a corpus, sort by `prob_hallucinated`, surface the top-K for human review, and route `limited_signal` / `insufficient_input` results to manual review separately from the auto-flag queue. Production triage pattern. | Inline 8-row corpus |
| `calibrate_on_holdout.py` | Re-fit the Verifier's logistic regression on your own labeled holdout data using a stdlib-only gradient-descent loop. Demonstrates that the shipped RAGTruth-Summary calibration is not optimal on adversarial-fabrication corpora, and shows the recalibration recipe. | Inline 12-row holdout |
| `two_stage_cascade.py` | Substrate cheap-screen + LLM judge on the uncertain band. Production-shape cost optimisation: skip the expensive judge on auto-accept and auto-flag rows, call it only on the ambiguous middle band. Judge is stubbed deterministically so the example runs offline; replace `simulated_judge_call()` with your real LLM client. | Inline 8-row corpus |

## Running

From the repository root, inside an activated virtual environment:

```bash
pip install -e .
python examples/verify_a_summary.py
```

Each example prints its output and exits with status 0 on success.

## Adding examples

New examples are welcome via the Suggestion process. An example SHOULD:

- Be a single Python file, runnable directly.
- Import only from `clarethium_touchstone` and the standard library.
- Print enough structured output that the user can see what each layer returned.
- Document its own caveats inline (which layers are informative on its inputs, which are not).

Examples are not part of the conformance surface (§11). They are documentation in code.
