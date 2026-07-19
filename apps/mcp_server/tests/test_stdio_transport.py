"""End-to-end MCP client/server smoke test over the local stdio transport."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from quantops_api.application.demo_service import DEMO_PORTFOLIO_ID

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.asyncio
@pytest.mark.contract
async def test_python_module_serves_mcp_over_stdio() -> None:
    import_paths = (
        REPOSITORY_ROOT / "apps" / "mcp_server",
        REPOSITORY_ROOT / "apps" / "api",
        REPOSITORY_ROOT / "packages" / "domain",
        REPOSITORY_ROOT / "packages" / "risk_engine" / "src",
        REPOSITORY_ROOT / "packages" / "data_contracts" / "src",
    )
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "quantops_mcp"],
        env={"PYTHONPATH": os.pathsep.join(str(path) for path in import_paths)},
        cwd=REPOSITORY_ROOT,
    )

    async with asyncio.timeout(10):
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.name == "QuantOps Read-Only Risk"
                assert initialized.protocolVersion == "2025-11-25"

                result = await session.call_tool(
                    "get_latest_portfolio_risk",
                    {"portfolio_id": str(DEMO_PORTFOLIO_ID), "scope": "demo"},
                )

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["scope"] == "demo"
    assert result.structuredContent["snapshot"]["portfolio_id"] == str(DEMO_PORTFOLIO_ID)
