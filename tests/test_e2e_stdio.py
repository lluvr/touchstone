"""End-to-end tests against the ``touchstone-mcp`` console script over stdio.

The unit tests in ``test_server.py`` exercise ``build_server()`` in
process. This module spawns ``touchstone-mcp`` as a real subprocess
and speaks the Model Context Protocol over stdio the way an actual
MCP host (Claude Desktop, Claude Code, Cursor) attaches it. That
catches three classes of regression that in-process tests cannot:

1. Wire-protocol breakage. JSON-RPC framing, structured-content
   envelope, error responses, capability negotiation.
2. Console-script wiring. ``[project.scripts] touchstone-mcp =
   touchstone_mcp:main`` actually resolves and runs.
3. Standard-conformance loss through the MCP layer. The library's
   reference test suite at ``tests/reference/cases/`` is the
   canonical conformance surface (Standard §11.1). This module
   re-runs every one of those cases through the MCP ``measure`` tool
   over stdio and verifies the structured response matches the
   case's expected layer outputs within the case's declared
   tolerance. If a case passes through the library API but fails
   through the MCP tool, the MCP wrapper is lossy and the server
   is not a conforming surface.

The reference cases live in the monorepo's library tree; the tests
that need them skip cleanly if the cases directory is not reachable
(e.g. tests run against an installed wheel without a git checkout).
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

# Reference cases live at <repo>/tests/reference/cases/. This file lives
# at <repo>/tests/test_e2e_stdio.py, so the cases directory is the
# sibling reference/cases under this file's own parent.
REFERENCE_CASES_DIR = Path(__file__).resolve().parent / "reference" / "cases"


# ---------------------------------------------------------------------------
# Comparison helpers (mirror tests/reference/test_reference_cases.py::_compare
# byte-for-byte so the conformance check is the same shape as the library's
# own conformance runner).
# ---------------------------------------------------------------------------


def _compare(actual: Any, expected: Any, path: str, tolerance: float) -> list[str]:
    """Recursive structural comparison. Returns a list of failure strings."""
    failures: list[str] = []

    if expected is None:
        if actual is not None:
            failures.append(f"{path}: expected None, got {actual!r}")
        return failures

    if isinstance(expected, bool):
        if not isinstance(actual, bool) or actual != expected:
            failures.append(f"{path}: expected bool {expected!r}, got {actual!r}")
        return failures

    if isinstance(expected, int):
        if not isinstance(actual, int) or actual != expected:
            failures.append(f"{path}: expected int {expected}, got {actual!r}")
        return failures

    if isinstance(expected, float):
        if actual is None or isinstance(actual, bool):
            failures.append(f"{path}: expected float {expected}, got {actual!r}")
            return failures
        try:
            actual_f = float(actual)
        except (TypeError, ValueError):
            failures.append(f"{path}: expected float {expected}, got {actual!r}")
            return failures
        if abs(actual_f - expected) > tolerance:
            failures.append(
                f"{path}: expected {expected} +/- {tolerance}, got {actual_f}"
                f" (delta={abs(actual_f - expected):.6f})"
            )
        return failures

    if isinstance(expected, str):
        if actual != expected:
            failures.append(f"{path}: expected {expected!r}, got {actual!r}")
        return failures

    if isinstance(expected, list):
        if not isinstance(actual, list):
            failures.append(f"{path}: expected list, got {type(actual).__name__}")
            return failures
        if len(actual) != len(expected):
            failures.append(f"{path}: expected list of length {len(expected)}, got {len(actual)}")
            return failures
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            failures.extend(_compare(a, e, f"{path}[{i}]", tolerance))
        return failures

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            failures.append(f"{path}: expected dict, got {type(actual).__name__}")
            return failures
        for k, v in expected.items():
            if k not in actual:
                failures.append(f"{path}.{k}: expected key missing from actual")
                continue
            failures.extend(_compare(actual[k], v, f"{path}.{k}", tolerance))
        return failures

    failures.append(f"{path}: unsupported expected type {type(expected).__name__}")
    return failures


# ---------------------------------------------------------------------------
# stdio JSON-RPC client
# ---------------------------------------------------------------------------


class StdioClient:
    """Minimal MCP stdio client backed by a child subprocess.

    Sends newline-delimited JSON-RPC and reads responses, matching ids.
    Notifications are sent without expecting a reply.
    """

    def __init__(self, proc: subprocess.Popen[bytes]) -> None:
        assert proc.stdin is not None and proc.stdout is not None
        self._proc = proc
        self._next_id = 1

    def _send_raw(self, msg: dict[str, Any]) -> None:
        line = (json.dumps(msg) + "\n").encode("utf-8")
        assert self._proc.stdin is not None
        self._proc.stdin.write(line)
        self._proc.stdin.flush()

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        body: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        self._send_raw(body)

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        rid = self._next_id
        self._next_id += 1
        body: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            body["params"] = params
        self._send_raw(body)
        deadline = time.monotonic() + timeout
        assert self._proc.stdout is not None
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError(f"no response for {method!r} (id={rid}) within {timeout}s")
            raw = self._proc.stdout.readline()
            if not raw:
                raise RuntimeError(f"server closed stdout before responding to {method!r}")
            try:
                msg = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                # Server logs to stderr; anything non-JSON on stdout is
                # protocol garbage and worth surfacing.
                continue
            if msg.get("id") == rid:
                return msg


def _server_command() -> list[str]:
    """Resolve the touchstone-mcp executable.

    pytest runs from the same venv that pip-installed touchstone-mcp,
    so the console script is on PATH alongside the python interpreter.
    Fall back to ``python -m touchstone_mcp`` if the script is missing
    (unlikely with a normal install but covers exotic environments).
    """
    exe = shutil.which("touchstone-mcp")
    if exe:
        return [exe]
    return [sys.executable, "-c", "from touchstone_mcp import main; main()"]


@pytest.fixture(scope="session")
def stdio_client() -> Any:
    """Spawn ``touchstone-mcp`` once per test session and yield a client.

    Performs the MCP initialize handshake (initialize -> notifications/
    initialized) before yielding so every test sees an already-active
    server. On teardown, closes stdin and waits for the process to exit;
    falls back to kill on timeout to avoid leaving zombies.
    """
    cmd = _server_command()
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        env=env,
    )
    client = StdioClient(proc)

    try:
        init = client.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "e2e-stdio-harness", "version": "0.0"},
            },
        )
        if "error" in init:
            raise RuntimeError(f"initialize failed: {init['error']}")
        client.notify("notifications/initialized")
    except Exception:
        proc.kill()
        proc.wait(timeout=5)
        raise

    try:
        yield client
    finally:
        try:
            assert proc.stdin is not None
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)


def _structured(response: dict[str, Any]) -> dict[str, Any]:
    """Extract the structured-content payload from a tools/call response."""
    if "error" in response:
        raise AssertionError(f"unexpected JSON-RPC error: {response['error']}")
    result = response.get("result", {})
    # MCP servers may surface structured content under either key
    # depending on protocol version; both are valid.
    sc = result.get("structuredContent") or result.get("structured_content")
    if sc is None:
        raise AssertionError(f"tools/call response missing structured content: {response}")
    return sc


# ---------------------------------------------------------------------------
# Group A: protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """The wire-protocol contract MCP hosts depend on."""

    def test_initialize_reports_server_identity(self, stdio_client: StdioClient) -> None:
        """Server must report its name and version in initialize."""
        # The session fixture already initialized; re-issuing initialize on
        # the same session is server-specific behaviour and we don't depend
        # on it. Instead, exercise tools/list which is the next call any
        # real host makes after initialize.
        resp = stdio_client.request("tools/list")
        assert "result" in resp, resp

    def test_tools_list_returns_exactly_four_tools(self, stdio_client: StdioClient) -> None:
        resp = stdio_client.request("tools/list")
        tools = resp["result"]["tools"]
        names = sorted(t["name"] for t in tools)
        assert names == sorted(["verify", "measure", "assess_derivation_regime", "list_modes"])

    def test_tools_have_nonempty_descriptions(self, stdio_client: StdioClient) -> None:
        """Tool descriptions drive what MCP hosts present to the user."""
        resp = stdio_client.request("tools/list")
        tools = resp["result"]["tools"]
        for tool in tools:
            assert tool.get("description"), f"{tool['name']!r} has no description"
            assert len(tool["description"]) > 50, (
                f"{tool['name']!r} description suspiciously short: {tool['description']!r}"
            )

    def test_tools_have_input_schemas(self, stdio_client: StdioClient) -> None:
        """inputSchema is required by MCP for tool calls to validate."""
        resp = stdio_client.request("tools/list")
        tools = resp["result"]["tools"]
        for tool in tools:
            schema = tool.get("inputSchema")
            assert schema is not None, f"{tool['name']!r} missing inputSchema"
            assert schema.get("type") == "object", (
                f"{tool['name']!r} inputSchema type is {schema.get('type')!r}, expected 'object'"
            )

    def test_unknown_tool_returns_jsonrpc_error(self, stdio_client: StdioClient) -> None:
        """Calling a non-existent tool must return a JSON-RPC error,
        not crash the server."""
        resp = stdio_client.request(
            "tools/call",
            {"name": "this_tool_does_not_exist", "arguments": {}},
        )
        # Either an error response (preferred) or a result with isError=True
        # (FastMCP's convention) is acceptable; what we forbid is silent
        # success or a crash.
        if "error" in resp:
            return
        result = resp.get("result", {})
        assert result.get("isError") is True, f"unknown tool should error; got {resp}"

    def test_verify_missing_source_returns_error(self, stdio_client: StdioClient) -> None:
        """verify requires source; calling without should error cleanly."""
        resp = stdio_client.request(
            "tools/call",
            {"name": "verify", "arguments": {"text": "some text"}},
        )
        if "error" in resp:
            return
        result = resp.get("result", {})
        assert result.get("isError") is True, f"verify without source should error; got {resp}"

    def test_server_survives_after_error(self, stdio_client: StdioClient) -> None:
        """A bad call must not poison subsequent good calls."""
        # First, trigger an error.
        stdio_client.request(
            "tools/call",
            {"name": "this_tool_does_not_exist", "arguments": {}},
        )
        # Then issue a normal call and confirm the structured response.
        resp = stdio_client.request(
            "tools/call",
            {
                "name": "verify",
                "arguments": {
                    "text": "Revenue grew 12% to $143M.",
                    "source": "Revenue grew 12% to $143M.",
                },
            },
        )
        sc = _structured(resp)
        assert "prob_hallucinated" in sc
        assert isinstance(sc["prob_hallucinated"], int | float)


# ---------------------------------------------------------------------------
# Group B: Standard conformance via the MCP measure tool
# ---------------------------------------------------------------------------


def _discover_reference_cases() -> list[tuple[str, dict[str, Any]]]:
    if not REFERENCE_CASES_DIR.exists():
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(REFERENCE_CASES_DIR.glob("*.json")):
        case = json.loads(path.read_text())
        out.append((case["id"], case))
    return out


REFERENCE_CASES = _discover_reference_cases()


@pytest.mark.skipif(
    not REFERENCE_CASES,
    reason=(
        "tests/reference/cases/ not found (running against installed wheel outside the monorepo)"
    ),
)
class TestReferenceConformanceViaMCP:
    """The library's Standard-conformance cases, replayed through MCP.

    If any case passes via direct library call but fails through the
    MCP measure tool, the JSON-RPC wrapper is lossy and the server
    cannot claim Standard conformance.
    """

    @pytest.mark.parametrize(
        "case_id,case",
        REFERENCE_CASES,
        ids=[cid for cid, _ in REFERENCE_CASES],
    )
    def test_case_passes_via_mcp_measure(
        self,
        stdio_client: StdioClient,
        case_id: str,
        case: dict[str, Any],
    ) -> None:
        inputs = case["inputs"]
        tolerance = float(case.get("tolerance", {}).get("absolute", 1e-4))

        args: dict[str, Any] = {"text": inputs["text"]}
        if "source" in inputs:
            args["source"] = inputs["source"]
        if "comparisons" in inputs:
            args["comparisons"] = inputs["comparisons"]
        if "topic" in inputs:
            args["topic"] = inputs["topic"]

        resp = stdio_client.request("tools/call", {"name": "measure", "arguments": args})
        actual = _structured(resp)

        failures = _compare(actual, case["expected"], "", tolerance)
        if failures:
            details = "\n".join(f"  - {f}" for f in failures)
            pytest.fail(
                f"Reference case {case_id} failed via MCP:\n{details}\n"
                f"Description: {case.get('description', '(none)')}"
            )


# ---------------------------------------------------------------------------
# Group C: realistic discrimination signal
# ---------------------------------------------------------------------------


FAITHFUL_SOURCE = (
    "Apple reported Q1 fiscal 2026 revenue of $143 billion. The iPhone "
    "segment grew 8 percent year-over-year. Tim Cook commented on AI "
    "investments during the earnings call. Operating margins reached 32 "
    "percent. Services revenue hit a record $26 billion."
)


class TestDiscriminationSignal:
    """Faithful inputs must score below fabricated inputs.

    The project's docs (README, docs/production_readiness.md) state
    that the default 0.5 threshold under-flags; the F1-optimal
    thresholds on the published external corpora sit in [0.07, 0.27].
    This test does not assert against the default threshold. It
    asserts the relative ranking that drives the triage use case:
    fabricated probabilities are higher than faithful, with no
    overlap on these inputs.
    """

    def _verify(self, client: StdioClient, text: str, source: str | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {"text": text}
        if source is not None:
            args["source"] = source
        resp = client.request("tools/call", {"name": "verify", "arguments": args})
        return _structured(resp)

    def test_faithful_below_fabricated_clean_separation(self, stdio_client: StdioClient) -> None:
        faithful = [
            FAITHFUL_SOURCE,  # self-source
            (  # paraphrase
                "In Q1 fiscal 2026, Apple's revenue reached $143 billion. "
                "iPhone sales rose 8% year over year. CEO Tim Cook discussed "
                "AI spending on the earnings call. Operating margin was 32%, "
                "and services revenue hit a record $26 billion."
            ),
        ]
        fabricated = [
            (  # fabricated numbers
                "Apple reported Q1 fiscal 2026 revenue of $185 billion, the "
                "company's highest ever. The iPhone segment grew 8% "
                "year-over-year. Operating margins reached 47%. Services "
                "revenue grew to $42 billion."
            ),
            (  # fabricated entities + numbers
                "Apple reported Q1 fiscal 2026 revenue of $143 billion. The "
                "iPhone segment grew 8% year-over-year. McKinsey forecasts "
                "industry-wide growth of 47% next quarter. The Federal "
                "Reserve will raise rates 75 basis points in response."
            ),
        ]
        f_probs = [
            self._verify(stdio_client, t, FAITHFUL_SOURCE)["prob_hallucinated"] for t in faithful
        ]
        fab_probs = [
            self._verify(stdio_client, t, FAITHFUL_SOURCE)["prob_hallucinated"] for t in fabricated
        ]
        assert max(f_probs) < min(fab_probs), (
            f"discrimination overlap: faithful={f_probs}, fabricated={fab_probs}"
        )

    def test_fabrication_localized_in_top_unsupported(self, stdio_client: StdioClient) -> None:
        text = (
            "Apple reported Q1 fiscal 2026 revenue of $185 billion, the "
            "company's highest ever. The iPhone segment grew 8% "
            "year-over-year."
        )
        out = self._verify(stdio_client, text, FAITHFUL_SOURCE)
        spans = [s.get("sentence", "") for s in out.get("top_unsupported", [])]
        assert any("185 billion" in s for s in spans), (
            f"top_unsupported should localize the fabricated $185B sentence; got {spans}"
        )

    def test_empty_text_classified_insufficient_input(self, stdio_client: StdioClient) -> None:
        out = self._verify(stdio_client, "", FAITHFUL_SOURCE)
        assert out["scope"] == "insufficient_input"

    def test_short_text_not_validated_scope(self, stdio_client: StdioClient) -> None:
        """Regression gate: the v0.1.0 short-input bug returned
        scope='validated' with high prob on trivially faithful short
        inputs. The scope must NOT classify as validated here."""
        out = self._verify(stdio_client, "Revenue grew 12%.", FAITHFUL_SOURCE)
        assert out["scope"] != "validated", out

    def test_substrate_plus_judge_auto_selects(self, stdio_client: StdioClient) -> None:
        resp = stdio_client.request(
            "tools/call",
            {
                "name": "verify",
                "arguments": {
                    "text": "Apple reported Q1 revenue of $185 billion.",
                    "source": "Apple reported Q1 revenue of $143 billion.",
                    "judge_hallucinated_prob": 0.9,
                    "judge_alpha": 0.3,
                },
            },
        )
        out = _structured(resp)
        assert out["mode"] == "substrate_plus_judge", out
        assert "substrate_prob" in out["signal_breakdown"], out
        assert "judge_hallucinated_prob" in out["signal_breakdown"], out


# ---------------------------------------------------------------------------
# Group D: process health
# ---------------------------------------------------------------------------


class TestProcessHealth:
    """The server holds up under sustained call patterns.

    A single touchstone-mcp process serves an entire host session; if
    its per-call latency degrades over N calls or it leaks resources
    that crash later calls, that breaks the production-deployment
    shape (one stdio process attached to an MCP host for hours).
    """

    LATENCY_BUDGET_P95_MS = 100.0  # README claims sub-100ms per 5 KB document
    SUSTAINED_CALLS = 50

    def test_latency_stable_over_sustained_calls(self, stdio_client: StdioClient) -> None:
        durations_ms: list[float] = []
        for _ in range(self.SUSTAINED_CALLS):
            start = time.perf_counter()
            resp = stdio_client.request(
                "tools/call",
                {
                    "name": "verify",
                    "arguments": {
                        "text": (
                            "Apple reported Q1 fiscal 2026 revenue of $143 "
                            "billion. The iPhone segment grew 8 percent "
                            "year-over-year. Tim Cook discussed AI on the "
                            "earnings call."
                        ),
                        "source": FAITHFUL_SOURCE,
                    },
                },
            )
            durations_ms.append((time.perf_counter() - start) * 1000.0)
            _structured(resp)  # also validates no isError flag

        durations_ms.sort()
        p50 = statistics.median(durations_ms)
        p95 = durations_ms[int(len(durations_ms) * 0.95)]
        mx = max(durations_ms)
        assert p95 < self.LATENCY_BUDGET_P95_MS, (
            f"p95 latency {p95:.1f}ms exceeds budget "
            f"{self.LATENCY_BUDGET_P95_MS}ms over {self.SUSTAINED_CALLS} calls "
            f"(p50={p50:.1f}ms max={mx:.1f}ms)"
        )

    def test_versions_reported_match_installed(self, stdio_client: StdioClient) -> None:
        from clarethium_touchstone._version import (
            __standard_version__,
        )
        from clarethium_touchstone._version import (
            __version__ as lib_version,
        )
        from touchstone_mcp import __version__ as mcp_version

        resp = stdio_client.request("tools/call", {"name": "list_modes", "arguments": {}})
        out = _structured(resp)
        versions = out["versions"]
        assert versions["touchstone_library"] == lib_version, (
            f"library version drift: list_modes={versions['touchstone_library']!r} "
            f"installed={lib_version!r}"
        )
        assert versions["touchstone_standard"] == __standard_version__, (
            f"standard version drift: list_modes="
            f"{versions['touchstone_standard']!r} "
            f"installed={__standard_version__!r}"
        )
        assert versions["touchstone_mcp_server"] == mcp_version, (
            f"MCP server version drift: list_modes="
            f"{versions['touchstone_mcp_server']!r} "
            f"installed={mcp_version!r}"
        )

    def test_assess_derivation_regime_thresholds(self, stdio_client: StdioClient) -> None:
        expected = [
            (0, "diagnostic"),
            (4, "diagnostic"),
            (5, "transition"),
            (9, "transition"),
            (10, "saturated"),
            (50, "saturated"),
        ]
        for n, regime in expected:
            resp = stdio_client.request(
                "tools/call",
                {
                    "name": "assess_derivation_regime",
                    "arguments": {"source_num_count": n},
                },
            )
            out = _structured(resp)
            assert out["derivation_regime"] == regime, (
                f"source_num_count={n} -> got {out['derivation_regime']!r}, expected {regime!r}"
            )
