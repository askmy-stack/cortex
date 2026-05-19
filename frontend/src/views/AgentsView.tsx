import { useState } from "react";
import { injectContext } from "../api/client";
import { useApp } from "../context/AppContext";
import { injectSummary } from "../lib/assistant";
import { DecisionCard } from "../components/memory/DecisionCard";
import { WorkspaceBar } from "../components/layout/WorkspaceBar";
import { Skeleton } from "../components/ui/Skeleton";
import { StateView } from "../components/ui/StateView";

export function AgentsView() {
  const { workspaceId, pushMessage } = useApp();
  const [context, setContext] = useState(
    "I'm implementing checkout improvements for payments-service and need organizational context on database and cache choices.",
  );
  const [agentId, setAgentId] = useState("cursor-agent");
  const [maxTokens, setMaxTokens] = useState(4000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Awaited<ReturnType<typeof injectContext>> | null>(null);

  async function run() {
    if (context.trim().length < 10) {
      setError("Describe the agent's task in at least 10 characters.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await injectContext({
        context: context.trim(),
        workspace_id: workspaceId.trim() || "local-dev",
        agent_id: agentId.trim() || "agent",
        max_tokens: maxTokens,
      });
      setResult(res);
      pushMessage(
        "assistant",
        injectSummary(res.injected_decisions.length, res.context_summary, res.token_estimate),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <article className="view view--agents fade-in">
      <header className="view__header">
        <h1>For AI agents</h1>
        <p className="view__subtitle">
          Simulate what Cortex injects into Cursor, Claude, or any MCP-connected agent before they act.
        </p>
      </header>

      <WorkspaceBar />

      <section className="panel">
        <label className="field-label" htmlFor="agent-id">
          Agent identifier
        </label>
        <input
          id="agent-id"
          className="input"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
        />

        <label className="field-label" htmlFor="agent-ctx">
          What is the agent working on?
        </label>
        <textarea
          id="agent-ctx"
          className="textarea"
          rows={5}
          value={context}
          onChange={(e) => setContext(e.target.value)}
        />

        <label className="field-label" htmlFor="tok">
          Context budget: {maxTokens} tokens
        </label>
        <input
          id="tok"
          type="range"
          min={400}
          max={16000}
          step={200}
          value={maxTokens}
          onChange={(e) => setMaxTokens(Number(e.target.value))}
        />

        <button type="button" className="btn btn--primary" onClick={() => void run()} disabled={loading}>
          {loading ? "Preparing context…" : "Preview injection"}
        </button>
      </section>

      {error ? (
        <StateView tone="error" icon="!" title="Injection failed">
          {error}
        </StateView>
      ) : null}

      {loading && !result ? (
        <section className="panel" aria-live="polite">
          <h2>
            <Skeleton variant="title" />
          </h2>
          <Skeleton variant="row" />
          <Skeleton variant="card" />
          <Skeleton variant="card" />
        </section>
      ) : null}

      {result ? (
        <section className="panel fade-in" aria-live="polite">
          <h2>What the agent would see</h2>
          {result.injected_decisions.length === 0 ? (
            <StateView icon="◇" title="No matching memory">
              Cortex didn't find decisions that match this context yet — try a more specific
              prompt or seed more memories.
            </StateView>
          ) : (
            <>
              <blockquote className="inject-summary">{result.context_summary}</blockquote>
              <p className="muted">
                ~{result.token_estimate} tokens · {result.latency_ms}ms
              </p>
              <div className="decision-list">
                {result.injected_decisions.map((d, i) => (
                  <DecisionCard key={d.event_id} decision={d} defaultOpen={i === 0} />
                ))}
              </div>
            </>
          )}
        </section>
      ) : null}
    </article>
  );
}
