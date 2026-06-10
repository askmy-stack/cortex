import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { queryMemory } from "../../api/client";
import { useApp } from "../../context/AppContext";
import { summarizeQueryResults } from "../../lib/assistant";
import { isUnauthorizedMessage } from "../../lib/auth";
import { TypingIndicator } from "../ui/TypingIndicator";

function renderMarkdownLite(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    return part;
  });
}

function formatTimestamp(ms: number): string {
  try {
    return new Date(ms).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

const NAV_PATTERNS = [
  { test: (q: string) => q.includes("what is cortex") || q.includes("what does cortex"), kind: "about" as const },
  { test: (q: string) => q.includes("graph") || q.includes("map") || q.includes("explore"), kind: "explore" as const },
  { test: (q: string) => q === "search" || q === "ask" || q.startsWith("go to ask"), kind: "ask-nav" as const },
];

export function AssistantPanel() {
  const {
    assistantOpen,
    setAssistantOpen,
    messages,
    pushMessage,
    setView,
    workspaceId,
    setLastQuery,
    setExploreDecisions,
    setSelectedDecisionId,
  } = useApp();
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const thinkingTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  useEffect(() => {
    return () => {
      if (thinkingTimer.current !== undefined) window.clearTimeout(thinkingTimer.current);
    };
  }, []);

  useEffect(() => {
    if (!assistantOpen) return;
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAssistantOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [assistantOpen, setAssistantOpen]);

  const runQuery = useCallback(
    async (q: string) => {
      const result = await queryMemory({
        query: q,
        workspace_id: workspaceId.trim() || "local-dev",
        limit: 6,
      });
      setLastQuery(result);
      setExploreDecisions(result.results);
      if (result.results[0]) setSelectedDecisionId(result.results[0].event_id);
      pushMessage("assistant", summarizeQueryResults(result));
      if (result.total > 0) setView("ask");
    },
    [workspaceId, pushMessage, setLastQuery, setExploreDecisions, setSelectedDecisionId, setView],
  );

  const handleAsk = useCallback(() => {
    const q = draft.trim();
    if (!q) return;
    pushMessage("user", q);
    setDraft("");
    setThinking(true);

    if (thinkingTimer.current !== undefined) window.clearTimeout(thinkingTimer.current);

    const lower = q.toLowerCase();
    const nav = NAV_PATTERNS.find((p) => p.test(lower));

    if (nav?.kind === "about") {
      thinkingTimer.current = window.setTimeout(() => {
        pushMessage(
          "assistant",
          "Cortex is your **organizational memory** — it captures *decisions* (not documents) from Slack, GitHub, Jira, and more, then makes them searchable for humans and AI agents. Go to **Ask** to query your institutional knowledge.",
        );
        setThinking(false);
      }, 200);
      return;
    }

    if (nav?.kind === "explore") {
      thinkingTimer.current = window.setTimeout(() => {
        pushMessage(
          "assistant",
          "Opening **Memory map** to see relationships between people, systems, and decisions.",
        );
        setView("explore");
        setThinking(false);
      }, 200);
      return;
    }

    if (nav?.kind === "ask-nav") {
      thinkingTimer.current = window.setTimeout(() => {
        pushMessage(
          "assistant",
          "Opening **Ask** — type a question like *Why CockroachDB for payments?* and I'll summarize what we find.",
        );
        setView("ask");
        setThinking(false);
      }, 200);
      return;
    }

    if (q.length < 3) {
      thinkingTimer.current = window.setTimeout(() => {
        pushMessage("assistant", "Please ask at least 3 characters — or try an example on the **Ask** page.");
        setThinking(false);
      }, 200);
      return;
    }

    void runQuery(q)
      .catch((e) => {
        const msg = e instanceof Error ? e.message : String(e);
        pushMessage(
          "assistant",
          isUnauthorizedMessage(msg)
            ? `${msg}\n\nOpen **Connection** in any view and save your API key.`
            : `Search failed: ${msg}`,
        );
      })
      .finally(() => setThinking(false));
  }, [draft, pushMessage, setView, runQuery]);

  if (!assistantOpen) {
    return (
      <button
        type="button"
        className="assistant-fab"
        onClick={() => setAssistantOpen(true)}
        aria-label="Open Cortex guide"
      >
        <span aria-hidden>✦</span> Guide
      </button>
    );
  }

  return (
    <>
      <button
        type="button"
        className="assistant-backdrop"
        aria-label="Close guide"
        onClick={() => setAssistantOpen(false)}
      />
      <aside className="assistant-panel" aria-label="Cortex guide" role="complementary">
        <header className="assistant-panel__head">
          <div>
            <h2>Cortex Guide</h2>
            <p>Ask questions — I'll search organizational memory</p>
          </div>
          <button
            type="button"
            className="btn-icon"
            onClick={() => setAssistantOpen(false)}
            aria-label="Close guide"
          >
            ×
          </button>
        </header>
        <div className="assistant-panel__messages" role="log" aria-live="polite">
          {messages.map((m) => (
            <article
              key={m.id}
              className={`assistant-msg assistant-msg--${m.role}`}
              title={formatTimestamp(m.timestamp)}
            >
              {renderMarkdownLite(m.content)}
            </article>
          ))}
          {thinking ? (
            <article className="assistant-msg assistant-msg--assistant">
              <TypingIndicator />
            </article>
          ) : null}
          <div ref={endRef} />
        </div>
        <footer className="assistant-panel__foot">
          <input
            ref={inputRef}
            type="text"
            className="input"
            placeholder="e.g. Why CockroachDB for payments?"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAsk()}
            aria-label="Message to Cortex guide"
          />
          <button
            type="button"
            className="btn btn--primary"
            onClick={handleAsk}
            disabled={!draft.trim() || thinking}
          >
            Send
          </button>
        </footer>
      </aside>
    </>
  );
}
