"""
Source trust tiering and recency ranker for Preflight.
Evaluates search results from SerpApi and ranks them by authority and freshness.
"""

import re
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional
from preflight.models import EvidenceItem
from preflight.trusted_domains import get_domain_tier

# Regex for detecting versions in text (e.g., v2.0, 15.0, v3)
VERSION_REGEX = re.compile(r"\b(?:v|version)?\s*([0-9]+\.[0-9]+(?:\.[0-9]+)?)\b", re.IGNORECASE)
MAJOR_VERSION_REGEX = re.compile(r"\b(?:v|version)\s*([0-9]+)\b", re.IGNORECASE)

# Keywords indicating breaking changes or deprecations
DEPRECATION_SIGNALS = [
    "deprecated", "deprecated in", "removed in", "renamed to", "moved to",
    "breaking change", "migration guide", "no longer supported", "has been replaced",
    "legacy", "obsolete", "discontinued"
]

# Keywords indicating current confirmation
CONFIRMATION_SIGNALS = [
    "stable", "latest", "introduced in", "still supported", "current version",
    "official documentation", "parameter verify", "session.get"
]


class ResultRanker:
    """Ranks and weights raw SerpApi search results based on domain trust and recency."""

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract clean domain name from URL."""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc
        except Exception:
            return ""

    @staticmethod
    def detect_signals(text: str) -> List[str]:
        """Detect deprecation and confirmation signals in snippets and titles."""
        text_lower = text.lower()
        signals = []
        for kw in DEPRECATION_SIGNALS:
            if kw in text_lower:
                signals.append(f"deprecation:{kw}")
        for kw in CONFIRMATION_SIGNALS:
            if kw in text_lower:
                signals.append(f"confirmation:{kw}")
        return signals

    # Alias for API backwards compatibility
    extract_signals = detect_signals

    @classmethod
    def calculate_recency_score(cls, date_str: Optional[str]) -> float:
        """Calculate freshness score multiplier based on date string."""
        if not date_str:
            return 0.70
        date_lower = date_str.lower()
        if any(term in date_lower for term in ["hour", "day"]):
            return 1.0
        if "week" in date_lower:
            return 0.95
        if "month" in date_lower:
            return 0.85
        if "year" in date_lower:
            if any(y in date_lower for y in ["2 year", "3 year", "4 year", "5 year", "2020", "2019", "2018"]):
                return 0.40
            return 0.60
        return 0.70

    @classmethod
    def process_serp_item(cls, item: Dict[str, Any]) -> Optional[EvidenceItem]:
        """Convert a single SerpApi organic result into an EvidenceItem."""
        link = item.get("link", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")

        if not link or not (title or snippet):
            return None

        domain = cls.extract_domain(link)
        tier, base_score = get_domain_tier(domain)

        # Check published date from SerpApi metadata
        date_str = item.get("date")

        # Detect versions in title and snippet
        combined_text = f"{title} {snippet}"
        v_match = VERSION_REGEX.search(combined_text) or MAJOR_VERSION_REGEX.search(combined_text)
        detected_version = v_match.group(1) if v_match else None

        # Detect semantic signals
        signals = cls.detect_signals(combined_text)

        # Recency boost / penalty calculation
        recency_multiplier = cls.calculate_recency_score(date_str)

        # Path authority boost (e.g. /releases/, /docs/, /changelog/)
        path_lower = urlparse(link).path.lower()
        if any(p in path_lower for p in ["/releases", "/changelog", "/migration", "/docs"]):
            base_score = min(1.0, base_score * 1.1)

        final_trust_score = round(min(1.0, base_score * recency_multiplier), 3)

        return EvidenceItem(
            title=title,
            url=link,
            snippet=snippet,
            domain=domain,
            trust_tier=tier,
            trust_score=final_trust_score,
            published_date=date_str,
            detected_version=detected_version,
            signals=signals,
        )

    @classmethod
    def rank_results(cls, raw_serp_responses: List[Dict[str, Any]]) -> List[EvidenceItem]:
        """Extract, deduplicate, and sort evidence items by trust score and relevance."""
        seen_urls = set()
        evidence_list: List[EvidenceItem] = []

        for resp in raw_serp_responses:
            # Process answer box if present
            answer_box = resp.get("answer_box", {})
            if answer_box and isinstance(answer_box, dict):
                ab_link = answer_box.get("link") or resp.get("search_parameters", {}).get("q", "")
                ab_snippet = answer_box.get("snippet") or answer_box.get("answer", "")
                if ab_snippet:
                    item = cls.process_serp_item({
                        "link": ab_link or "https://serpapi.com/answer-box",
                        "title": answer_box.get("title", "Instant Answer"),
                        "snippet": ab_snippet,
                    })
                    if item and item.url not in seen_urls:
                        seen_urls.add(item.url)
                        evidence_list.append(item)

            # Process organic results
            for org in resp.get("organic_results", []):
                item = cls.process_serp_item(org)
                if item and item.url not in seen_urls:
                    seen_urls.add(item.url)
                    evidence_list.append(item)

        # Sort: Primary by trust score descending, secondary by Tier ascending (Tier 1 first)
        evidence_list.sort(key=lambda ev: (-ev.trust_score, ev.trust_tier))
        return evidence_list
