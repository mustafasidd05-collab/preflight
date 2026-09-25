"""
Verdict synthesizer for Preflight.
Combines weighted evidence, detects semantic signals, and produces the final PreflightVerdict.
"""

import re
import time
from typing import List, Optional, Tuple
from preflight.models import PreflightVerdict, EvidenceItem, ClaimAnalysis, VerdictType


# Common correction pattern extractors
CORRECTION_PATTERNS = [
    r"(?:use|moved to|renamed to|replaced with|replaced by|installed from)\s+[`'\"]?([a-zA-Z0-9_\-\.]+)[`'\"]?",
    r"(?:from|import)\s+([a-zA-Z0-9_\-]+)\s+import\s+([a-zA-Z0-9_]+)",
    r"[`'\"]([a-zA-Z0-9_\-\.]+\s+import\s+[a-zA-Z0-9_]+)[`'\"]",
    r"(?:now returns|params is now a|type is now)\s+[`'\"]?([a-zA-Z0-9_<>\s]+)[`'\"]?",
]


class VerdictSynthesizer:
    """Synthesizes ranked search evidence into a structured verdict."""

    @staticmethod
    def extract_correction(claim: str, evidence_list: List[EvidenceItem]) -> Optional[str]:
        """Extract recommended modern replacement code or statement from snippets."""
        for ev in evidence_list[:5]:
            text = f"{ev.title} {ev.snippet}"
            
            # Specific high-value heuristic for Pydantic v2
            if "pydantic" in claim.lower() and "basesettings" in claim.lower():
                if "pydantic_settings" in text.lower() or "pydantic-settings" in text.lower():
                    return "from pydantic_settings import BaseSettings"

            # Specific high-value heuristic for Next.js 15 params
            if "next" in claim.lower() and "params" in claim.lower():
                if "promise" in text.lower() or "async" in text.lower():
                    return "In Next.js 15+, page and layout `params` is a Promise: `async function Page({ params }: { params: Promise<{ id: string }> })`"

            # Specific high-value heuristic for React 19 forwardRef
            if "react" in claim.lower() and "forwardref" in claim.lower():
                if "prop" in text.lower() or "deprecated" in text.lower():
                    return "In React 19, `ref` can be passed directly as a standard component prop without wrapping in `forwardRef`"

            # Specific high-value heuristic for FastAPI lifespan / on_event
            if "fastapi" in claim.lower() and ("on_event" in claim.lower() or "lifespan" in claim.lower() or "startup" in claim.lower()):
                if "lifespan" in text.lower():
                    return "@asynccontextmanager\nasync def lifespan(app: FastAPI):\n    yield\n\napp = FastAPI(lifespan=lifespan)"

            # General regex extraction
            for pat in CORRECTION_PATTERNS:
                match = re.search(pat, text, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) == 2:
                        return f"from {groups[0]} import {groups[1]}"
                    elif len(groups) == 1 and len(groups[0]) > 3:
                        val = groups[0].strip()
                        if val.lower() not in {"the", "a", "this", "new", "true", "false"}:
                            return f"Use `{val}` instead"

        return None

    @classmethod
    def synthesize(
        cls,
        claim: str,
        analysis: ClaimAnalysis,
        evidence: List[EvidenceItem],
        queries_executed: List[str],
        start_time_ns: int,
        is_replayed: bool = False,
        unverifiable_missing_key: bool = False,
        api_error: Optional[str] = None,
        fixture_missing: bool = False,
    ) -> PreflightVerdict:
        """Evaluate evidence and return a complete PreflightVerdict."""
        elapsed_ms = int((time.perf_counter_ns() - start_time_ns) / 1_000_000)

        # Handle explicit API error
        if api_error:
            return PreflightVerdict(
                claim=claim,
                verdict="UNVERIFIABLE",
                confidence=0.0,
                summary=f"CRITICAL: Live SerpApi query failed: {api_error}",
                correction=None,
                canonical_reference="https://serpapi.com/manage-api-key",
                suggested_action="Verify your SerpApi API key validity and network connectivity at https://serpapi.com/manage-api-key",
                evidence_count=0,
                top_evidence=[],
                queries_executed=queries_executed,
                is_replayed=False,
                response_time_ms=elapsed_ms,
            )

        # Handle missing key in live mode (loud & explicit)
        if unverifiable_missing_key:
            return PreflightVerdict(
                claim=claim,
                verdict="UNVERIFIABLE",
                confidence=0.0,
                summary="CRITICAL: No SERPAPI_API_KEY set and replay mode (--replay) was not requested. Live web verification requires an authentic SerpApi key.",
                correction=None,
                canonical_reference="https://serpapi.com/manage-api-key",
                suggested_action="Set the SERPAPI_API_KEY environment variable, pass --serpapi-key to the CLI, or append --replay for offline demonstration.",
                evidence_count=0,
                top_evidence=[],
                queries_executed=queries_executed,
                is_replayed=False,
                response_time_ms=elapsed_ms,
            )

        # Handle missing fixture in replay mode
        if fixture_missing and not evidence:
            return PreflightVerdict(
                claim=claim,
                verdict="UNVERIFIABLE",
                confidence=0.0,
                summary=f"Replay Error: No pre-recorded SerpApi fixture exists for this claim. Replay mode only supports pre-recorded benchmarks.",
                correction=None,
                canonical_reference="https://serpapi.com",
                suggested_action="Run without --replay and provide SERPAPI_API_KEY to search live web data for arbitrary claims.",
                evidence_count=0,
                top_evidence=[],
                queries_executed=queries_executed,
                is_replayed=True,
                response_time_ms=elapsed_ms,
            )

        if not evidence:
            return PreflightVerdict(
                claim=claim,
                verdict="UNVERIFIABLE",
                confidence=0.2,
                summary="No authoritative evidence found matching the specific technical assertion.",
                correction=None,
                canonical_reference=None,
                suggested_action="Avoid making assumptions about this API without consulting official package documentation.",
                evidence_count=0,
                top_evidence=[],
                queries_executed=queries_executed,
                is_replayed=is_replayed,
                response_time_ms=elapsed_ms,
            )

        # Calculate signal scores weighted by domain trust
        deprecate_score = 0.0
        confirm_score = 0.0

        for item in evidence:
            dep_count = sum(1 for s in item.signals if s.startswith("deprecation:"))
            conf_count = sum(1 for s in item.signals if s.startswith("confirmation:"))

            # Tier 1 carries full weight, Tier 2 carries 0.7, Tier 3 carries 0.3
            weight = item.trust_score

            deprecate_score += dep_count * weight
            confirm_score += conf_count * weight

            # Bonus for explicit documentation URL
            if item.trust_tier == 1:
                confirm_score += 0.5 * weight

        # Best canonical reference
        canonical_ref = evidence[0].url if evidence else None
        correction = cls.extract_correction(claim, evidence)

        # Check if the claim itself states a deprecation or replacement relationship
        claim_lower = claim.lower()
        claim_asserts_deprecation = any(
            w in claim_lower
            for w in ["deprecated", "replaced", "obsolete", "removed", "replacement", "no longer"]
        )

        pkg_name = analysis.package_name or "this package"
        sym_name = analysis.symbol_name or "this feature"

        # Decision Thresholds
        if deprecate_score >= 1.0 and (deprecate_score > confirm_score * 0.8 or claim_asserts_deprecation):
            if claim_asserts_deprecation:
                # The claim asserted X is deprecated or replaced by Y, and evidence confirms it
                verdict: VerdictType = "CONFIRMED"
                confidence = min(0.98, max(0.85, 0.75 + (deprecate_score * 0.08)))
                if "fastapi" in claim_lower and ("on_event" in claim_lower or "lifespan" in claim_lower):
                    summary = (
                        "Confirmed: Official FastAPI documentation verifies that `on_event` ('startup'/'shutdown') "
                        "handlers are deprecated and replaced by `lifespan` context managers."
                    )
                    suggested_action = (
                        "Use the modern `lifespan` context manager pattern with `@asynccontextmanager`."
                    )
                else:
                    summary = (
                        f"Confirmed: Official documentation and migration notes verify that {pkg_name} ({sym_name}) "
                        f"is indeed deprecated or superseded as asserted."
                    )
                    suggested_action = (
                        f"Proceed with modern replacement syntax. {f'Recommended: `{correction}`.' if correction else ''}"
                    )
            else:
                # The claim asserted the old pattern; evidence shows it is deprecated
                verdict = "OUTDATED"
                confidence = min(0.98, max(0.80, 0.70 + (deprecate_score * 0.08)))
                summary = (
                    f"The assertion regarding {pkg_name} ({sym_name}) appears outdated or deprecated based on "
                    f"official documentation and migration notes."
                )
                suggested_action = (
                    f"Do not use the deprecated pattern. {f'Update to: `{correction}`.' if correction else 'Review the canonical reference for the current syntax.'}"
                )

        elif confirm_score >= 1.0 and deprecate_score < 0.8:
            verdict = "CONFIRMED"
            confidence = min(0.96, max(0.75, 0.70 + (confirm_score * 0.06)))
            summary = f"The claim is confirmed current and active in official documentation and registries."
            suggested_action = "Proceed with this implementation. The syntax and usage are supported."

        elif deprecate_score >= 0.8 and confirm_score >= 0.8:
            verdict = "CONFLICTING"
            confidence = 0.65
            summary = "Found conflicting signals between older community examples and newer release notices."
            suggested_action = "Check your targeted major version explicitly before finalizing the implementation."

        else:
            verdict = "UNVERIFIABLE"
            confidence = 0.40
            summary = "Search results did not yield sufficient authoritative signal to definitively verify or refute the claim."
            suggested_action = "Check the official repository directly or test the syntax in an isolated sandbox."

        return PreflightVerdict(
            claim=claim,
            verdict=verdict,
            confidence=round(confidence, 2),
            summary=summary,
            correction=correction if verdict == "OUTDATED" else None,
            canonical_reference=canonical_ref,
            suggested_action=suggested_action,
            evidence_count=len(evidence),
            top_evidence=evidence[:4],
            queries_executed=queries_executed,
            is_replayed=is_replayed,
            response_time_ms=elapsed_ms,
        )
