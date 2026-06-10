import type {
  CausalChainResponse,
  ContradictionItem,
  DecisionResult,
  Health,
  InjectResponse,
  QueryResponse,
} from "../types";
import { authHeaders, loadStoredApiKey, resolveApiKey } from "../lib/auth";

// Empty base = same-origin requests (e.g. `/query`). In dev the Vite proxy and
// in prod the nginx reverse proxy forward these to the API, so the dashboard
// works wherever it is hosted. Set VITE_API_URL only to target a remote API.
export const apiBase = String(import.meta.env.VITE_API_URL ?? "")
  .trim()
  .replace(/\/$/, "");

let _apiKeyOverride = "";

/** Called from AppContext when the user updates the Connection settings. */
export function setClientApiKey(key: string): void {
  _apiKeyOverride = key;
}

function effectiveApiKey(): string {
  return resolveApiKey(_apiKeyOverride || loadStoredApiKey());
}

function requestHeaders(): Record<string, string> {
  return authHeaders(effectiveApiKey());
}

/** Surface upstream HTTP status + a trimmed body so the UI can show useful errors. */
async function parseError(response: Response): Promise<string> {
  let detail = "";
  try {
    detail = await response.text();
  } catch {
    detail = "";
  }
  const status = `${response.status} ${response.statusText || ""}`.trim();
  if (response.status === 401) {
    return (
      "Authentication required (401). Add your API key in Connection settings " +
      "(top of Ask, Agents, or Review). When CORTEX_API_KEYS is set on the server, " +
      "requests without a valid key are rejected."
    );
  }
  if (!detail) return `Request failed (${status})`;
  return `Request failed (${status}): ${detail.slice(0, 200)}`;
}

export async function fetchHealth(): Promise<Health> {
  const response = await fetch(`${apiBase}/health`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<Health>;
}

export async function queryMemory(body: {
  query: string;
  workspace_id: string;
  limit: number;
}): Promise<QueryResponse> {
  const response = await fetch(`${apiBase}/query`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<QueryResponse>;
}

export async function injectContext(body: {
  context: string;
  workspace_id: string;
  agent_id: string;
  max_tokens: number;
}): Promise<InjectResponse> {
  const response = await fetch(`${apiBase}/inject`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<InjectResponse>;
}

export async function rememberMemory(body: {
  content: string;
  workspace_id: string;
  author?: string;
  affects?: string[];
}): Promise<{ status: string; event_id: string; topic: string }> {
  const response = await fetch(`${apiBase}/remember`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify({
      author: "dashboard-user",
      affects: [],
      ...body,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<{ status: string; event_id: string; topic: string }>;
}

export async function fetchContradictions(workspaceId: string): Promise<ContradictionItem[]> {
  const ws = encodeURIComponent(workspaceId);
  const response = await fetch(`${apiBase}/contradictions/pending?workspace_id=${ws}`, {
    headers: requestHeaders(),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<ContradictionItem[]>;
}

export async function fetchCausalChain(
  decisionId: string,
  workspaceId: string,
  maxDepth = 4,
): Promise<CausalChainResponse> {
  const params = new URLSearchParams({
    workspace_id: workspaceId,
    max_depth: String(maxDepth),
  });
  const response = await fetch(`${apiBase}/decisions/${decisionId}/chain?${params}`, {
    headers: requestHeaders(),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<CausalChainResponse>;
}

export async function fetchBySystem(
  systemId: string,
  workspaceId: string,
  limit = 10,
): Promise<DecisionResult[]> {
  const params = new URLSearchParams({ workspace_id: workspaceId, limit: String(limit) });
  const response = await fetch(
    `${apiBase}/decisions/by-system/${encodeURIComponent(systemId)}?${params}`,
    { headers: requestHeaders() },
  );
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<DecisionResult[]>;
}

/** Whether the dashboard will send an API key on protected routes. */
export function hasApiKeyConfigured(): boolean {
  return Boolean(effectiveApiKey());
}
