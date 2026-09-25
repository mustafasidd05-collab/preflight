"""
Curated registry of trusted developer domains and ecosystem heuristics.
"""

from typing import Dict, List, Set, Tuple
from preflight.models import Ecosystem

# Tier 1: Canonical package registries, official documentation hosts, official GitHub releases
TIER_1_DOMAINS: Set[str] = {
    # Package Registries
    "pypi.org",
    "npmjs.com",
    "crates.io",
    "pkg.go.dev",
    "rubygems.org",
    "packagist.org",
    "nuget.org",

    # Core Language & Spec Docs
    "docs.python.org",
    "developer.mozilla.org",
    "typescriptlang.org",
    "nodejs.org",
    "go.dev",
    "rust-lang.org",
    "docs.rs",

    # Major Framework Documentation
    "docs.pydantic.dev",
    "pydantic-docs.helpmanual.io",
    "fastapi.tiangolo.com",
    "flask.palletsprojects.com",
    "docs.djangoproject.com",
    "requests.readthedocs.io",
    "sqlalchemy.org",
    "pandas.pydata.org",
    "numpy.org",
    "scipy.org",
    "pytest.org",

    "nextjs.org",
    "react.dev",
    "reactjs.org",
    "vuejs.org",
    "angular.dev",
    "svelte.dev",
    "expressjs.com",
    "tailwindcss.com",

    "python.langchain.com",
    "js.langchain.com",
    "platform.openai.com",
    "docs.anthropic.com",
    "ai.google.dev",

    # General Documentation Platforms
    "readthedocs.io",
    "gitbook.io",
    "github.io",
}

# Tier 2: High quality community sources, Q&A, source code repositories, engineering blogs
TIER_2_DOMAINS: Set[str] = {
    "github.com",
    "gitlab.com",
    "stackoverflow.com",
    "stackexchange.com",
    "news.ycombinator.com",
    "dev.to",
    "reddit.com",
}

# Tier 3 / Lower Trust: Content aggregators, SEO farms, tutorial sites (frequently unmaintained/outdated)
TIER_3_DOMAINS: Set[str] = {
    "geeksforgeeks.org",
    "w3schools.com",
    "tutorialspoint.com",
    "medium.com",
    "javatpoint.com",
    "freecodecamp.org",
    "towardsdatascience.com",
}

# Ecosystem keyword indicators
ECOSYSTEM_SIGNALS: Dict[Ecosystem, List[str]] = {
    "python": [
        "python", "pip", "pypi", "def ", "import ", "from ", "class ",
        "pydantic", "fastapi", "django", "flask", "requests", "pandas",
        "numpy", "asyncio", "pytest", "sqlalchemy", "celery", "poetry"
    ],
    "javascript": [
        "javascript", "js", "npm", "yarn", "pnpm", "node", "nodejs",
        "const ", "let ", "function", "require(", "import from",
        "react", "vue", "svelte", "express", "lodash", "axios"
    ],
    "typescript": [
        "typescript", "ts", "interface ", "type ", "<T>", "as const",
        "nextjs", "next.js", "nest.js", "prisma", "zod", "trpc"
    ],
    "rust": [
        "rust", "cargo", "crates.io", "fn ", "impl ", "trait ",
        "struct ", "pub ", "tokio", "actix", "serde", "axum"
    ],
    "go": [
        "golang", "go get", "pkg.go.dev", "func ", "goroutine",
        "struct {", "gin", "gorm", "echo", "fiber"
    ],
    "general": []
}


def get_domain_tier(domain: str) -> Tuple[int, float]:
    """
    Returns (tier, base_trust_score) for a given domain string.
    Tier 1 = Official/Registry (0.95 - 1.0)
    Tier 2 = Community/Repositories (0.65 - 0.75)
    Tier 3 = Aggregators/Tutorials (0.25 - 0.35)
    Unknown = 0.50 default
    """
    domain = domain.lower().strip()
    
    # Check exact match
    if domain in TIER_1_DOMAINS:
        return 1, 1.0
    if domain in TIER_2_DOMAINS:
        return 2, 0.75
    if domain in TIER_3_DOMAINS:
        return 3, 0.30

    # Subdomain match (e.g. docs.github.com or something.readthedocs.io)
    for t1 in TIER_1_DOMAINS:
        if domain.endswith("." + t1) or domain == t1:
            return 1, 0.95

    for t2 in TIER_2_DOMAINS:
        if domain.endswith("." + t2) or domain == t2:
            return 2, 0.70

    for t3 in TIER_3_DOMAINS:
        if domain.endswith("." + t3) or domain == t3:
            return 3, 0.30

    # Special rules for documentation subdomains
    if domain.startswith("docs.") or domain.startswith("documentation."):
        return 1, 0.90
    if "readthedocs" in domain or "gitbook" in domain:
        return 1, 0.90

    # Neutral default for unknown domains
    return 2, 0.55


def get_domain_weight(domain: str) -> float:
    """Convenience helper returning just the trust weight float (0.0 to 1.0)."""
    return get_domain_tier(domain)[1]
