import { useId, useState } from "react";
import { useApp } from "../../context/AppContext";
import { fetchHealth, hasApiKeyConfigured } from "../../api/client";
import { persistApiKey } from "../../lib/auth";
import { setClientApiKey } from "../../api/client";
import { useToast } from "../ui/Toast";

const PRESETS = ["local-dev", "acme-demo"] as const;

export function WorkspaceBar() {
  const { workspaceId, setWorkspaceId, apiKey, setApiKey, saveApiKey } = useApp();
  const { showToast } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testOk, setTestOk] = useState<boolean | null>(null);
  const keyInputId = useId();
  const secured = hasApiKeyConfigured();

  async function testConnection(): Promise<void> {
    setTesting(true);
    setTestOk(null);
    try {
      const health = await fetchHealth();
      const ok =
        health.status === "ok" &&
        health.dependencies?.neo4j === "ok" &&
        health.dependencies?.redis === "ok";
      setTestOk(ok);
      showToast(ok ? "API connection successful" : "API reachable but dependencies degraded");
    } catch {
      setTestOk(false);
      showToast("Could not reach API — check Connection settings");
    } finally {
      setTesting(false);
    }
  }

  function handleSave(): void {
    saveApiKey();
    showToast(apiKey.trim() ? "API key saved" : "API key cleared — open mode");
    void testConnection();
  }

  function handleClear(): void {
    setApiKey("");
    persistApiKey("");
    setClientApiKey("");
    setTestOk(null);
    showToast("API key cleared");
  }

  return (
    <section className="connection-bar" aria-label="Workspace and API connection">
      <div className="connection-bar__primary">
        <div className="connection-bar__workspace">
          <label className="connection-bar__label" htmlFor="workspace-input">
            Organization workspace
          </label>
          <div className="connection-bar__row">
            <input
              id="workspace-input"
              className="input connection-bar__input"
              value={workspaceId}
              onChange={(e) => setWorkspaceId(e.target.value)}
              placeholder="e.g. acme-engineering"
            />
            {PRESETS.map((w) => (
              <button
                key={w}
                type="button"
                className={`chip ${workspaceId === w ? "chip--active" : ""}`}
                onClick={() => setWorkspaceId(w)}
              >
                {w}
              </button>
            ))}
          </div>
        </div>

        <button
          type="button"
          className={`connection-bar__toggle btn btn--ghost ${expanded ? "connection-bar__toggle--open" : ""}`}
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          aria-controls="connection-settings"
        >
          <span
            className={`connection-bar__status ${secured ? "connection-bar__status--secured" : ""}`}
            aria-hidden
          >
            {secured ? "🔒" : "◇"}
          </span>
          Connection
        </button>
      </div>

      {expanded ? (
        <div id="connection-settings" className="connection-bar__settings panel panel--inset">
          <p className="connection-bar__hint muted">
            When the API requires authentication, add your key here. Keys stay in your browser
            unless you configure <code>VITE_CORTEX_API_KEY</code> at build time.
          </p>
          <label className="connection-bar__label" htmlFor={keyInputId}>
            API key
          </label>
          <div className="connection-bar__row">
            <input
              id={keyInputId}
              className="input connection-bar__input"
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Optional — required when API keys are enabled"
              autoComplete="off"
              spellCheck={false}
            />
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => setShowKey((v) => !v)}
              aria-pressed={showKey}
            >
              {showKey ? "Hide" : "Show"}
            </button>
            <button type="button" className="btn btn--primary" onClick={handleSave}>
              Save
            </button>
            <button type="button" className="btn btn--ghost" onClick={handleClear}>
              Clear
            </button>
          </div>
          <div className="connection-bar__row">
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => void testConnection()}
              disabled={testing}
            >
              {testing ? "Testing…" : "Test connection"}
            </button>
          </div>
          {secured ? (
            <p className="connection-bar__saved text-ok" role="status">
              Secured — requests include your API key.
            </p>
          ) : (
            <p className="connection-bar__saved muted" role="status">
              Open mode — no API key sent (public demo).
            </p>
          )}
          {testOk === true ? (
            <p className="connection-bar__saved text-ok" role="status">
              API health check passed.
            </p>
          ) : null}
          {testOk === false ? (
            <p className="connection-bar__saved text-warn" role="status">
              API unreachable — verify URL and credentials.
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
