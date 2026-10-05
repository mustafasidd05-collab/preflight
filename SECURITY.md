# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Preflight, please report it responsibly:

1. **Email:** Send details to `security@serpapi.com` or open a private security advisory on GitHub.
2. **Do Not Open Public Issues:** Please do not file public issues regarding unpatched security vulnerabilities.
3. **Information to Include:**
   - Description of the vulnerability and attack vector
   - Steps to reproduce or proof-of-concept
   - Potential impact on AI agent execution or API credentials

## Security Architecture & Best Practices

- **API Keys:** Never commit `SERPAPI_API_KEY` to source control. Use `.env` or system environment variables.
- **AI Agent Isolation:** Preflight is designed as a grounding oracle. Host environments should run agent tools within appropriate security sandboxes.
- **Cache Management:** Local cached search responses are stored in `.preflight_cache/` and are gitignored by default.
