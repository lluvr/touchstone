"""Touchstone MCP server (Model Context Protocol).

Exposes :class:`clarethium_touchstone.Verifier` and the lower-level
:func:`clarethium_touchstone.measure` orchestrator as MCP tools, so any
MCP host (Claude Desktop, Claude Code, Cursor, custom) can invoke
Touchstone's calibrated verifier in-context.

Install with the ``mcp`` extra::

    pip install "clarethium-touchstone[mcp]"

The ``touchstone-mcp`` console script is then registered and runs on
stdio transport by default, matching the convention every MCP host
expects for local servers.

Programmatic use::

    from clarethium_touchstone.mcp import build_server

    server = build_server()
    server.run()                 # stdio transport

The four tools exposed:

* ``verify`` — calibrated ``(text, source)`` hallucination probability,
  scope classification, signal breakdown, and span-level localization.
* ``measure`` — raw multi-layer Touchstone output (all eleven Section 5
  measurement layers).
* ``assess_derivation_regime`` — Layer 11 standalone regime classifier.
* ``list_modes`` — enumerate the four Verifier modes with their
  required inputs and the library + Standard versions in use.

Importing this module requires :mod:`fastmcp`. The base
``clarethium-touchstone`` install does not pull in ``fastmcp``; install
the ``mcp`` extra above to enable the server.
"""

from __future__ import annotations

try:
    from clarethium_touchstone.mcp.server import build_server, main
except ImportError as exc:  # pragma: no cover - dependency-presence guard
    raise ImportError(
        "clarethium_touchstone.mcp requires the 'mcp' extra. "
        "Install via: pip install 'clarethium-touchstone[mcp]'"
    ) from exc

__all__ = ["build_server", "main"]
