"""Tests for the four Touchstone MCP tools.

``touchstone-mcp`` declares ``clarethium-touchstone`` and ``fastmcp``
as hard runtime dependencies, so this test module imports them
unconditionally. Install the package with the ``test`` extra to run
the suite::

    pip install -e ".[test]"
"""

from __future__ import annotations

import pytest
from fastmcp import FastMCP

from touchstone_mcp import build_server

# All tests are async; pytest-asyncio's auto mode picks them up.
pytestmark = pytest.mark.asyncio


SUPPORTED_TEXT = (
    "Apple reported Q1 fiscal 2026 revenue of $143 billion. The iPhone "
    "segment grew 8% year-over-year. Tim Cook commented on AI investments "
    "during the earnings call. Operating margins reached 32%."
)
SUPPORTED_SOURCE = SUPPORTED_TEXT

HALLUCINATED_TEXT = (
    "Apple reported Q1 fiscal 2026 revenue of $185 billion, the company's "
    "highest ever. McKinsey forecasts industry-wide growth of 47% next "
    "quarter. The Federal Reserve will raise rates 75 basis points in "
    "response. Tesla announced a competing AR product for late 2027."
)
HALLUCINATED_SOURCE = SUPPORTED_TEXT


@pytest.fixture
def server() -> FastMCP:
    """A fresh FastMCP instance with all four MCP tools registered."""
    return build_server()


# -- Tool registration --------------------------------------------------------


async def test_server_registers_all_four_tools(server: FastMCP) -> None:
    """The server registers exactly the four documented tools."""
    tools = await server.list_tools()
    names = sorted(t.name for t in tools)
    assert names == sorted(["verify", "measure", "assess_derivation_regime", "list_modes"])


async def test_server_has_name_and_instructions(server: FastMCP) -> None:
    """Server identity is set so MCP hosts can render it."""
    assert server.name == "touchstone"
    assert server.instructions
    assert "Touchstone" in server.instructions


async def test_tool_descriptions_non_empty(server: FastMCP) -> None:
    """Every tool ships a non-empty description (driven by docstrings)."""
    tools = await server.list_tools()
    for tool in tools:
        assert tool.description, f"tool {tool.name!r} has no description"
        assert len(tool.description) > 50, (
            f"tool {tool.name!r} description too short: {tool.description!r}"
        )


# -- verify tool --------------------------------------------------------------


async def test_verify_faithful_pair_low_prob(server: FastMCP) -> None:
    """A self-source faithful input scores low."""
    result = await server.call_tool(
        "verify",
        {"text": SUPPORTED_TEXT, "source": SUPPORTED_SOURCE},
    )
    out = result.structured_content
    assert out["scope"] == "validated"
    assert out["prob_hallucinated"] < 0.5
    assert out["mode"] == "substrate_only"


async def test_verify_hallucinated_pair_high_prob(server: FastMCP) -> None:
    """An adversarial hallucinated input scores above 0.5."""
    result = await server.call_tool(
        "verify",
        {"text": HALLUCINATED_TEXT, "source": HALLUCINATED_SOURCE},
    )
    out = result.structured_content
    assert out["scope"] == "validated"
    assert out["prob_hallucinated"] > 0.5
    assert len(out["top_unsupported"]) > 0


async def test_verify_returns_required_shape(server: FastMCP) -> None:
    """Verify returns every documented field."""
    result = await server.call_tool(
        "verify",
        {"text": HALLUCINATED_TEXT, "source": HALLUCINATED_SOURCE},
    )
    out = result.structured_content
    assert set(out.keys()) >= {
        "prob_hallucinated",
        "mode",
        "scope",
        "scope_notes",
        "signal_breakdown",
        "top_unsupported",
    }
    assert isinstance(out["prob_hallucinated"], float)
    assert 0.0 <= out["prob_hallucinated"] <= 1.0
    assert isinstance(out["scope_notes"], list)
    assert isinstance(out["signal_breakdown"], dict)
    assert isinstance(out["top_unsupported"], list)


async def test_verify_empty_text_classified_insufficient_input(server: FastMCP) -> None:
    """Empty text returns scope=insufficient_input."""
    result = await server.call_tool(
        "verify",
        {"text": "", "source": "Some real source text with substance."},
    )
    out = result.structured_content
    assert out["scope"] == "insufficient_input"


