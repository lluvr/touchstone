"""Reference-suite runner.

Loads every JSON case in ``tests/reference/cases/`` and executes
``clarethium_touchstone.measure()`` against it, comparing the result
to the case's ``expected`` block within a per-case tolerance. This
file is pytest-discoverable so the cases run as part of the regular
test suite.

Each case file is a JSON document with this shape::

    {
        "id": "L4_001_basic_self_source",
        "description": "Layer 4: every digit-formatted number is sourced.",
        "standard_section": "5.4",
        "inputs": {
            "text": "...",
            "source": "...",
            "comparisons": ["...", "..."],
            "topic": "..."
        },
        "expected": {
            "source_matching": {
                "unsourced_rate": 0.0,
                "n_total": 2
            }
        },
        "tolerance": {"absolute": 0.0001}
    }

Only the keys in ``expected`` are checked. Other layer keys in the
``MeasureResult`` are allowed to vary. Scalar floats are compared with
absolute tolerance ``tolerance.absolute`` (default ``1e-4``); integers
and booleans must match exactly; strings must match exactly; lists
and dicts are compared element-wise with the same rules. ``None``
values must match exactly.

The case format is intentionally minimal so adopter implementations
in other languages can produce identical JSON outputs and pass the
same cases without depending on Python-specific data shapes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from clarethium_touchstone import measure

CASES_DIR = Path(__file__).parent / "cases"


def _discover_cases() -> list[tuple[str, dict[str, Any]]]:
    if not CASES_DIR.exists():
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(CASES_DIR.glob("*.json")):
        case = json.loads(path.read_text())
        out.append((case["id"], case))
    return out


def _compare(actual: Any, expected: Any, path: str, tolerance: float) -> list[str]:
    """Recursive structural comparison. Returns a list of failure strings."""
    failures: list[str] = []

    if expected is None:
        if actual is not None:
            failures.append(f"{path}: expected None, got {actual!r}")
        return failures

    if isinstance(expected, bool):
        if not isinstance(actual, bool) or actual != expected:
            failures.append(f"{path}: expected bool {expected!r}, got {actual!r}")
        return failures

    if isinstance(expected, int):
        # bool is a subclass of int; handled above first.
        if not isinstance(actual, int) or actual != expected:
            failures.append(f"{path}: expected int {expected}, got {actual!r}")
        return failures

    if isinstance(expected, float):
        if actual is None or isinstance(actual, bool):
            failures.append(f"{path}: expected float {expected}, got {actual!r}")
            return failures
        try:
            actual_f = float(actual)
        except (TypeError, ValueError):
            failures.append(f"{path}: expected float {expected}, got {actual!r}")
            return failures
        if abs(actual_f - expected) > tolerance:
            failures.append(
                f"{path}: expected {expected} ± {tolerance}, got {actual_f} "
                f"(delta={abs(actual_f - expected):.6f})"
            )
        return failures

    if isinstance(expected, str):
        if actual != expected:
            failures.append(f"{path}: expected {expected!r}, got {actual!r}")
        return failures

    if isinstance(expected, list):
        if not isinstance(actual, list):
            failures.append(f"{path}: expected list, got {type(actual).__name__}")
            return failures
        if len(actual) != len(expected):
            failures.append(f"{path}: expected list of length {len(expected)}, got {len(actual)}")
            return failures
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            failures.extend(_compare(a, e, f"{path}[{i}]", tolerance))
        return failures

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            failures.append(f"{path}: expected dict, got {type(actual).__name__}")
            return failures
        for k, v in expected.items():
            if k not in actual:
                failures.append(f"{path}.{k}: expected key missing from actual")
                continue
            failures.extend(_compare(actual[k], v, f"{path}.{k}", tolerance))
        return failures

    failures.append(f"{path}: unsupported expected type {type(expected).__name__}")
    return failures


@pytest.mark.parametrize(
    "case_id,case", _discover_cases(), ids=lambda c: c if isinstance(c, str) else ""
)
def test_reference_case(case_id: str, case: dict[str, Any]) -> None:
    """Run a single reference case end-to-end through ``measure()``.

    Reads inputs from the case, executes Touchstone, and verifies that
    the layer outputs named in ``expected`` match within the case's
    declared tolerance. Layer keys not in ``expected`` are not checked.
    """
    inputs = case["inputs"]
    tolerance = float(case.get("tolerance", {}).get("absolute", 1e-4))

    kwargs: dict[str, Any] = {}
    if "source" in inputs:
        kwargs["source"] = inputs["source"]
    if "comparisons" in inputs:
        kwargs["comparisons"] = inputs["comparisons"]
    if "topic" in inputs:
        kwargs["topic"] = inputs["topic"]

    result = measure(inputs["text"], **kwargs)

    failures = _compare(result, case["expected"], "", tolerance)
    if failures:
        details = "\n".join(f"  - {f}" for f in failures)
        msg = (
            f"Reference case {case_id} failed:\n{details}\n"
            f"Case description: {case.get('description', '(no description)')}"
        )
        pytest.fail(msg)
