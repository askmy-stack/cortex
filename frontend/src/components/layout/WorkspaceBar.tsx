import { useId, useState } from "react";
import { useApp } from "../../context/AppContext";
import { hasApiKeyConfigured } from "../../api/client";

const PRESETS = ["local-dev", "acme-demo"] as const;

export function WorkspaceBar() {
  const { workspaceId, setWorkspaceId, apiKey, setApiKey, saveApiKey } = useApp();
  const [expanded, setExpanded] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const keyInputId = useId();
  const secured = hasApiKeyConfigured();

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
              placeholder="e.g. local-dev"
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
            When the API has <code>CORTEX_API_KEYS</code> set, add a key here. Keys stay in your
            browser (localStorage) unless you set <code>VITE_CORTEX_API_KEY</code> at build time.
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
              placeholder="sk_… (optional in open dev mode)"
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
            <button type="button" className="btn btn--primary" onClick={() => saveApiKey()}>
              Save
            </button>
          </div>
          {secured ? (
            <p className="connection-bar__saved text-ok" role="status">
              Secured — requests include your API key.
            </p>
          ) : (
            <p className="connection-bar__saved muted" role="status">
              Open mode — no API key sent (fine for local <code>make demo</code>).
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}
