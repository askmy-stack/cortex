export type Health = {
  status: string;
  version: string;
  uptime_seconds: number;
  dependencies: Record<string, string>;
};

export type DecisionResult = {
  event_id: string;
  event_type: string;
  content: string;
  made_by: string[];
  affects: string[];
  rationale: string[];
  importance_score: number;
  trust_score: number;
  extraction_confidence: number;
  source: string;
  channel: string;
  extracted_at: string;
  status: string;
  supersedes_ids?: string[];
  triggered_by_id?: string | null;
};

export type QueryResponse = {
  query: string;
  workspace_id: string;
  results: DecisionResult[];
  total: number;
  latency_ms: number;
  coverage_score?: number;
};

export type InjectResponse = {
  agent_id: string;
  workspace_id: string;
  injected_decisions: DecisionResult[];
  context_summary: string;
  token_estimate: number;
  latency_ms: number;
};

export type ContradictionItem = {
  id: string;
  score: number;
  explanation: string;
  new_decision_id: string | null;
  prior_decision_id: string | null;
  status: string;
};

export type CausalChainResponse = {
  decision_id: string;
  workspace_id: string;
  nodes: DecisionResult[];
  total: number;
};

export type ViewId = "home" | "ask" | "explore" | "agents" | "review";

export type AssistantMessage = {
  id: string;
  role: "assistant" | "user" | "system";
  content: string;
  timestamp: number;
};
