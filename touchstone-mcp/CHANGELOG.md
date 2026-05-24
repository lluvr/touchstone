# Changelog

All notable changes to `touchstone-mcp` are documented here. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.1.0 - 2026-05-24

Initial release as a standalone PyPI distribution. The Touchstone MCP
server previously shipped as the `[mcp]` optional-dependency extra of
`clarethium-touchstone` (last shipped under that path in
`clarethium-touchstone==0.1.2`); it now ships as its own distribution
to align with the sibling Clarethium MCP servers (`cma-mcp`,
`frame-check-mcp`) and to keep the core library install
dependency-free.

### Migration from `clarethium-touchstone[mcp]`

Before (`clarethium-touchstone <= 0.1.2`):

```bash
pip install "clarethium-touchstone[mcp]"
```

```python
from clarethium_touchstone.mcp import build_server
```

After (`clarethium-touchstone >= 0.2.0` + `touchstone-mcp >= 0.1.0`):

```bash
pip install touchstone-mcp
```

```python
from touchstone_mcp import build_server
```

The MCP host config (`{"command": "touchstone-mcp"}`) is unchanged.
The four tools (`verify`, `measure`, `assess_derivation_regime`,
`list_modes`) are unchanged in name, schema, and output shape.

### Server surface

* Four MCP tools registered: `verify`, `measure`,
  `assess_derivation_regime`, `list_modes`.
* `build_server()` returns a configured `fastmcp.FastMCP` instance.
* `main()` runs the server on the stdio transport. The `touchstone-mcp`
  console script binds to `touchstone_mcp:main`.
* Module-level `Verifier` instance so calibration coefficients load
  once and are reused across calls.

### Dependencies

* `clarethium-touchstone >= 0.2.0` (the reference implementation).
* `fastmcp >= 2.0` (the MCP runtime).
