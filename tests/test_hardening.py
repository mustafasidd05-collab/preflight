import os
import time
from datetime import datetime

import pytest
from pydantic import ValidationError

from preflight.models import EvidenceItem
from preflight.ranker import (
    ResultRanker,
    score_evidence,
    unwrap_untrusted,
    wrap_untrusted,
)
from preflight.search_client import cache_is_fresh, prune_expired_cache, redact_sensitive
from preflight.synthesizer import (
    VerdictSynthesizer,
    extract_correction_symbol,
    guard_canonical_reference,
)
from preflight.trusted_domains import get_domain_tier, normalize_host


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://docs.python.org/3/library/", "docs.python.org"),
        ("http://www.Nextjs.org/docs", "nextjs.org"),
        ("user:pass@requests.readthedocs.io:443/en/latest/", "requests.readthedocs.io"),
        ("docs.pydantic.dev", "docs.pydantic.dev"),
        ("https://github.io.evil.com/x", "github.io.evil.com"),
        ("", ""),
    ],
)
def test_normalize_host(raw, expected):
    assert normalize_host(raw) == expected


@pytest.mark.parametrize(
    "host,tier,score",
    [
        ("requests.readthedocs.io", 1, 1.00),
        ("docs.pydantic.dev", 1, 1.00),
        ("www.nextjs.org", 1, 1.00),
        ("evil.github.io", 0, 0.50),
        ("malicious.readthedocs.io", 0, 0.50),
        ("docs.pydantic.dev.evil.com", 0, 0.50),
        ("notstackoverflow.com", 0, 0.50),
        ("stackoverflow.com.evil.org", 0, 0.50),
        ("gist.github.com", 2, 0.75),
        ("stackoverflow.com", 2, 0.75),
        ("medium.com", 3, 0.30),
    ],
)
def test_domain_tier_eviction(host, tier, score):
    assert get_domain_tier(host) == (tier, score)


@pytest.mark.parametrize(
    "date_str,expected",
    [
        ("2 hours ago", 1.00),
        ("3 days ago", 1.00),
        ("yesterday", 1.00),
        ("3 weeks ago", 0.95),
        ("2 months ago", 0.85),
        ("6 months ago", 0.85),
        ("12 months ago", 0.70),
        ("18 months ago", 0.70),
        ("24 months ago", 0.40),
        ("1 year ago", 0.70),
        ("a year ago", 0.70),
        ("2 years ago", 0.40),
        (f"Jan 3, {datetime.now().year}", 0.70),
        (f"Jun 30, {datetime.now().year - 3}", 0.40),
        ("recently", 0.60),
        (None, 0.60),
    ],
)
def test_recency_boundary_table(date_str, expected):
    assert ResultRanker.calculate_recency_score(date_str) == expected


def test_trust_score_clamped_to_unit_interval():
    # base 1.00 x recency 1.00 x path bonus 1.1 = 1.1 -> clamped to 1.0
    tier, score = score_evidence("https://docs.pydantic.dev/docs/api", "2 hours ago")
    assert tier == 1
    assert score == 1.0
    assert 0.0 <= score <= 1.0


def test_schema_rejects_out_of_range_trust_score():
    with pytest.raises(ValidationError):
        EvidenceItem(
            title="t", url="https://a.example/", snippet="s", domain="a.example",
            trust_tier=0, trust_score=1.2,
        )
    with pytest.raises(ValidationError):
        EvidenceItem(
            title="t", url="https://a.example/", snippet="s", domain="a.example",
            trust_tier=0, trust_score=-0.1,
        )


def test_snippet_wrapping_and_unwrap():
    raw = "See the docs\x00\x07 for details."
    wrapped = wrap_untrusted(raw)
    assert wrapped.startswith("<untrusted_search_snippet>")
    assert wrapped.endswith("</untrusted_search_snippet>")
    assert "\x00" not in wrapped and "\x07" not in wrapped
    assert unwrap_untrusted(wrapped) == "See the docs for details."


def test_api_key_redaction():
    assert (
        redact_sensitive("https://serpapi.com/search?api_key=abc123&engine=google")
        == "https://serpapi.com/search?api_key=[REDACTED]&engine=google"
    )
    assert redact_sensitive("{'api_key': 'xyz'}") == "{'api_key': '[REDACTED]'}"
    assert "SECRET" not in redact_sensitive("Request failed: api_key=SECRET")


def test_cache_ttl_expiry(tmp_path):
    f = tmp_path / "k.json"
    f.write_text("{}")
    assert cache_is_fresh(f)
    old = time.time() - 8 * 86400
    os.utime(f, (old, old))
    assert not cache_is_fresh(f)
    assert prune_expired_cache(tmp_path) == 1
    assert not f.exists()


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://docs.python.org/3/", "https://docs.python.org/3/"),
        ("http://example.com/x", None),
        ("javascript:alert(1)", None),
        (None, None),
    ],
)
def test_canonical_reference_https_only(url, expected):
    assert guard_canonical_reference(url) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("use the", None),
        ("moved to a", None),
        ("use our", None),
        ("moved to pydantic-settings", "pydantic-settings"),
        ("renamed to BaseSettings", "BaseSettings"),
    ],
)
def test_fallback_correction_regex_stopwords(text, expected):
    assert extract_correction_symbol(text) == expected


def test_rank_results_tier_tiebreak_prefers_tier3_over_tier0():
    raw_serp = [
        {
            "organic_results": [
                {
                    "title": "Untrusted Attacker Blog",
                    "link": "https://evil.github.io/exploit",
                    "snippet": "Some unverified code",
                    # None date -> recency 0.60; Tier 0 base 0.50 -> 0.50 * 0.60 = 0.30
                    "date": None,
                },
                {
                    "title": "Tutorial Point Guide",
                    "link": "https://tutorialspoint.com/guide",
                    "snippet": "Tutorial guide",
                    # today -> recency 1.00; Tier 3 base 0.30 -> 0.30 * 1.00 = 0.30
                    "date": "today",
                },
            ]
        }
    ]
    ranked = ResultRanker.rank_results(raw_serp)
    assert len(ranked) == 2
    assert ranked[0].trust_score == ranked[1].trust_score == 0.30
    assert ranked[0].trust_tier == 3
    assert ranked[0].domain == "tutorialspoint.com"
    assert ranked[1].trust_tier == 0
    assert ranked[1].domain == "evil.github.io"


def test_extract_correction_nextjs_15_variants():
    code, variants = VerdictSynthesizer.extract_correction(
        "Next.js 15 page params is an async Promise", []
    )
    assert code is not None
    assert "await params" in code
    assert len(variants) >= 3
    assert any(v.context == "client_component" for v in variants)
    assert any(v.context == "codemod" for v in variants)


def test_detect_signals_word_boundary_no_false_positives():
    text = "an interactive, reactive UI using non-standard APIs with radioactive elements"
    signals = ResultRanker.detect_signals(text)
    assert not any("active" in s for s in signals)
    assert not any("standard" in s for s in signals)
    assert len(signals) == 0
