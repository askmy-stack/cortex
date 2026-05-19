import { useCallback, useEffect, useState } from "react";
import { fetchHealth } from "../api/client";
import type { Health } from "../types";
import { useApp } from "../context/AppContext";

export function HomeView() {
  const { setView, pushMessage } = useApp();
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setHealth(await fetchHealth());
    } catch (e) {
      setHealth(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <article className="view view--home fade-in">
      <header className="hero">
        <p className="hero__eyebrow">Organizational intelligence</p>
        <h1 className="hero__title">
          Remember <em>why</em> your team decided — not just what happened.
        </h1>
        <p className="hero__lead">
          Cortex captures decisions from Slack, GitHub, Jira, and more — then makes that
          institutional knowledge searchable for people and AI agents.
        </p>
        <div className="hero__actions">
          <button type="button" className="btn btn--primary btn--lg" onClick={() => setView("ask")}>
            Ask a question
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              pushMessage("assistant", "Cortex stores **decisions** with who made them, which systems they affect, and why — so you never lose context when people leave or tools change.");
            }}
          >
            How it works
          </button>
        </div>
      </header>

      <section className="card-grid">
        <article className="info-card">
          <span className="info-card__icon" aria-hidden>◈</span>
          <h3>Capture</h3>
          <p>Events flow in from your tools and become structured decision memories.</p>
        </article>
        <article className="info-card">
          <span className="info-card__icon" aria-hidden>◎</span>
          <h3>Connect</h3>
          <p>People, systems, and rationale link together in a living knowledge graph.</p>
        </article>
        <article className="info-card">
          <span className="info-card__icon" aria-hidden>⚡</span>
          <h3>Inject</h3>
          <p>AI agents receive the right context automatically — before they guess.</p>
        </article>
      </section>

      <section className="panel">
        <header className="panel__head">
          <h2>System health</h2>
          <button type="button" className="btn btn--secondary" onClick={() => void load()} disabled={loading}>
            {loading ? "Checking…" : "Refresh"}
          </button>
        </header>
        {error ? (
          <p className="alert alert--error">
            Cannot reach the API. Run <code>make demo</code> and ensure the API is on port 8000.
            <br />
            <small>{error}</small>
          </p>
        ) : null}
        {health ? (
          <ul className="health-strip">
            <li>
              <span>API</span>
              <strong className={health.status === "ok" ? "text-ok" : "text-bad"}>{health.status}</strong>
            </li>
            <li>
              <span>Version</span>
              <strong>{health.version}</strong>
            </li>
            <li>
              <span>Uptime</span>
              <strong>{Math.round(health.uptime_seconds)}s</strong>
            </li>
            {Object.entries(health.dependencies).map(([k, v]) => (
              <li key={k}>
                <span>{k}</span>
                <strong className={v === "ok" ? "text-ok" : "text-bad"}>{v}</strong>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </article>
  );
}
