"""
Pydantic data models for Preflight.
"""

from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


Ecosystem = Literal["python", "javascript", "typescript", "rust", "go", "general"]
VerdictType = Literal["CONFIRMED", "OUTDATED", "CONFLICTING", "UNVERIFIABLE"]


class EvidenceItem(BaseModel):
    """An individual piece of evidence extracted from a search result."""
    title: str = Field(..., description="Page title")
    url: str = Field(..., description="Source URL")
    snippet: str = Field(..., description="Relevant text excerpt from source")
    domain: str = Field(..., description="Extracted root domain")
    trust_tier: int = Field(..., description="Trust tier (1=Official/Registry, 2=Community, 3=Aggregator)")
    trust_score: float = Field(..., ge=0.0, le=1.0, description="Composite trust score (0.0 - 1.0)")
    published_date: Optional[str] = Field(None, description="Published date string if detected in SERP")
    detected_version: Optional[str] = Field(None, description="Software version detected in title or snippet")
    signals: List[str] = Field(default_factory=list, description="Extracted semantic signals (e.g. deprecated, breaking, current)")


class ClaimAnalysis(BaseModel):
    """Deconstructed elements of a raw technical assertion."""
    raw_claim: str
    inferred_ecosystem: Ecosystem
    package_name: Optional[str] = None
    symbol_name: Optional[str] = None
    claimed_version: Optional[str] = None
    target_action: Optional[str] = None
    search_queries: List[str] = Field(default_factory=list)

    @property
    def package(self) -> Optional[str]:
        return self.package_name

    @property
    def symbol(self) -> Optional[str]:
        return self.symbol_name

    @property
    def version(self) -> Optional[str]:
        return self.claimed_version

    @property
    def claim(self) -> str:
        return self.raw_claim

    @property
    def ecosystem(self) -> Ecosystem:
        return self.inferred_ecosystem


class PreflightVerdict(BaseModel):
    """The structured decision object returned to the calling AI agent."""
    claim: str = Field(..., description="The original claim evaluated")
    verdict: VerdictType = Field(..., description="Final status: CONFIRMED, OUTDATED, CONFLICTING, or UNVERIFIABLE")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    summary: str = Field(..., description="Concise explanation of the verdict rationale")
    correction: Optional[str] = Field(None, description="Actionable replacement code or accurate assertion if outdated")
    canonical_reference: Optional[str] = Field(None, description="Most authoritative URL validating this verdict")
    suggested_action: str = Field(..., description="Specific recommendation for the coding agent")
    evidence_count: int = Field(..., description="Number of evaluated search evidence items")
    top_evidence: List[EvidenceItem] = Field(default_factory=list, description="Top ranked evidence sources supporting the verdict")
    queries_executed: List[str] = Field(default_factory=list, description="Search queries run against SerpApi")
    is_replayed: bool = Field(False, description="True if evidence was replayed from recorded SerpApi queries (offline mode)")
    response_time_ms: int = Field(..., description="Execution time in milliseconds")


class VerifyClaimRequest(BaseModel):
    """Request payload for claim verification."""
    claim: str = Field(..., description="The code, API, or library assertion to verify against live web docs")
    ecosystem: Optional[Ecosystem] = Field(None, description="Optional programming language or ecosystem hint")
    target_package: Optional[str] = Field(None, description="Optional package name hint (e.g., 'pydantic', 'next')")
    replay: bool = Field(False, description="Explicitly replay from recorded SerpApi cache if available")


class QuickCheckResponse(BaseModel):
    """Lightweight response for fast API symbol queries."""
    package: str
    symbol: str
    status: VerdictType
    latest_reference: Optional[str] = None
    note: str
