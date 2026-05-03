"""Smoke tests verifying package structure, exports, and version metadata."""

from __future__ import annotations


def test_package_importable() -> None:
    """The package can be imported."""
    import clarethium_touchstone

    assert clarethium_touchstone is not None


def test_public_api_exports() -> None:
    """Top-level public API functions are exported (v0.1: measurement only)."""
    import clarethium_touchstone

    assert hasattr(clarethium_touchstone, "measure")
    assert hasattr(clarethium_touchstone, "__version__")


def test_align_and_profile_not_exported_in_v0_1() -> None:
    """``align`` and ``profile`` are NOT part of the v0.1 public API.

    Standard Section 6 (Specification Compliance) is reserved for a
    future release. The pre-port stubs raised NotImplementedError; the
    cleanup removes the API surface entirely so first-contact callers
    see a clean ImportError rather than a misleading runtime crash.
    """
    import clarethium_touchstone

    assert not hasattr(clarethium_touchstone, "align")
    assert not hasattr(clarethium_touchstone, "profile")


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


def test_align_module_does_not_exist_in_v0_1() -> None:
    """The ``clarethium_touchstone.align`` module is not part of v0.1.

    Importing it raises ModuleNotFoundError (the file is absent).
    """
    import pytest

    with pytest.raises(ModuleNotFoundError):
        import clarethium_touchstone.align  # noqa: F401


def test_orchestrator_returns_measure_result_without_source() -> None:
    """``measure()`` runs successfully on text alone. Source-dependent
    layer keys carry None; text-only layers populate.
    """
    from clarethium_touchstone import measure

    result = measure("Some text without enough numbers here today.")
    # Always-available layers
    assert result["structural_profile"] is not None
    assert result["claim_density"] is not None
    assert result["presentation_features"] is not None
    assert result["information_novelty"] is not None
    assert result["quality_profile"] is not None
    # Source-dependent layers: None when no source
    assert result["source_matching"] is None
    assert result["entity_provenance"] is None
    assert result["vocabulary_proximity"] is None
    assert result["epistemic_calibration"] is None
    assert result["grounding_decomposition"] is None
    # Comparisons-dependent: None when no comparisons
    assert result["temporal_instability"] is None
    # Version metadata always present
    assert "standard_version" in result
    assert "library_version" in result


def test_orchestrator_runs_all_layers_with_source_and_comparisons() -> None:
    """With both ``source`` and ``comparisons``, every layer key holds a
    non-None result.
    """
    from clarethium_touchstone import measure

    text = "Revenue grew 12% to $143M with 25% margins reported here today."
    result = measure(text, source=text, comparisons=[text])
    # Every layer key is non-None
    layer_keys = [
        "structural_profile",
        "claim_density",
        "temporal_instability",
        "source_matching",
        "entity_provenance",
        "vocabulary_proximity",
        "presentation_features",
        "epistemic_calibration",
        "information_novelty",
        "quality_profile",
        "grounding_decomposition",
    ]
    for key in layer_keys:
        assert result[key] is not None, f"{key} should be populated"


def test_orchestrator_threads_baseline_generator_to_layer_1a() -> None:
    """``measure(..., topic=..., baseline_generator=...)`` runs Layer 1a;
    the heading_defaultness sub-dict is populated rather than None.
    """
    from clarethium_touchstone import measure

    def stub_gen(_prompt: str) -> str | None:
        return "## My Topic\n## Another Section\nBaseline body."

    result = measure(
        "## My Topic\nDoc body content here today.",
        topic="my topic",
        baseline_generator=stub_gen,
        n_baselines=2,
    )
    hd = result["structural_profile"]["heading_defaultness"]
    assert hd is not None
    assert hd["n_baseline_documents"] == 2


def test_orchestrator_layer_1a_inert_without_generator() -> None:
    """Without a ``baseline_generator``, Layer 1a stays inert even if a
    topic is supplied — heading_defaultness is None.
    """
    from clarethium_touchstone import measure

    result = measure(
        "## My Section\nContent.",
        topic="some topic",
    )
    assert result["structural_profile"]["heading_defaultness"] is None


def test_types_module_present() -> None:
    """Public type definitions are accessible (v0.1: measurement types only)."""
    from clarethium_touchstone import types

    assert hasattr(types, "MeasureResult")
    assert hasattr(types, "GroundingDecomposition")
    assert hasattr(types, "GFPCategory")
    # Section 6 alignment types are not in v0.1
    assert not hasattr(types, "AlignResult")
    assert not hasattr(types, "Requirement")
    assert not hasattr(types, "RequirementType")
