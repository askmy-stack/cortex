import type { ViewId } from "../../types";
import { useApp } from "../../context/AppContext";
import {
  IconAgent,
  IconGraph,
  IconHome,
  IconReview,
  IconSearch,
} from "../ui/icons";

const NAV: { id: ViewId; label: string; hint: string; Icon: typeof IconHome }[] = [
  { id: "home", label: "Overview", hint: "Executive summary", Icon: IconHome },
  { id: "ask", label: "Search", hint: "Ask memory", Icon: IconSearch },
  { id: "explore", label: "Memory map", hint: "Connections & lineage", Icon: IconGraph },
  { id: "agents", label: "AI agents", hint: "Inject & capture", Icon: IconAgent },
  { id: "review", label: "Conflicts", hint: "Human review", Icon: IconReview },
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
              aria-label={`${item.label} — ${item.hint}`}
            >
              <span className="sidebar__icon" aria-hidden>
                <item.Icon size={18} />
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
