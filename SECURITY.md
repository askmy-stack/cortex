# Security Policy

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

- Preferred: use GitHub's private vulnerability reporting for this repository
  (Security tab → **Report a vulnerability**).
- Alternative: email **kamineniabhinaysai@gmail.com** with a description of
  the issue, steps to reproduce, and its potential impact.

We aim to acknowledge reports within 7 days and to keep you updated as we
investigate and fix confirmed issues.

## Supported Versions

Cortex does not yet have tagged releases; security fixes are applied to the
`main` branch. Run the latest `main` to get fixes as soon as they land.

## Authentication Model

- **API auth** (`api/deps.py`) is controlled by `CORTEX_API_KEYS`
  (`key:role;role` pairs). When set, roles are resolved server-side from a
  validated `Authorization: Bearer <key>` or `X-API-Key` header, and the
  client-supplied `X-Cortex-Roles` header is ignored. When unset, the API
  runs in **open/dev mode** and trusts `X-Cortex-Roles` — do not run with
  `CORTEX_API_KEYS` unset on a network-reachable deployment.
- **MCP server** (`mcp/server.js`) requires `CORTEX_API_KEY` whenever
  `ENVIRONMENT=production`; without it, it refuses all tool calls rather than
  falling back to the legacy role header, since that header is a privilege
  escalation vector when MCP env access doesn't imply a real API key.
- **Webhooks** (`api/webhooks.py` — Slack, GitHub, Jira, Linear) are verified
  independently via per-connector HMAC signatures (`SLACK_SIGNING_SECRET`,
  `GITHUB_WEBHOOK_SECRET`, `JIRA_WEBHOOK_SECRET`, `LINEAR_WEBHOOK_SECRET`).
  Configure these in production; requests with a missing or invalid signature
  are rejected with `401` once a secret is configured.
- `API_SECRET_KEY`/`JWT_ALGORITHM`/`JWT_EXPIRY_HOURS` are reserved for future
  JWT-based auth and are not currently used to authenticate requests.

## GDPR / Right to Erasure

`POST /gdpr/erase` (`api/gdpr.py`) cascades deletes for a person across
Decisions, Rationales, and Contradictions in the knowledge graph, and writes
a `GdprAuditLog` entry. It requires the `admin`, `gdpr_officer`, or `legal`
role — protect `CORTEX_API_KEYS` accordingly, since anyone who can obtain one
of those roles can erase organizational memory.

## Data Handled

Cortex ingests and stores organizational data pulled from connected tools
(Slack messages, GitHub PRs/commits, Jira issues, Linear issues), including
author emails/usernames and message content, across Neo4j, TimescaleDB,
Qdrant, Redis, and PostgreSQL. Raw connector content may be sent to an LLM
provider (OpenAI, or a local Ollama instance) for decision extraction and
CMVK verification — no redaction is applied before this step, so avoid
connecting sources containing data you don't want sent to your configured
LLM provider.

## Reporting Non-Security Bugs

For non-security bugs, please use the normal GitHub issue tracker.
