import type { ViewId } from "../../types";
import { useApp } from "../../context/AppContext";

const NAV: { id: ViewId; label: string; hint: string; icon: string }[] = [
  { id: "home", label: "Home", hint: "Welcome & status", icon: "⌂" },
  { id: "ask", label: "Ask", hint: "Search memory", icon: "?" },
  { id: "explore", label: "Memory map", hint: "Graph & timeline", icon: "◎" },
  { id: "agents", label: "For agents", hint: "Context injection", icon: "⚡" },
  { id: "review", label: "Review", hint: "Contradictions", icon: "⚖" },
];

export function Sidebar() {
  const { view, setView } = useApp();

  return (
  <nav className="sidebar" aria-label="Main navigation">
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
