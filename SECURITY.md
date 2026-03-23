# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 0.1.x (latest) | ✅ |

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Please report security issues by emailing the maintainer directly
(see the GitHub profile for contact details). Include:

- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- Any suggested mitigations

You will receive an acknowledgement within 48 hours and a resolution plan
within 7 days for confirmed vulnerabilities.

## Security Design Notes

### Credentials
- All secrets (API keys, SMTP passwords) are loaded exclusively via `kpi_lens/config.py`
  using Pydantic Settings from a `.env` file. No credentials appear in source code.
- `.env` is gitignored. `.env.example` contains only placeholder values.
- `.claude/settings.json` is gitignored (may contain local permission configs).

### Database
- Default storage is a local SQLite file. For production deployments, replace
  `DATABASE_URL` in `.env` with a PostgreSQL connection string protected by
  network ACLs.
- The MCP server is **read-only** — it never writes to the database directly.

### API
- No authentication middleware is included in v0.1.x. For internet-facing deployments,
  place the FastAPI service behind an API gateway or reverse proxy that handles
  authentication and rate-limiting.

### LLM
- No user-supplied input is sent to the Anthropic API without sanitisation.
  All prompts are constructed by the application from structured KPI data.
