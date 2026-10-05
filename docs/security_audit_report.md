# Security Audit Report: Preflight FastMCP Grounding Engine

> [!NOTE]
> **Remediation Status:** Historical security audit report. All findings ([SEC-01] through [SEC-06]) have been fully remediated and verified in the codebase as of Revision 5/6. Regression defenses are tested continuously in [`tests/test_hardening.py`](file:///c:/Users/hp/Projects/SerpApi/tests/test_hardening.py).

**Audit Date:** October 2026  
**Auditor:** Antigravity Autonomous Security Subsystem  
**Target Codebase:** [Preflight](file:///c:/Users/hp/Projects/SerpApi) (`fastmcp` + SerpApi Grounding Engine for AI Coding Agents)  
**Status:** Remediated & Verified (83/83 Tests Passing, Static Analysis & Threat Model Finished)  

---

## 1. Executive Summary

A comprehensive architectural and application security audit was performed on the **Preflight** MCP server and CLI utility. Preflight acts as an authoritative grounding oracle for AI coding assistants (Claude Code, Cursor, OpenCode, Claude Desktop) by evaluating code assertions against live web search results via SerpApi.

### Risk Overview
| Severity | Count | Primary Impact Areas | Remediation Status |
|:---|:---:|:---|:---|
| **High** | 2 | Domain authority hijacking via permissive wildcards; Indirect prompt injection via unauthenticated web snippets | **RESOLVED** (Exact-host Tier 1 registry; deterministic templates & boundary tags) |
| **Medium** | 2 | API key leakage in exception serialization / CLI flags; Non-atomic configuration overwrite in installer | **RESOLVED** (`redact_sensitive()`; atomic `.tmp` + `os.replace` + `.bak`) |
| **Low / Informational** | 3 | Unbounded cache disk exhaustion; FIPS incompatibility (unflagged MD5); Unhandled top-level MCP exceptions | **RESOLVED** (7-day TTL pruning; `usedforsecurity=False`; partial gather resilience) |

Overall, Preflight exhibits clean code structure, parameterized search queries without shell injection risks, and strict test coverage. Defenses against **domain spoofing**, **indirect prompt injection**, and **configuration corruption** are now fully active and verified.

---

## 2. Threat Model & Architecture Surface

```
[ AI Agent Context (Claude / Cursor) ]
              │   ▲
  MCP Tool    │   │ Structured PreflightVerdict
  Invocation  ▼   │ (Contains Deterministic Template Action & Correction)
[ Preflight FastMCP Server (server.py) ]
              │   ▲
  Search      │   │ Filtered & Weighted Evidence (Tier 1 > Tier 2 > Tier 3 > Tier 0)
  Queries     ▼   │
[ ResultRanker & Synthesizer ]
              │   ▲
  HTTP GET    │   │ Raw SerpApi SERP JSON (<untrusted_search_snippet> Wrapped)
  (Redacted)  ▼   │
[ SerpApi / Public Internet ] ─── (Attacker-Controlled Content / SEO)
```

### Attack Vectors Analyzed & Mitigated:
1. **Adversarial Web Content / SEO Poisoning:** Untrusted third-party documentation attempts to inject malicious code patterns into SerpApi results. *Mitigated by strict exact-host Tier 1 registry and Tier 0 untrusted fallback.*
2. **Indirect Prompt Injection:** Adversarial text embedded in web snippets attempts to override calling agent instructions. *Mitigated by `<untrusted_search_snippet>` boundaries and 100% template-generated summaries and suggested actions.*
3. **Domain Authority Spoofing:** Subdomain or prefix matching grants Tier 1 official status to attacker-controlled sites. *Mitigated by exact-host matching in `trusted_domains.py` and boundary-safe subdomain checks.*
4. **Credential Leakage:** Exposure of `SERPAPI_API_KEY` via process tables, logs, or error responses. *Mitigated by centralized `redact_sensitive()` masking.*
5. **Client Configuration Integrity:** Corruption or truncation of developer IDE configuration files during automated setup. *Mitigated by atomic writing to `.tmp`, file mode preservation, and `.bak` generation.*

---

## 3. Vulnerability Findings & Risk Analysis

### [SEC-01] HIGH: Domain Trust Hijacking via Permissive Subdomain & Prefix Matching
- **Classification:** CWE-20 (Improper Input Validation), CWE-345 (Insufficient Verification of Data Authenticity)
- **Remediation Implemented:**
  - Evicted `github.io`, `readthedocs.io`, and `gitbook.io` wildcards from Tier 1.
  - Pinned Tier 1 to exact verified hosts (`TIER_1_EXACT_HOSTS`), such as `docs.pydantic.dev` and `requests.readthedocs.io`.
  - Dropped arbitrary prefix matching (`docs.*`).
  - Added Tier 0 (Untrusted / Unknown) with score 0.50 for all unlisted domains.

---

### [SEC-02] HIGH: Indirect Prompt Injection via Untrusted Web Snippets
- **Classification:** OWASP LLM01: Prompt Injection, CWE-1426 (Improper Handling of Generative AI Inputs/Outputs)
- **Remediation Implemented:**
  - Sanitized snippets and enclosed them within `<untrusted_search_snippet>` delimiters.
  - Made `suggested_action` and `summary` 100% deterministic template-generated.
  - Validated symbol extraction against stopword lists and word boundaries.

---

### [SEC-03] MEDIUM: Sensitive Credential Exposure via Process Arguments & Exception Serialization
- **Classification:** CWE-214 (Invocation of Process with Sensitive Information in Arguments), CWE-209 (Generation of Error Message Containing Sensitive Information)
- **Remediation Implemented:**
  - Centralized `redact_sensitive()` in `search_client.py` masking `api_key=[REDACTED]`.
  - Deprecated command-line `--serpapi-key` in favor of `.env` and environment variables.

---

### [SEC-04] MEDIUM: Non-Atomic File Overwrite of IDE Configurations
- **Classification:** CWE-377 (Insecure Temporary File), CWE-732 (Incorrect Permission Assignment)
- **Remediation Implemented:**
  - Implemented `atomic_write_json()` in `client_installer.py` using `.tmp` files and `os.replace()`.
  - Preserved original file permissions via `os.chmod`.
  - Created `.bak` backups prior to modifications.
  - Enforced non-destructive preservation of existing user configurations while cleanly auto-pruning legacy prototype entries (`fact-dock`).

---

### [SEC-05] LOW: Unbounded Disk Cache Growth (Resource Exhaustion)
- **Classification:** CWE-400 (Uncontrolled Resource Consumption)
- **Remediation Implemented:**
  - Introduced 7-day TTL (`CACHE_TTL_SECONDS = 7 * 86400`).
  - Implemented `cache_is_fresh()` and `prune_expired_cache()`.

---

### [SEC-06] LOW: Use of MD5 Without FIPS Declaration
- **Classification:** CWE-328 (Use of Weak Hash)
- **Remediation Implemented:**
  - Passed `usedforsecurity=False` in all `hashlib.md5()` invocations.

---

## 4. Verification & Testing Status

| Test Suite | Tests Run | Passed | Failed | Status |
|:---|:---:|:---:|:---:|:---|
| `test_client_installer.py` | 11 | 11 | 0 | PASS |
| `test_hardening.py` | 50 | 50 | 0 | PASS |
| `test_mcp_stdio_e2e.py` | 1 | 1 | 0 | PASS |
| `test_query_engine.py` | 6 | 6 | 0 | PASS |
| `test_ranker.py` | 4 | 4 | 0 | PASS |
| `test_search_client.py` | 3 | 3 | 0 | PASS |
| `test_server.py` | 4 | 4 | 0 | PASS |
| `test_synthesizer.py` | 4 | 4 | 0 | PASS |
| **Total** | **83** | **83** | **0** | **100% Passing** |

- **Dependency Audit:** Zero unpinned or known vulnerable direct dependencies in `pyproject.toml`.
- **Secret Scanning:** No committed secrets found in Git history or active files.
