import { useEffect, useState } from "react";

const apiBase = import.meta.env.VITE_API_URL ?? "";

type Health = {
  status: string;
  version: string;
  uptime_seconds: number;
  dependencies: Record<string, string>;
};

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const url = `${apiBase}/health`;
    fetch(url)
      .then((r) => {
        if (!r.ok) {
          throw new Error(`HTTP ${r.status}`);
        }
        return r.json();
      })
      .then((data: Health) => setHealth(data))
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main>
      <h1>Cortex</h1>
      <p>Organizational memory dashboard (Phase 6 preview).</p>

      <section className="card">
        <h2>API health</h2>
        {error && <p className="status-bad">Could not reach API: {error}</p>}
        {!error && !health && <p>Loading…</p>}
        {health && (
          <>
            <p>
              Status:{" "}
              <span className={health.status === "ok" ? "status-ok" : "status-bad"}>
                {health.status}
              </span>{" "}
              · v{health.version} · uptime {health.uptime_seconds}s
            </p>
            <pre>{JSON.stringify(health.dependencies, null, 2)}</pre>
          </>
        )}
      </section>

      <section className="card">
        <h2>Links</h2>
        <ul>
          <li>
            <a href={`${apiBase || ""}/docs`}>OpenAPI docs</a>
          </li>
          <li>
            <a href={`${apiBase || ""}/contradictions/pending?workspace_id=local-dev`}>
              Pending contradictions (GET)
            </a>
          </li>
        </ul>
      </section>
    </main>
  );
}
