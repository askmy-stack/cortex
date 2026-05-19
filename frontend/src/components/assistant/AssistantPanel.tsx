import { useEffect, useRef, useState, type ReactNode } from "react";
import { useApp } from "../../context/AppContext";

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

export function AssistantPanel() {
  const { assistantOpen, setAssistantOpen, messages, pushMessage, setView } = useApp();
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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

  function handleAsk() {
    const q = draft.trim();
    if (!q) return;
    pushMessage("user", q);
    setDraft("");
    const lower = q.toLowerCase();
    if (lower.includes("what is cortex") || lower.includes("what does cortex")) {
      pushMessage(
        "assistant",
        "Cortex is your **organizational memory** — it captures *decisions* (not documents) from Slack, GitHub, Jira, and more, then makes them searchable for humans and AI agents. Go to **Ask** to query your institutional knowledge.",
      );
    } else if (lower.includes("search") || lower.includes("ask")) {
      pushMessage("assistant", "Opening **Ask** — type a question like *Why CockroachDB for payments?* and I'll summarize what we find.");
      setView("ask");
    } else if (lower.includes("graph") || lower.includes("map")) {
      pushMessage("assistant", "Open **Memory map** to see relationships between people, systems, and decisions.");
      setView("explore");
    } else {
      pushMessage(
        "assistant",
        "Try asking on the **Ask** page, or pick an example question. I can explain results in plain language after you search.",
      );
      setView("ask");
    }
  }

  return (
    <aside className="assistant-panel" aria-label="Cortex guide">
      <header className="assistant-panel__head">
        <div>
          <h2>Cortex Guide</h2>
          <p>Your companion for organizational memory</p>
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
          >
            {renderMarkdownLite(m.content)}
          </article>
        ))}
        <div ref={endRef} />
      </div>
      <footer className="assistant-panel__foot">
        <input
          type="text"
          className="input"
          placeholder="What would you like to know?"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          aria-label="Message to Cortex guide"
        />
        <button type="button" className="btn btn--primary" onClick={handleAsk}>
          Send
        </button>
      </footer>
    </aside>
  );
}
