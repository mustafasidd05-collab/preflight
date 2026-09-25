"""
Tests for VerdictSynthesizer: multi-source consensus, verdict resolution, and correction extraction.
"""

import time
import pytest
from preflight.models import ClaimAnalysis, EvidenceItem
from preflight.synthesizer import VerdictSynthesizer


def test_synthesize_outdated_claim():
    claim = "In Pydantic v2, BaseSettings is imported directly from pydantic"
    analysis = ClaimAnalysis(
        raw_claim=claim,
        inferred_ecosystem="python",
        package_name="pydantic",
        symbol_name="BaseSettings",
        claimed_version="2",
        search_queries=["site:docs.pydantic.dev BaseSettings v2"],
    )
    evidence = [
        EvidenceItem(
            title="Migration Guide - Pydantic Docs",
            url="https://docs.pydantic.dev/latest/migration/",
            snippet="In Pydantic v2, BaseSettings has been moved to pydantic-settings. Instead use: from pydantic_settings import BaseSettings",
            domain="docs.pydantic.dev",
            trust_tier=1,
            trust_score=1.0,
            published_date="1 month ago",
            detected_version="2",
            signals=["deprecation:moved to", "deprecation:migration guide"],
        ),
        EvidenceItem(
            title="Pydantic GitHub Releases",
            url="https://github.com/pydantic/pydantic/releases",
            snippet="BaseSettings moved to pydantic-settings in v2.0 breaking change",
            domain="github.com",
            trust_tier=2,
            trust_score=0.8,
            published_date="2023",
            detected_version="2.0",
            signals=["deprecation:breaking change", "deprecation:moved to"],
        ),
    ]

    verdict = VerdictSynthesizer.synthesize(
        claim=claim,
        analysis=analysis,
        evidence=evidence,
        queries_executed=analysis.search_queries,
        start_time_ns=time.perf_counter_ns(),
        is_replayed=False,
    )

    assert verdict.verdict == "OUTDATED"
    assert verdict.confidence >= 0.8
    assert verdict.canonical_reference == "https://docs.pydantic.dev/latest/migration/"
    assert "pydantic_settings" in (verdict.correction or "")
    assert verdict.evidence_count == 2


def test_synthesize_confirmed_claim():
    claim = "In Python requests, session.verify controls SSL certificate verification"
    analysis = ClaimAnalysis(
        raw_claim=claim,
        inferred_ecosystem="python",
        package_name="requests",
        symbol_name="session.verify",
        claimed_version=None,
        search_queries=["site:requests.readthedocs.io session.verify"],
    )
    evidence = [
        EvidenceItem(
            title="SSL Verification - Requests Docs",
            url="https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification",
            snippet="Session.get verify parameter controls SSL verification. Default is True.",
            domain="requests.readthedocs.io",
            trust_tier=1,
            trust_score=1.0,
            published_date="recent",
            detected_version=None,
            signals=["confirmation:session.get", "confirmation:stable"],
        )
    ]

    verdict = VerdictSynthesizer.synthesize(
        claim=claim,
        analysis=analysis,
        evidence=evidence,
        queries_executed=analysis.search_queries,
        start_time_ns=time.perf_counter_ns(),
        is_replayed=False,
    )

    assert verdict.verdict == "CONFIRMED"
    assert verdict.confidence >= 0.7
    assert "requests.readthedocs.io" in (verdict.canonical_reference or "")


def test_synthesize_unverifiable_claim():
    claim = "In FoobarSDK v99, enableQuantumSpeed(True) is the main call"
    analysis = ClaimAnalysis(
        raw_claim=claim,
        inferred_ecosystem="general",
        package_name="foobarsdk",
        symbol_name="enableQuantumSpeed",
        claimed_version="99",
        search_queries=["site:pypi.org foobarsdk"],
    )

    verdict = VerdictSynthesizer.synthesize(
        claim=claim,
        analysis=analysis,
        evidence=[],
        queries_executed=analysis.search_queries,
        start_time_ns=time.perf_counter_ns(),
        is_replayed=False,
    )

    assert verdict.verdict == "UNVERIFIABLE"
    assert verdict.confidence <= 0.2
    assert verdict.evidence_count == 0


def test_synthesize_fastapi_deprecation_replacement_claim():
    claim = "In FastAPI 0.115+, lifespan events replaced on_event startup/shutdown handlers"
    analysis = ClaimAnalysis(
        raw_claim=claim,
        inferred_ecosystem="python",
        package_name="fastapi",
        symbol_name="on_event",
        claimed_version="0.115",
        search_queries=[
            'site:fastapi.tiangolo.com OR site:pypi.org/project/fastapi "on_event" v0.115',
            '"fastapi" "on_event" (deprecated OR removed OR "breaking change" OR "migration guide")',
            '"fastapi" "on_event" usage example',
        ],
    )
    evidence = [
        EvidenceItem(
            title="Lifespan Events - FastAPI",
            url="https://fastapi.tiangolo.com/advanced/events/",
            snippet="In previous versions, you would use @app.on_event('startup') and @app.on_event('shutdown'). These are now deprecated and replaced by lifespan events.",
            domain="fastapi.tiangolo.com",
            trust_tier=1,
            trust_score=1.0,
            published_date="recent",
            detected_version="0.115",
            signals=["deprecation:deprecated", "deprecation:has been replaced"],
        ),
    ]

    verdict = VerdictSynthesizer.synthesize(
        claim=claim,
        analysis=analysis,
        evidence=evidence,
        queries_executed=analysis.search_queries,
        start_time_ns=time.perf_counter_ns(),
        is_replayed=False,
    )

    assert verdict.verdict == "CONFIRMED"
    assert "on_event" in verdict.summary
    assert "deprecated" in verdict.summary
    assert "lifespan" in verdict.summary
    assert verdict.canonical_reference == "https://fastapi.tiangolo.com/advanced/events/"

