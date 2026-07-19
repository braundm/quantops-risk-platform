# QuantOps read-only MCP server

This package is a deliberately narrow Model Context Protocol adapter over the existing
`DemoQuantOpsService`. It does not query SQL, calculate risk independently, expose provider
prompts, or offer any mutation capability.

## Supported surface

Tools:

- `get_latest_portfolio_risk` — latest engine-backed snapshot for the one approved demo portfolio;
- `get_snapshot_evidence` — evidence manifest for an in-scope snapshot;
- `list_system_scenarios` — versioned hypothetical system scenario catalog.

Resources:

- `quantops://methodology/risk/1.0.0` — bounded methodology summary embedded in this package.

Every tool is annotated read-only, idempotent, non-destructive, and closed-world. Results are
typed structured output with a backwards-compatible text representation supplied by FastMCP.
They include evidence identity where applicable, explicit synthetic-data and no-investment-advice
labels, deterministic ordering, a 32 KiB serialized response limit, and a one-second application
service timeout.

There are no tools for portfolio writes, risk recomputation, scenario execution, audit mutation,
filesystem access, shell execution, URL fetching, environment inspection, database access, model
sampling, or arbitrary resource reading.

## Local stdio development

From the repository root, after installing the package dependencies into the local environment:

```powershell
$env:PYTHONPATH = "apps/mcp_server;apps/api"
.venv\Scripts\python.exe -m quantops_mcp
```

The process speaks MCP over standard input/output. It does not start an HTTP listener and does not
claim live-database integration. Protocol logs go to standard error through the SDK.

## Verification

```powershell
$env:PYTHONPATH = "apps/mcp_server;apps/api;packages/domain;packages/risk_engine/src"
.venv\Scripts\ruff.exe check apps/mcp_server
.venv\Scripts\ruff.exe format --check apps/mcp_server
.venv\Scripts\mypy.exe --strict apps/mcp_server/quantops_mcp apps/mcp_server/tests
.venv\Scripts\pytest.exe apps/mcp_server/tests -q
$env:UV_CACHE_DIR = ".uv-cache"
.venv\Scripts\uv.exe build apps/mcp_server --offline
```

## Official compatibility references

The implementation was checked on 19 July 2026 against primary sources:

- [MCP Python SDK stable package](https://pypi.org/project/mcp/) — stable v1.28.1; v2 prereleases
  require explicit opt-in and v1 users are advised to cap dependencies below 2;
- [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.28.1) —
  FastMCP tools/resources, structured output, stdio clients, and in-memory testing;
- [official Python SDK server guide](https://py.sdk.modelcontextprotocol.io/server/);
- [MCP protocol versioning](https://modelcontextprotocol.io/docs/learn/versioning) — current
  protocol revision 2025-11-25;
- [2025-11-25 protocol schema](https://modelcontextprotocol.io/specification/2025-11-25/schema)
  — structured content and tool annotations.

See [THREAT_MODEL.md](THREAT_MODEL.md) for the enforced boundary and residual risks.
