import { useApp } from "../../context/AppContext";

const PRESETS = ["local-dev", "acme-demo"] as const;

export function WorkspaceBar() {
  const { workspaceId, setWorkspaceId } = useApp();

  return (
    <section className="workspace-bar" aria-label="Workspace">
      <label className="workspace-bar__label" htmlFor="workspace-input">
        Organization workspace
      </label>
      <div className="workspace-bar__row">
        <input
          id="workspace-input"
          className="input workspace-bar__input"
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
    </section>
  );
}
