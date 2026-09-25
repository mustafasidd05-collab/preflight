"""
Tests for SerpApiSearchClient: query caching, replay fixture matching, and fallback behavior.
"""

import pytest
from preflight.search_client import SerpApiSearchClient, FIXTURES_DIR


@pytest.mark.asyncio
async def test_replay_fixture_matching_pydantic():
    client = SerpApiSearchClient()
    # Force replay mode
    res = await client.search('site:docs.pydantic.dev "BaseSettings" v2', force_replay=True)
    assert res.get("_is_replayed") is True
    assert "organic_results" in res
    assert len(res["organic_results"]) > 0
    # Must contain official docs
    assert any("pydantic" in r.get("link", "") for r in res["organic_results"])


@pytest.mark.asyncio
async def test_replay_fixture_matching_nextjs():
    client = SerpApiSearchClient()
    res = await client.search('site:nextjs.org/docs v15 params', force_replay=True)
    assert res.get("_is_replayed") is True
    assert "organic_results" in res
    assert any("nextjs.org" in r.get("link", "") for r in res["organic_results"])


@pytest.mark.asyncio
async def test_fallback_when_no_api_key(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    client = SerpApiSearchClient()
    # In live mode (force_replay=False), missing key must NEVER silently replay
    res = await client.search('pydantic BaseSettings', force_replay=False)
    assert res.get("_is_replayed") is False
    assert res.get("_unverifiable_due_to_missing_key") is True

    # In replay mode (force_replay=True), it should replay from recorded fixtures
    replay_res = await client.search('pydantic BaseSettings', force_replay=True)
    assert replay_res.get("_is_replayed") is True
