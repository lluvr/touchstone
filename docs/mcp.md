# Touchstone MCP

Touchstone MCP is the Model Context Protocol server that exposes the
`Verifier` and the `measure()` orchestrator as MCP tools. Any MCP host
(Claude Desktop, Claude Code, Cursor, custom) can attach the server
and call Touchstone in-context. The server ships inside the
[`touchstone-mcp`](https://pypi.org/project/touchstone-mcp/) package
as `src/touchstone_mcp.py`.

## Install

```bash
pip install touchstone-mcp
```

The package bundles the `clarethium_touchstone` reference implementation
library and installs with `fastmcp` (the MCP runtime) as its only
third-party dependency. The console script `touchstone-mcp` is
registered alongside.

## Tools exposed

| Tool | What it does |
|---|---|
| `verify(text, source, ...)` | Calibrated `(text, source)` hallucination probability, scope classification, signal breakdown, and span-level localization. Mirrors `Verifier.score()`. |
| `measure(text, source, ...)` | Raw multi-layer Touchstone output (all eleven Section 5 measurement layers). |
| `assess_derivation_regime(source_num_count)` | Layer 11 standalone regime classifier; surfaces a "trust this signal" hint before measurement runs. |
| `list_modes()` | Enumerate the four Verifier modes with their required inputs and the library + Standard versions in use. |

The `verify` tool accepts all the same optional baseline arguments the
underlying `Verifier.score()` does: `minicheck_supported_prob`,
`alignscore_supported_prob`, `judge_hallucinated_prob`, `judge_alpha`,
`top_k_unsupported`. Mode auto-selects from which optional arguments
are supplied; see [`api-reference.md`](api-reference.md#verifier) for
the mode-selection rules and the full parameter table.

## Wire it into your host

### Claude Desktop

Add to your MCP configuration (`~/Library/Application Support/Claude/claude_desktop_config.json`
on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "touchstone": {
      "command": "touchstone-mcp"
    }
  }
}
```

Restart Claude Desktop for the server to register.

### Claude Code

Add to `~/.claude/mcp.json` or your workspace's `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "touchstone": {
      "command": "touchstone-mcp",
      "args": []
    }
  }
}
```

### Cursor

Add a stdio MCP server entry with `command: touchstone-mcp` via
Cursor's MCP configuration UI.

### Custom hosts

```python
from touchstone_mcp import build_server

server = build_server()
server.run()                 # stdio transport (default)
```

`build_server()` returns a configured `fastmcp.FastMCP` instance that
can be attached to any FastMCP-compatible transport.

## Example tool call

A host calling `verify` with a hallucinated summary against a faithful
source receives:

```json
{
  "prob_hallucinated": 0.796,
  "mode": "substrate_only",
  "scope": "validated",
  "scope_notes": [
    "informative signals: ['l11', 'l4', 'l6']",
    "uninformative signals: ['l5']"
  ],
  "signal_breakdown": {
    "intercept": -2.1982,
    "l6_inv": 2.7608,
    "l4_unsourced": -0.1598,
    "l4_n_total_norm": 0.1642,
    "l11_p": 0.6991,
    "l5_entity_unsourced": 0.0,
    "l5_n_entities_norm": 0.0947
  },
  "top_unsupported": [
    {
      "sentence": "Apple reported Q1 fiscal 2026 revenue of $185 billion, the company's highest ever.",
      "sentence_index": 0,
      "layer11_primary": "P",
      "p_markers": ["unsourced_numbers"],
      "grounding_score": null
    }
  ]
}
```

The host can act on `prob_hallucinated` directly for `scope ==
"validated"` results. For `"limited_signal"` or
`"insufficient_input"` scopes, route the result to manual review
rather than auto-flagging; see [`api-reference.md`](api-reference.md#scope)
for scope semantics.

## Threshold guidance

The MCP tool returns the raw probability and scope; it does NOT make
the flag/no-flag decision for you. The default
`should_flag(threshold=0.5)` in the underlying library under-flags on
every published external corpus. F1-optimal thresholds on those
corpora are 0.07-0.27. Tune on your own held-out data before any
production deployment. [`production_readiness.md`](production_readiness.md)
§2 has the per-corpus tables.

## What Touchstone MCP is NOT

- **Not a standalone production hallucination detector.** Touchstone
  alone scores at chance on subtle semantic hallucinations that
  preserve vocabulary; the 16-case stress test in
  [`production_readiness.md`](production_readiness.md) documents the
  structural blindness. Use Touchstone as a triage signal or as the
  lexical-feature half of a two-stage architecture with an LLM-based
  judge.
- **Not a benchmark harness.** Touchstone ships benchmarks
  (`benchmarks/external/`) for reproducing the empirical-validation
  tables; this MCP server exposes the inference-time tools, not the
  benchmark runners.
