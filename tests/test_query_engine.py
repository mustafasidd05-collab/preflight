"""
Tests for QueryEngine: claim deconstruction and multi-vector query formulation.
"""

import pytest
from preflight.query_engine import QueryEngine


def test_infer_ecosystem_python():
    claim = "In Python 3.12, asyncio.run should be used instead of get_event_loop"
    eco = QueryEngine.infer_ecosystem(claim)
    assert eco == "python"


def test_infer_ecosystem_javascript():
    claim = "In Next.js 15, page params is an async Promise in TypeScript"
    eco = QueryEngine.infer_ecosystem(claim)
    assert eco in ("javascript", "typescript")


def test_extract_package_known_and_generic():
    assert QueryEngine.extract_package("In Pydantic v2, BaseSettings moved") == "pydantic"
    assert QueryEngine.extract_package("In requests, session.verify is a boolean") == "requests"
    assert QueryEngine.extract_package("In Next.js 15, route handlers use Request") in ("nextjs", "next.js", "next")
    assert QueryEngine.extract_package("In react 19, forwardRef is deprecated") == "react"


def test_extract_symbol():
    assert QueryEngine.extract_symbol("In Pydantic v2, BaseSettings is imported", package="pydantic") == "BaseSettings"
    assert QueryEngine.extract_symbol("In requests, session.verify controls SSL", package="requests") == "session.verify"
    assert QueryEngine.extract_symbol("React 19 forwardRef is no longer needed", package="react") == "forwardRef"


def test_extract_version():
    assert QueryEngine.extract_version("In Pydantic v2, models use model_validate") == "2"
    assert QueryEngine.extract_version("Next.js 15 changes layout params") == "15"
    assert QueryEngine.extract_version("React 19 removes forwardRef") == "19"


def test_analyze_claim_generates_search_vectors():
    analysis = QueryEngine.analyze_claim(
        claim="In Pydantic v2, BaseSettings is imported from pydantic",
        ecosystem_hint="python",
        package_hint="pydantic",
    )
    assert analysis.package == "pydantic"
    assert analysis.symbol == "BaseSettings"
    assert analysis.version == "2"
    assert len(analysis.search_queries) >= 2
    # First query must target canonical docs
    assert "docs.pydantic.dev" in analysis.search_queries[0] or "pypi.org" in analysis.search_queries[0]
    # Second query must check deprecation
    assert any("deprecated" in q or "breaking" in q for q in analysis.search_queries)
