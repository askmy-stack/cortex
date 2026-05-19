import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const apiBaseUrl = process.env.CORTEX_API_URL ?? "http://localhost:8000";

const server = new McpServer({
  name: "cortex",
  version: "0.1.0",
});

async function postJson(path, body) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-cortex-roles": process.env.CORTEX_CALLER_ROLES ?? "authenticated",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Cortex API ${path} failed with ${response.status}`);
  }
  return response.json();
}

server.tool(
  "cortex_query",
  {
    description: "Query organizational memory",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string" },
        workspace_id: { type: "string" },
        limit: { type: "number" },
      },
      required: ["query", "workspace_id"],
    },
  },
  async ({ query, workspace_id, limit = 10 }) => {
    const payload = await postJson("/query", { query, workspace_id, limit });
    return {
      content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
    };
  },
);

server.tool(
  "cortex_remember",
  {
    description: "Submit explicit organizational memory into the ingestion pipeline",
    inputSchema: {
      type: "object",
      properties: {
        content: { type: "string" },
        workspace_id: { type: "string" },
        author: { type: "string" },
        affects: { type: "array", items: { type: "string" } },
      },
      required: ["content", "workspace_id"],
    },
  },
  async ({ content, workspace_id, author = "mcp-agent", affects = [] }) => {
    const payload = await postJson("/remember", {
      content,
      workspace_id,
      author,
      affects,
    });
    return {
      content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
    };
  },
);

server.tool(
  "cortex_inject",
  {
    description: "Inject relevant organizational memory into agent context",
    inputSchema: {
      type: "object",
      properties: {
        context: { type: "string" },
        workspace_id: { type: "string" },
        agent_id: { type: "string" },
        max_tokens: { type: "number" },
      },
      required: ["context", "workspace_id", "agent_id"],
    },
  },
  async ({ context, workspace_id, agent_id, max_tokens = 4000 }) => {
    const payload = await postJson("/inject", {
      context,
      workspace_id,
      agent_id,
      max_tokens,
    });
    return {
      content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
    };
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
