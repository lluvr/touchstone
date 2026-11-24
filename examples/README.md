# Examples

End-to-end usage examples for the `clarethium_touchstone` library. Each example is a standalone script that runs against `clarethium_touchstone` installed from the repo (`pip install -e .`).

## Available examples

| File | What it shows | Source data |
|------|----------------|-------------|
| `verify_a_summary.py` | Profile a short analytical summary against the source it was derived from. Reports Layer 4 (source matching), Layer 10 (quality_profile.gap), and Layer 11 (G/F/P decomposition). Demonstrates the typical adopter call shape, the precision indicators, and how to interpret a low-N scope_assessment. | Inline sample text |
| `production_verifier.py` | End-to-end `Verifier` demo across substrate-only and substrate+baseline modes; shows calibrated probabilities, signal breakdowns, and span-level localization. | Inline sample text |
| `batch_triage.py` | Batch-score a corpus and sort by `prob_hallucinated` for a review queue. `validated` means the lexical features fired. The default `should_flag(0.5)` under-flags. | Inline 8-row corpus |
| `calibrate_on_holdout.py` | Re-fit the Verifier's logistic regression on your own labeled holdout data using a stdlib-only gradient-descent loop. Demonstrates that the shipped RAGTruth-Summary calibration is not optimal on adversarial-fabrication corpora, and shows the recalibration recipe. | Inline 12-row holdout |
| `two_stage_cascade.py` | Earlier cascade demo. The holdout does not support shipping it: blending this score onto a judge was parity or worse on 5 of 6 Grok cells. The judge in the script is a stub. | Inline 8-row corpus |
| `mcp_programmatic.py` | Programmatic invocation of the Touchstone MCP server's four tools (`verify`, `measure`, `assess_derivation_regime`, `list_modes`). Requires the `touchstone-mcp` package (`pip install touchstone-mcp` or `pip install -e .` from the repo). Useful for verifying the server works locally and as a starting point for embedding it in a custom transport. | Inline fixtures |

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
