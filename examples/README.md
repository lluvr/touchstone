# Examples

End-to-end usage examples for the `clarethium-touchstone` library. Each example is a standalone script that runs against `clarethium_touchstone` installed from the repo (`pip install -e .`).

## Available examples

| File | What it shows | Source data |
|------|----------------|-------------|
| `verify_a_summary.py` | Profile a short analytical summary against the source it was derived from. Reports Layer 4 (source matching), Layer 10 (quality_profile.gap), and Layer 11 (G/F/P decomposition). Demonstrates the typical adopter call shape, the precision indicators, and how to interpret a low-N scope_assessment. | Inline sample text |

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
