# touchstone-mcp

Model Context Protocol server for [Touchstone](https://github.com/Clarethium/touchstone): hallucination detection for LLM outputs without calling another LLM.

`touchstone-mcp` exposes the calibrated `Verifier` and the raw measurement orchestrator from the [`clarethium-touchstone`](https://pypi.org/project/clarethium-touchstone/) reference implementation as MCP tools. Any MCP host (Claude Desktop, Claude Code, Cursor, custom) can attach it as a stdio MCP server.

## Install

```bash
pip install touchstone-mcp
```

`fastmcp` and `clarethium-touchstone` install transitively. The `touchstone-mcp` console script is registered automatically and runs on the stdio transport by default.

## Host config

Drop this into your MCP host config:

```json
{
  "mcpServers": {
    "touchstone": {
      "command": "touchstone-mcp"
    }
  }
}
```

For Claude Code: `claude mcp add touchstone touchstone-mcp`.

## Tools exposed

* `verify` — calibrated `(text, source)` hallucination probability with scope classification, signal breakdown, and span-level localization.
* `measure` — raw multi-layer Touchstone output (all eleven Section 5 measurement layers).
* `assess_derivation_regime` — Layer 11 standalone regime classifier.
* `list_modes` — enumerate the four Verifier modes with their required inputs.

See [the host wiring guide](https://github.com/Clarethium/touchstone/blob/main/docs/mcp.md) for full tool reference, scope semantics, and threshold guidance.

## Programmatic use

```python
from touchstone_mcp import build_server

server = build_server()
server.run()                 # stdio transport
```

## Version pairing

`touchstone-mcp` depends on `clarethium-touchstone>=0.2.0`. The MCP server is a thin wrapper around the library's public surface; measurement semantics and calibration coefficients are defined and tested in the library, not here.

## License

Apache-2.0. See `LICENSE`.
