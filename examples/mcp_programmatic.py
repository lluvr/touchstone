"""Programmatic invocation of the Touchstone MCP server's tools.

Demonstrates calling each of the four tools without going through a
remote MCP host. Useful for verifying the server works locally and as
a starting point for embedding the server in a custom transport.

Run from the repository root::

    pip install -e ".[mcp]"
    python examples/mcp_programmatic.py
"""

from __future__ import annotations

import asyncio

from clarethium_touchstone.mcp import build_server


async def main() -> None:
    server = build_server()

    tools = await server.list_tools()
    print(f"Server: {server.name}")
    print(f"Tools registered: {[t.name for t in tools]}")
    print()

    # 1. list_modes
    print("=== list_modes ===")
    res = await server.call_tool("list_modes", {})
    out = res.structured_content
    for mode in out["modes"]:
        print(f"  {mode['name']:<40s} requires={mode['requires']}")
    print(f"  versions: {out['versions']}")
    print()

    # 2. assess_derivation_regime
    print("=== assess_derivation_regime(source_num_count=14) ===")
    res = await server.call_tool("assess_derivation_regime", {"source_num_count": 14})
    out = res.structured_content
    print(f"  regime: {out['derivation_regime']}")
    print(f"  cross-reference L4 for numbers: {out['cross_reference_layer_4_for_numbers']}")
    print()

    # 3. verify — faithful case
    print("=== verify (faithful self-source) ===")
    res = await server.call_tool(
        "verify",
        {
            "text": (
                "Apple reported Q1 fiscal 2026 revenue of $143 billion. "
                "The iPhone segment grew 8% year-over-year. "
                "Tim Cook commented on AI investments during the earnings call."
            ),
            "source": (
                "Apple reported Q1 fiscal 2026 revenue of $143 billion. "
                "The iPhone segment grew 8% year-over-year. "
                "Tim Cook commented on AI investments during the earnings call."
            ),
        },
    )
    out = res.structured_content
    print(f"  prob_hallucinated: {out['prob_hallucinated']:.3f}")
    print(f"  scope: {out['scope']}")
    print(f"  spans: {len(out['top_unsupported'])}")
    print()

    # 4. verify — hallucinated case
    print("=== verify (hallucinated) ===")
    res = await server.call_tool(
        "verify",
        {
            "text": (
                "Apple reported Q1 fiscal 2026 revenue of $185 billion, the company's "
                "highest ever. McKinsey forecasts industry-wide growth of 47% next "
                "quarter. The Federal Reserve will raise rates 75 basis points in "
                "response. Tesla announced a competing AR product for late 2027."
            ),
            "source": (
                "Apple reported Q1 fiscal 2026 revenue of $143 billion. "
                "The iPhone segment grew 8% year-over-year. "
                "Tim Cook commented on AI investments during the earnings call. "
                "Operating margins reached 32%."
            ),
        },
    )
    out = res.structured_content
    print(f"  prob_hallucinated: {out['prob_hallucinated']:.3f}")
    print(f"  scope: {out['scope']}")
    for span in out["top_unsupported"]:
        print(f"  [{span['layer11_primary']}] {span['sentence']!r}")
        print(f"      markers={span['p_markers']}")


if __name__ == "__main__":
    asyncio.run(main())
