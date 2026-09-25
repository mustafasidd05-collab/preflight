"""
Tests for ResultRanker: authority scoring, recency decay, and signal extraction.
"""

import pytest
from preflight.ranker import ResultRanker
from preflight.trusted_domains import get_domain_tier, get_domain_weight


def test_domain_tiering():
    # Tier 1
    assert get_domain_tier("docs.pydantic.dev")[0] == 1
    assert get_domain_tier("pypi.org")[0] == 1
    assert get_domain_tier("nextjs.org")[0] == 1
    assert get_domain_weight("docs.python.org") == 1.0

    # Tier 2
    assert get_domain_tier("github.com")[0] == 2
    assert get_domain_tier("stackoverflow.com")[0] == 2
    assert get_domain_weight("github.com") == 0.75

    # Tier 3
    assert get_domain_tier("random-blog.medium.com")[0] == 3
    assert get_domain_weight("tutorialspoint.com") == 0.30


def test_recency_multiplier():
    assert ResultRanker.calculate_recency_score("2 days ago") == 1.0
    assert ResultRanker.calculate_recency_score("3 weeks ago") == 0.95
    assert ResultRanker.calculate_recency_score("2 months ago") == 0.85
    assert ResultRanker.calculate_recency_score("3 years ago") == 0.40
    assert ResultRanker.calculate_recency_score(None) == 0.70


def test_signal_extraction():
    snippet = "BaseSettings is deprecated in v2.0 and moved to pydantic-settings"
    signals = ResultRanker.extract_signals(snippet)
    assert any("deprecated" in s for s in signals)
    assert any("moved to" in s for s in signals)


def test_rank_results_ordering():
    raw_serp = [{
        "organic_results": [
            {
                "title": "Random Medium Post",
                "link": "https://medium.com/someuser/pydantic",
                "snippet": "Pydantic tips and tricks",
                "date": "2 years ago",
            },
            {
                "title": "Official Migration Guide",
                "link": "https://docs.pydantic.dev/latest/migration/",
                "snippet": "In Pydantic v2, BaseSettings has been moved to pydantic-settings",
                "date": "1 month ago",
            },
        ]
    }]

    ranked = ResultRanker.rank_results(raw_serp)
    assert len(ranked) == 2
    # Official docs should rank first due to Tier 1 domain and higher recency
    assert ranked[0].trust_tier == 1
    assert "docs.pydantic.dev" in ranked[0].domain
    assert ranked[0].trust_score > ranked[1].trust_score
