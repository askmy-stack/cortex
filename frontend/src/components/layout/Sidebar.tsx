import type { ViewId } from "../../types";
import { useApp } from "../../context/AppContext";

const NAV: { id: ViewId; label: string; hint: string; icon: string }[] = [
  { id: "home", label: "Overview", hint: "Executive summary", icon: "⌂" },
  { id: "ask", label: "Search", hint: "Ask memory", icon: "?" },
  { id: "explore", label: "Memory map", hint: "Connections & lineage", icon: "◎" },
  { id: "agents", label: "AI agents", hint: "Inject & capture", icon: "⚡" },
  { id: "review", label: "Conflicts", hint: "Human review", icon: "⚖" },
];

export function Sidebar() {
  const { view, setView } = useApp();

  return (
    <nav className="sidebar" aria-label="Main navigation">
      <div className="sidebar__brand">
        <span className="sidebar__brand-label">Intelligence</span>
        <span className="sidebar__brand-title">Cortex</span>
      </div>
      <ul className="sidebar__list">
        {NAV.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className={`sidebar__link ${view === item.id ? "sidebar__link--active" : ""}`}
              onClick={() => setView(item.id)}
              aria-current={view === item.id ? "page" : undefined}
            >
              <span className="sidebar__icon" aria-hidden>
                {item.icon}
              </span>
              <span className="sidebar__text">
                <span className="sidebar__label">{item.label}</span>
                <span className="sidebar__hint">{item.hint}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
