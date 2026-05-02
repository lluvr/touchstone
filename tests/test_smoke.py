"""Smoke tests verifying package structure, exports, and version metadata."""

from __future__ import annotations

import pytest


def test_package_importable() -> None:
    """The package can be imported."""
    import clarethium_touchstone

    assert clarethium_touchstone is not None


def test_public_api_exports() -> None:
    """Top-level public API functions are exported."""
    import clarethium_touchstone

    assert hasattr(clarethium_touchstone, "measure")
    assert hasattr(clarethium_touchstone, "align")
    assert hasattr(clarethium_touchstone, "profile")
    assert hasattr(clarethium_touchstone, "__version__")


def test_version_strings() -> None:
    """Version metadata is well-formed."""
    from clarethium_touchstone._version import __standard_version__, __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0
    assert isinstance(__standard_version__, str)
    assert __standard_version__.startswith("1.0")


def test_measure_layer_functions_present() -> None:
    """All Standard Section 5 layer functions are accessible from measure module.

    Functions are imported by name; if any are missing the import fails. Asserting
    callability confirms each is a function rather than a stale binding.
    """
    from clarethium_touchstone.measure import (
        claim_density,
        entity_provenance,
        epistemic_calibration,
        fabrication_rate,
        grounding_decomposition,
        information_novelty,
        measure,
        presentation_features,
        quality_profile,
        source_matching,
        structural_profile,
        temporal_instability,
        vocabulary_proximity,
    )

    functions = (
        measure,
        structural_profile,
        claim_density,
        temporal_instability,
        fabrication_rate,
        source_matching,
        entity_provenance,
        vocabulary_proximity,
        presentation_features,
        epistemic_calibration,
        information_novelty,
        quality_profile,
        grounding_decomposition,
    )
    assert all(callable(f) for f in functions)


def test_align_layer_functions_present() -> None:
    """All Standard Section 6 layer functions are accessible from align module."""
    from clarethium_touchstone.align import (
        align,
        analyze_spec,
        coverage_mapping,
        emphasis_balance,
        extract_requirements,
        pipeline_check,
        scope_drift,
        semantic_coverage,
    )

    functions = (
        align,
        extract_requirements,
        coverage_mapping,
        scope_drift,
        emphasis_balance,
        semantic_coverage,
        analyze_spec,
        pipeline_check,
    )
    assert all(callable(f) for f in functions)


def test_implementation_pending() -> None:
    """Skeleton functions raise NotImplementedError until extraction completes.

    This test will be flipped to verify behavior once the operator extracts
    the reference implementation from the research vault.
    """
    from clarethium_touchstone import measure

    with pytest.raises(NotImplementedError):
        measure("any text")


def test_types_module_present() -> None:
    """Public type definitions are accessible."""
    from clarethium_touchstone import types

    assert hasattr(types, "MeasureResult")
    assert hasattr(types, "AlignResult")
    assert hasattr(types, "GroundingDecomposition")
    assert hasattr(types, "Requirement")
    assert hasattr(types, "RequirementType")
    assert hasattr(types, "GFPCategory")
