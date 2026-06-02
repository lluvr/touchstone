"""Touchstone MCP server: a deterministic first-pass filter for unsupported
claims in LLM output, computed without a second model call (not a standalone
hallucination detector), exposed as Model Context Protocol tools.

Install with::

    pip install touchstone-mcp

The ``touchstone-mcp`` console script is registered automatically and
runs on the stdio transport by default, matching the convention every
MCP host (Claude Desktop, Claude Code, Cursor, custom) expects for
local servers.

Programmatic use::

    from touchstone_mcp import build_server

    server = build_server()
    server.run()                 # stdio transport

The four tools exposed:

* ``verify`` -- calibrated production Verifier. Returns probability,
  scope, signal breakdown, and span-level localization for a
  ``(text, source)`` pair. Use this for the common "is this output
  faithful to its source" decision.
* ``measure`` -- low-level orchestrator that runs every Touchstone
  Section 5 measurement layer whose preconditions are met. Use this
  when the caller needs the raw layer outputs for drill-down.
* ``assess_derivation_regime`` -- Layer 11 standalone regime classifier.
  Useful for surfacing a "trust this signal" hint before any
  measurement runs.
* ``list_modes`` -- enumerate the four Verifier modes and their
  preconditions. Helpful for hosts that present a mode selector.

The server uses FastMCP's decorator API. Type hints on the tool
functions drive the MCP schema; docstrings drive the tool descriptions
exposed to the host. Measurement semantics and calibration coefficients
are defined and tested in ``clarethium_touchstone`` (the bundled
reference implementation); this module is a thin wrapper around its
public surface.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any

from fastmcp import FastMCP

from clarethium_touchstone import (
    VERIFIER_MODES,
    Verifier,
)
from clarethium_touchstone import (
    assess_derivation_regime as _assess_derivation_regime,
)
from clarethium_touchstone import (
    measure as _measure,
)
from clarethium_touchstone._version import (
    __standard_version__,
)
from clarethium_touchstone._version import (
    __version__ as _touchstone_lib_version,
)

try:
    __version__ = _pkg_version("touchstone-mcp")
except PackageNotFoundError:  # source checkout without an installed dist
    __version__ = "0.0.0+source"

# Module-level Verifier so the calibration coefficients load once and
# repeated calls reuse them. The Verifier is stateless across calls;
# each `score()` produces an independent result.
_VERIFIER = Verifier()


def build_server() -> FastMCP:
    """Construct the Touchstone MCP server.

    Returns a configured :class:`fastmcp.FastMCP` instance with four
    tools registered. The instance is not started; the caller invokes
    ``server.run()`` (stdio by default) or attaches it to a custom
    transport.
    """
    mcp = FastMCP(
        name="touchstone",
        version=__version__,
        instructions=(
            "Touchstone: a deterministic first-pass filter for unsupported "
            "claims in LLM output, computed without a second model call (not "
            "a standalone hallucination detector). Call `verify` to score a "
            "(text, source) pair for hallucination probability with span-level "
            "localization. Call `measure` for the raw multi-layer output. Read "
            "scope and scope_notes on every verify result before acting on the "
            "probability."
        ),
    )

    @mcp.tool()
    def verify(
        text: str,
        source: str,
        minicheck_supported_prob: float | None = None,
        alignscore_supported_prob: float | None = None,
        judge_hallucinated_prob: float | None = None,
        judge_alpha: float = 0.3,
        top_k_unsupported: int = 3,
    ) -> dict[str, Any]:
        """Score a (text, source) pair for hallucination probability.

        Returns the calibrated probability that ``text`` contains
        unsupported claims relative to ``source``, along with the
        signal breakdown, scope classification, and the top suspect
        sentences with their Layer 11 markers.

        Args:
            text: The AI-generated output to verify.
            source: The grounding source the output should be supported
                by.
            minicheck_supported_prob: Optional MiniCheck supported-
                probability in [0, 1]. When supplied, the verifier
                auto-selects ``substrate_plus_minicheck`` mode.
            alignscore_supported_prob: Optional AlignScore supported-
                probability in [0, 1]. Combine with MiniCheck for
                ``substrate_plus_minicheck_alignscore`` mode.
            judge_hallucinated_prob: Optional LLM-judge probability of
                hallucination in [0, 1]. Auto-selects
                ``substrate_plus_judge`` mode. Mutually exclusive with
                the MiniCheck / AlignScore parameters in the same call.
            judge_alpha: Substrate weight in the substrate+judge blend.
                Defaults to 0.3 (a substrate-light default; the picked
                α in the published holdout-blend table is corpus-
                dependent). Tune on held-out data.
            top_k_unsupported: Maximum number of suspect spans to
                return. Defaults to 3.

        Returns:
            A dict with keys ``prob_hallucinated`` (float in [0, 1]),
            ``mode`` (which calibration mode produced the score),
            ``scope`` (``"validated"`` / ``"limited_signal"`` /
            ``"insufficient_input"`` -- see scope_notes for the
            classification reason), ``scope_notes`` (list of
            diagnostic strings), ``signal_breakdown`` (per-feature
            logit contributions), and ``top_unsupported`` (list of
            sentence-level dicts with ``sentence``, ``sentence_index``,
            ``layer11_primary``, ``p_markers``, ``grounding_score``).

        Threshold guidance: the default decision threshold of 0.5
        under-flags on every published external corpus. F1-optimal
        thresholds in the empirical-validation tables are 0.07-0.27.
        Tune on your held-out data before any production deployment.
        """
        result = _VERIFIER.score(
            text=text,
            source=source,
            minicheck_supported_prob=minicheck_supported_prob,
            alignscore_supported_prob=alignscore_supported_prob,
            judge_hallucinated_prob=judge_hallucinated_prob,
            judge_alpha=judge_alpha,
            top_k_unsupported=top_k_unsupported,
        )
        return {
            "prob_hallucinated": result.prob_hallucinated,
            "mode": result.mode,
            "scope": result.scope,
            "scope_notes": list(result.scope_notes),
            "signal_breakdown": dict(result.signal_breakdown),
            "top_unsupported": [
                {
                    "sentence": span.sentence,
                    "sentence_index": span.sentence_index,
                    "layer11_primary": span.layer11_primary,
                    "p_markers": list(span.p_markers),
                    "grounding_score": span.grounding_score,
                }
                for span in result.top_unsupported
            ],
        }

    @mcp.tool()
    def measure(
        text: str,
        source: str | None = None,
        topic: str | None = None,
        comparisons: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run every Touchstone measurement layer whose preconditions
        are met.

        This is the lower-level companion to ``verify``. Returns the
        full ``MeasureResult`` keyed by layer name; source-dependent
        layers (4, 5, 6, 8, 11) return ``None`` when ``source`` is
        absent.

        Args:
            text: The AI-generated output to measure.
            source: Optional grounding source. Required for Layers 4,
                5, 6, 8, and 11.
            topic: Optional topic string for Layer 1a (heading
                defaultness). Layer 1a additionally requires a caller-
                supplied baseline-generator callable, which the MCP
                tool does not currently expose; passing ``topic``
                without a baseline generator produces a Layer 1a
                output of ``None``.
            comparisons: Optional list of other independently-generated
                versions of the output for Layer 3 (temporal
                instability).

        Returns:
            The full MeasureResult dict keyed by layer name:
            ``structural_profile``, ``claim_density``,
            ``temporal_instability``, ``source_matching``,
            ``entity_provenance``, ``vocabulary_proximity``,
            ``presentation_features``, ``epistemic_calibration``,
            ``information_novelty``, ``quality_profile``,
            ``grounding_decomposition``.
        """
        return dict(_measure(text, source=source, topic=topic, comparisons=comparisons))

    @mcp.tool()
    def assess_derivation_regime(source_num_count: int) -> dict[str, Any]:
        """Classify the reliability of Layer 11's derivation checker
        for a given source.

        Layer 11's primary unsourced-numbers signal saturates as the
        source's unique-number count grows. This tool returns the
        regime classification (``"diagnostic"`` for source_num_count
        < 5, ``"transition"`` for [5, 10), ``"saturated"`` for >= 10)
        and the user-facing guidance text.

        Use this before running ``measure`` or ``verify`` to surface
        a "trust this signal" hint to the user. On saturated sources,
        the result's guidance string directs callers to Layer 4
        source matching for numerical fabrication detection rather
        than to Layer 11.

        Args:
            source_num_count: Count of digit-formatted numbers in the
                source text.

        Returns:
            A dict with ``derivation_regime``, ``source_num_count``,
            ``cross_reference_layer_4_for_numbers``,
            ``note_user_facing``, and other regime metadata.
        """
        return dict(_assess_derivation_regime(source_num_count=source_num_count))

    @mcp.tool()
    def list_modes() -> dict[str, Any]:
        """Enumerate the four Verifier modes and their required inputs.

        Returns a dict with the mode list and per-mode metadata so the
        host can present a mode selector to the user without
        re-deriving the mode-selection rules.

        Returns:
            A dict with ``modes`` (list of mode metadata dicts) and
            ``versions`` (clarethium_touchstone library version,
            Touchstone Standard version, MCP server version).
        """
        modes: list[dict[str, Any]] = [
            {
                "name": "substrate_only",
                "requires": [],
                "description": (
                    "Default. No external dependencies. Sub-100 ms per "
                    "5 KB document. AUC ~ 0.67-0.76 on the three external "
                    "summarization corpora."
                ),
            },
            {
                "name": "substrate_plus_minicheck",
                "requires": ["minicheck_supported_prob"],
                "description": (
                    "Add the MiniCheck Flan-T5-Large supported-probability. AUC ~ 0.76."
                ),
            },
            {
                "name": "substrate_plus_minicheck_alignscore",
                "requires": [
                    "minicheck_supported_prob",
                    "alignscore_supported_prob",
                ],
                "description": ("Add both LLM-based baselines. AUC ~ 0.77."),
            },
            {
                "name": "substrate_plus_judge",
                "requires": ["judge_hallucinated_prob"],
                "description": (
                    "Linear-blend the substrate probability with a frontier "
                    "LLM judge probability. AUC ranges 0.78-0.94 on the "
                    "published corpora depending on judge vendor and "
                    "cued/blind variant. Mutually exclusive with MiniCheck "
                    "/ AlignScore in the same call."
                ),
            },
        ]
        assert tuple(m["name"] for m in modes) == VERIFIER_MODES, (
            "mode metadata drifted from VERIFIER_MODES"
        )
        return {
            "modes": modes,
            "versions": {
                "touchstone_library": _touchstone_lib_version,
                "touchstone_standard": __standard_version__,
                "touchstone_mcp_server": __version__,
            },
        }

    return mcp


def main() -> None:
    """Entry point for the ``touchstone-mcp`` console script.

    Runs the server on the default stdio transport, which is the
    transport every MCP host (Claude Desktop, Claude Code, Cursor)
    expects for local servers.
    """
    server = build_server()
    server.run()


if __name__ == "__main__":
    main()
