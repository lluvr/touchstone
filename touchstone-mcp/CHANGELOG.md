# Changelog

All notable changes to `touchstone-mcp` are documented here. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.1.1 - 2026-05-24

Patch release: fixes the server-version reported to MCP host UIs, plus sibling-pattern completeness (CITATION.cff + NOTICE bundled in the wheel). No tool surface, schema, or output shape changes; `touchstone-mcp==0.1.1` is a drop-in replacement for `0.1.0`.

### What changed

- **`serverInfo.version` now reports `0.1.1` instead of FastMCP's version.** In `0.1.0`, the MCP `initialize` response carried `serverInfo = {"name": "touchstone", "version": "3.3.1"}` because the FastMCP constructor defaulted `version` to its own package version. MCP host UIs (Claude Desktop, Claude Code, Cursor) display `serverInfo.version` next to the server name; the wrong number was misleading. Passing the package `__version__` to `FastMCP(version=...)` makes the displayed version match the installed `touchstone-mcp` distribution.
- **`CITATION.cff` added** so academic, applied, and compliance citations resolve via structured metadata. Modelled on the sibling `cma-mcp` CITATION shape; references both the `clarethium-touchstone` library and the Touchstone Standard as separately citeable artifacts.
- **`NOTICE` added** (Apache 2.0 §4(d) attribution), bundled alongside `LICENSE` in the wheel's `dist-info/licenses/` via `license-files = ["LICENSE", "NOTICE"]` in `pyproject.toml`. Names the two-distribution monorepo, the wrapped library, and the sibling Clarethium projects.

### What stayed

- The four MCP tools (`verify`, `measure`, `assess_derivation_regime`, `list_modes`), their schemas, output shapes, and structured-content payloads are byte-identical to `0.1.0`.
- The `touchstone-mcp` console script command, the stdio transport default, and the host-config JSON in `docs/mcp.md` are unchanged.
- Runtime dependencies (`clarethium-touchstone >= 0.2.0`, `fastmcp >= 2.0`) are unchanged. Resolves cleanly against `clarethium-touchstone` 0.2.1 (the simultaneous metadata-only patch) without a re-pin.

### Verification this release ships the right artifact

- `pip install touchstone-mcp==0.1.1` resolves and installs cleanly in a fresh venv; the `touchstone-mcp` console script registers, `from touchstone_mcp import build_server` works, and the spawned server's `initialize` response carries `serverInfo.version = "0.1.1"`.
- The wheel's `dist-info/licenses/` directory contains both `LICENSE` and `NOTICE`.
- 17 unit tests + 31 end-to-end stdio JSON-RPC tests pass; `mypy --strict` + `ruff check + format check` + canon audit all clean.

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
