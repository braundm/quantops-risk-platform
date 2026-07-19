"""Protocol-level tests for the exact read-only MCP surface."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import TextResourceContents
from pydantic import AnyUrl
from quantops_api.application.demo_service import DEMO_PORTFOLIO_ID, DemoQuantOpsService

from quantops_mcp.adapter import DEFAULT_MAX_RESPONSE_BYTES
from quantops_mcp.server import METHODOLOGY_RESOURCE_URI, create_server


def _serialized_size(value: dict[str, object]) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    )


@pytest.mark.asyncio
@pytest.mark.contract
async def test_exact_read_only_surface_and_structured_results() -> None:
    service = DemoQuantOpsService()
    audit_before = service.list_audit_events()

    async with create_connected_server_and_client_session(create_server(service)) as session:
        listed = await session.list_tools()
        tools = {tool.name: tool for tool in listed.tools}
        assert set(tools) == {
            "get_latest_portfolio_risk",
            "get_snapshot_evidence",
            "list_system_scenarios",
        }
        assert not {
            "create",
            "delete",
            "execute",
            "recompute",
            "replace",
            "run",
            "update",
            "write",
        }.intersection("_".join(tools).split("_"))

        for tool in tools.values():
            assert tool.outputSchema is not None
            assert tool.annotations is not None
            assert tool.annotations.readOnlyHint is True
            assert tool.annotations.destructiveHint is False
            assert tool.annotations.idempotentHint is True
            assert tool.annotations.openWorldHint is False

        risk_result = await session.call_tool(
            "get_latest_portfolio_risk",
            {"portfolio_id": str(DEMO_PORTFOLIO_ID), "scope": "demo"},
        )
        assert risk_result.isError is False
        assert risk_result.structuredContent is not None
        risk = risk_result.structuredContent
        assert risk["scope"] == "demo"
        assert risk["is_synthetic"] is True
        assert risk["not_investment_advice"] is True
        assert risk["evidence_id"] == risk["snapshot"]["evidence_id"]
        assert risk["snapshot"]["portfolio_id"] == str(DEMO_PORTFOLIO_ID)
        assert risk["snapshot"]["observation_count"] == 40
        assert _serialized_size(risk) <= DEFAULT_MAX_RESPONSE_BYTES

        snapshot_id = UUID(risk["snapshot"]["snapshot_id"])
        evidence_result = await session.call_tool(
            "get_snapshot_evidence",
            {"snapshot_id": str(snapshot_id), "scope": "demo"},
        )
        assert evidence_result.isError is False
        assert evidence_result.structuredContent is not None
        evidence = evidence_result.structuredContent
        assert evidence["snapshot_id"] == str(snapshot_id)
        assert evidence["evidence_id"] == risk["evidence_id"]
        assert evidence["evidence"]["evidence_id"] == risk["evidence_id"]
        assert len(evidence["evidence"]["items"]) == 5
        assert all(item["payload_sha256"] for item in evidence["evidence"]["items"])
        assert _serialized_size(evidence) <= DEFAULT_MAX_RESPONSE_BYTES

        scenarios_result = await session.call_tool("list_system_scenarios", {"scope": "demo"})
        assert scenarios_result.isError is False
        assert scenarios_result.structuredContent is not None
        scenarios = scenarios_result.structuredContent
        assert scenarios["count"] == 5
        assert [item["scenario_id"] for item in scenarios["scenarios"]] == sorted(
            item["scenario_id"] for item in scenarios["scenarios"]
        )
        assert all(item["hypothetical"] is True for item in scenarios["scenarios"])
        assert _serialized_size(scenarios) <= DEFAULT_MAX_RESPONSE_BYTES

        prompts = await session.list_prompts()
        templates = await session.list_resource_templates()
        assert prompts.prompts == []
        assert templates.resourceTemplates == []

    assert service.list_audit_events() == audit_before


@pytest.mark.asyncio
@pytest.mark.contract
async def test_methodology_is_the_only_fixed_resource() -> None:
    async with create_connected_server_and_client_session(create_server()) as session:
        resources = await session.list_resources()
        assert [str(item.uri) for item in resources.resources] == [METHODOLOGY_RESOURCE_URI]

        result = await session.read_resource(AnyUrl(METHODOLOGY_RESOURCE_URI))
        assert len(result.contents) == 1
        content = result.contents[0]
        assert isinstance(content, TextResourceContents)
        assert content.mimeType == "text/markdown"
        assert "deterministic, versioned calculations" in content.text
        assert "not forecasts or probabilities" in content.text
        assert "does not provide investment advice" in content.text
