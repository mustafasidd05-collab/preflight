"""
Tests for FastMCP Server: verify_claim, quick_check, prompt, and resources.
"""

import json
import pytest
from preflight.server import verify_claim, quick_check, pre_flight_api_audit, get_status, get_trusted_domains


@pytest.mark.asyncio
async def test_server_verify_claim_tool():
    claim = "In Pydantic v2, BaseSettings is imported directly from pydantic"
    res_json = await verify_claim(claim=claim, replay=True)
    data = json.loads(res_json)

    assert data["claim"] == claim
    assert data["verdict"] == "OUTDATED"
    assert data["is_replayed"] is True
    assert "pydantic_settings" in (data.get("correction") or "")
    assert data["confidence"] > 0.7


@pytest.mark.asyncio
async def test_server_quick_check_tool():
    res_json = await quick_check(package="pydantic", symbol="BaseSettings", version="2", replay=True)
    data = json.loads(res_json)

    assert data["package"] == "pydantic"
    assert data["symbol"] == "BaseSettings"
    assert data["status"] == "OUTDATED"


def test_server_prompt_template():
    prompt = pre_flight_api_audit("pydantic, nextjs, fastapi")
    assert "pydantic, nextjs, fastapi" in prompt
    assert "verify_claim" in prompt


def test_server_resources():
    status_raw = get_status()
    status_data = json.loads(status_raw)
    assert status_data["server"] == "Preflight"
    assert "tools" in status_data

    domains_raw = get_trusted_domains()
    domains_data = json.loads(domains_raw)
    assert "tier_1_authoritative_registries_and_docs" in domains_data
    assert "pypi.org" in domains_data["tier_1_authoritative_registries_and_docs"]

