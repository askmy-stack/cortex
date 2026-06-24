# Wire Cortex MCP in 60 seconds

Cortex ships a **stdio MCP server** that calls your live API (`POST /query`, `POST /inject`). Agents get organizational memory without custom integration code.

## Prerequisites

- Node.js 18+
- A running Cortex API (local `make demo`, or production Railway URL)

## Cursor / Claude Desktop config

Add to your MCP settings (Cursor: **Settings → MCP**, or `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "cortex": {
      "command": "node",
      "args": ["/absolute/path/to/Cortex/mcp/server.js"],
      "env": {
        "CORTEX_API_URL": "https://cortex-api-production-fbd5.up.railway.app",
        "CORTEX_API_KEY": ""
      }
    }
  }
}
```

For **local** development:

```json
"CORTEX_API_URL": "http://localhost:8000"
```

When the cloud API uses optional auth, set `CORTEX_API_KEY` to your read-only demo key (see [DEPLOY.md](./DEPLOY.md)).

## Available tools

| Tool | Purpose |
|------|---------|
| `cortex_query` | Natural-language search over organizational decisions |
| `cortex_remember` | Submit explicit memory into the ingestion pipeline |
| `cortex_inject` | Active context injection for an agent prompt |

## Verify

1. Restart Cursor after saving MCP config.
2. In chat, ask the agent to call `cortex_query` with workspace `local-dev` and query *Why CockroachDB for payments?*
3. You should see structured decision JSON — not raw Slack threads.

## Architecture note (interviews)

```text
Your IDE agent → MCP (stdio) → Cortex API → Neo4j graph (+ Redis cache)
```

The MCP server is **agent-neutral** — any MCP-compatible client works. Cloud v1 deploys the API only; MCP runs beside your agent locally (zero extra Railway cost).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `401 Unauthorized` | Set `CORTEX_API_KEY` or remove keys on API for open demo |
| `503` / connection refused | Check `CORTEX_API_URL`; Railway free tier may cold-start ~30s |
| Empty results | Confirm workspace id (`local-dev` on cloud seed) |

See also: [README.md](../README.md), [PORTFOLIO_DEMO.md](./PORTFOLIO_DEMO.md).