async def test_verify_short_self_reference_not_validated(server: FastMCP) -> None:
    """A trivially short self-referential input is not validated scope."""
    text = "Revenue grew 12%."
    result = await server.call_tool("verify", {"text": text, "source": text})
    out = result.structured_content
    assert out["scope"] != "validated"
    assert out["prob_hallucinated"] < 0.3


async def test_verify_top_k_caps_output(server: FastMCP) -> None:
    """top_k_unsupported caps the returned span count."""
    result = await server.call_tool(
        "verify",
        {
            "text": HALLUCINATED_TEXT,
            "source": HALLUCINATED_SOURCE,
            "top_k_unsupported": 1,
        },
    )
    out = result.structured_content
    assert len(out["top_unsupported"]) <= 1


async def test_verify_substrate_plus_judge_mode_auto_selects(server: FastMCP) -> None:
    """Passing judge_hallucinated_prob switches mode."""
    result = await server.call_tool(
        "verify",
        {
            "text": HALLUCINATED_TEXT,
            "source": HALLUCINATED_SOURCE,
            "judge_hallucinated_prob": 0.9,
            "judge_alpha": 0.3,
        },
    )
    out = result.structured_content
    assert out["mode"] == "substrate_plus_judge"
    assert "substrate_prob" in out["signal_breakdown"]
    assert "judge_hallucinated_prob" in out["signal_breakdown"]


# -- measure tool -------------------------------------------------------------


async def test_measure_returns_all_layers(server: FastMCP) -> None:
    """measure returns every layer key."""
    result = await server.call_tool("measure", {"text": SUPPORTED_TEXT, "source": SUPPORTED_SOURCE})
    out = result.structured_content
    expected_layers = {
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
    }
    assert set(out.keys()) >= expected_layers


async def test_measure_no_source_omits_source_dependent_layers(server: FastMCP) -> None:
    """When source is omitted, source-dependent layers return None."""
    result = await server.call_tool(
        "measure",
        {"text": "Revenue grew 12% to $143M with 25% margins."},
    )
    out = result.structured_content
    # Layers 4, 5, 6, 11 require source.
    assert out["source_matching"] is None
    assert out["entity_provenance"] is None
    assert out["vocabulary_proximity"] is None
    assert out["grounding_decomposition"] is None
    # Layer 7 (presentation) does not require source and should fire.
    assert out["presentation_features"] is not None


# -- assess_derivation_regime tool -------------------------------------------


async def test_assess_derivation_regime_saturated_at_high_n(server: FastMCP) -> None:
    """Source with >= 10 numbers classifies as saturated."""
    result = await server.call_tool("assess_derivation_regime", {"source_num_count": 14})
    out = result.structured_content
    assert out["derivation_regime"] == "saturated"
    assert out["cross_reference_layer_4_for_numbers"] is True


async def test_assess_derivation_regime_diagnostic_at_low_n(server: FastMCP) -> None:
    """Source with < 5 numbers classifies as diagnostic."""
    result = await server.call_tool("assess_derivation_regime", {"source_num_count": 2})
    out = result.structured_content
    assert out["derivation_regime"] == "diagnostic"


# -- list_modes tool ----------------------------------------------------------


async def test_list_modes_returns_four_modes(server: FastMCP) -> None:
    """list_modes enumerates the four canonical mode strings."""
    result = await server.call_tool("list_modes", {})
    out = result.structured_content
    names = [m["name"] for m in out["modes"]]
    assert names == [
        "substrate_only",
        "substrate_plus_minicheck",
        "substrate_plus_minicheck_alignscore",
        "substrate_plus_judge",
    ]


async def test_list_modes_returns_versions(server: FastMCP) -> None:
    """list_modes returns library + Standard versions."""
    result = await server.call_tool("list_modes", {})
    out = result.structured_content
    assert "versions" in out
    versions = out["versions"]
    assert versions["touchstone_library"]
    assert versions["touchstone_standard"]


async def test_list_modes_per_mode_required_inputs(server: FastMCP) -> None:
    """Each mode metadata names its required input parameters."""
    result = await server.call_tool("list_modes", {})
    out = result.structured_content
    expected_requires = {
        "substrate_only": [],
        "substrate_plus_minicheck": ["minicheck_supported_prob"],
        "substrate_plus_minicheck_alignscore": [
            "minicheck_supported_prob",
            "alignscore_supported_prob",
        ],
        "substrate_plus_judge": ["judge_hallucinated_prob"],
    }
    for mode in out["modes"]:
        assert mode["requires"] == expected_requires[mode["name"]]
