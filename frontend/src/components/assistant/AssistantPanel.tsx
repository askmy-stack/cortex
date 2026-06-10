import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { queryMemory } from "../../api/client";
import { useApp } from "../../context/AppContext";
import { COPILOT_SUGGESTIONS, summarizeQueryResults } from "../../lib/assistant";
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
  {
    test: (q: string) => q.includes("what is cortex") || q.includes("what does cortex"),
    kind: "about" as const,
  },
  {
    test: (q: string) => q.includes("graph") || q.includes("map") || q.includes("explore"),
    kind: "explore" as const,
  },
  {
    test: (q: string) => q === "search" || q === "ask" || q.startsWith("go to ask"),
    kind: "ask-nav" as const,
  },
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
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setAssistantOpen(!assistantOpen);
      }
      if (e.key === "Escape" && assistantOpen) setAssistantOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [assistantOpen, setAssistantOpen]);

  useEffect(() => {
    if (assistantOpen) inputRef.current?.focus();
  }, [assistantOpen]);

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

  const submit = useCallback(
    (raw: string) => {
      const q = raw.trim();
      if (!q || thinking) return;
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
            "Cortex is your **organizational memory** — it captures *decisions* (not documents) from Slack, GitHub, Jira, and more, then makes them searchable for humans and AI agents.\n\nI can search memory, explain results, and guide you to the memory map.",
          );
          setThinking(false);
        }, 200);
        return;
      }

      if (nav?.kind === "explore") {
        thinkingTimer.current = window.setTimeout(() => {
          pushMessage("assistant", "Opening the **memory map** — relationships between people, systems, and decisions.");
          setView("explore");
          setThinking(false);
        }, 200);
        return;
      }

      if (nav?.kind === "ask-nav") {
        thinkingTimer.current = window.setTimeout(() => {
          pushMessage("assistant", "Taking you to **Search** — ask anything about past decisions.");
          setView("ask");
          setThinking(false);
        }, 200);
        return;
      }

      if (q.length < 3) {
        thinkingTimer.current = window.setTimeout(() => {
          pushMessage("assistant", "Please use at least 3 characters — or tap a suggestion below.");
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
              ? `${msg}\n\nOpen **Connection** settings and save your API key.`
              : `I couldn't search memory: ${msg}`,
          );
        })
        .finally(() => setThinking(false));
    },
    [thinking, pushMessage, setView, runQuery],
  );

  if (!assistantOpen) {
    return (
      <button
        type="button"
        className="assistant-fab"
        onClick={() => setAssistantOpen(true)}
        aria-label="Open Cortex Copilot"
        title="Cortex Copilot (⌘K)"
      >
        <span aria-hidden>✦</span> Copilot
      </button>
    );
  }

  return (
    <>
      <button
        type="button"
        className="assistant-backdrop"
        aria-label="Close Copilot"
        onClick={() => setAssistantOpen(false)}
      />
      <aside className="assistant-panel" aria-label="Cortex Copilot" role="complementary">
        <header className="assistant-panel__head">
          <div className="assistant-panel__brand">
            <span className="copilot-avatar" aria-hidden>
              C
            </span>
            <div>
              <h2>Cortex Copilot</h2>
              <p>Search memory · explain decisions · guide your next step</p>
            </div>
          </div>
          <button
            type="button"
            className="btn-icon"
            onClick={() => setAssistantOpen(false)}
            aria-label="Close Copilot"
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
              {m.role === "assistant" ? (
                <span className="copilot-avatar" aria-hidden>
                  C
                </span>
              ) : null}
              <div className="assistant-msg__bubble">{renderMarkdownLite(m.content)}</div>
            </article>
          ))}
          {thinking ? (
            <article className="assistant-msg assistant-msg--assistant">
              <span className="copilot-avatar" aria-hidden>
                C
              </span>
              <div className="assistant-msg__bubble">
                <TypingIndicator />
              </div>
            </article>
          ) : null}
          <div ref={endRef} />
        </div>
        <div className="copilot-suggestions" role="group" aria-label="Suggested questions">
          {COPILOT_SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              className="copilot-suggestion"
              onClick={() => submit(s)}
              disabled={thinking}
            >
              {s}
            </button>
          ))}
        </div>
        <footer className="assistant-panel__foot">
          <input
            ref={inputRef}
            type="text"
            className="input"
            placeholder="Ask about a decision, system, or person…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit(draft)}
            aria-label="Message Cortex Copilot"
          />
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => submit(draft)}
            disabled={!draft.trim() || thinking}
          >
            Send
          </button>
        </footer>
      </aside>
    </>
  );
}
