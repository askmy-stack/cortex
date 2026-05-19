import type {
  CausalChainResponse,
  ContradictionItem,
  Health,
  InjectResponse,
  QueryResponse,
} from "../types";

const DEFAULT_API_BASE = "http://localhost:8000";

export const apiBase =
  String(import.meta.env.VITE_API_URL ?? "")
    .trim()
    .replace(/\/$/, "") || DEFAULT_API_BASE;

async function parseError(response: Response): Promise<string> {
  const detail = await response.text();
  return `Request failed (${response.status}): ${detail.slice(0, 200)}`;
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
    headers: { "Content-Type": "application/json" },
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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<InjectResponse>;
}

export async function fetchContradictions(workspaceId: string): Promise<ContradictionItem[]> {
  const ws = encodeURIComponent(workspaceId);
  const response = await fetch(`${apiBase}/contradictions/pending?workspace_id=${ws}`);
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
  const response = await fetch(`${apiBase}/decisions/${decisionId}/chain?${params}`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<CausalChainResponse>;
}

export async function fetchBySystem(
  systemId: string,
  workspaceId: string,
  limit = 10,
): Promise<import("../types").DecisionResult[]> {
  const params = new URLSearchParams({ workspace_id: workspaceId, limit: String(limit) });
  const response = await fetch(`${apiBase}/decisions/by-system/${encodeURIComponent(systemId)}?${params}`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<import("../types").DecisionResult[]>;
}
