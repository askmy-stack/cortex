import type { ViewId } from "../../types";
import { useApp } from "../../context/AppContext";

const ITEMS: { id: ViewId; label: string; icon: string }[] = [
  { id: "home", label: "Overview", icon: "⌂" },
  { id: "ask", label: "Search", icon: "?" },
  { id: "explore", label: "Map", icon: "◎" },
  { id: "agents", label: "AI", icon: "⚡" },
  { id: "review", label: "Review", icon: "⚖" },
];

/** Bottom tab bar for phone/tablet — primary navigation on small screens. */
export function MobileNav() {
  const { view, setView, setAssistantOpen } = useApp();

  return (
    <nav className="mobile-nav" aria-label="Mobile navigation">
      {ITEMS.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`mobile-nav__item ${view === item.id ? "mobile-nav__item--active" : ""}`}
          onClick={() => setView(item.id)}
          aria-current={view === item.id ? "page" : undefined}
        >
          <span className="mobile-nav__icon" aria-hidden>
            {item.icon}
          </span>
          <span className="mobile-nav__label">{item.label}</span>
        </button>
      ))}
      <button
        type="button"
        className="mobile-nav__item mobile-nav__item--copilot"
        onClick={() => setAssistantOpen(true)}
        aria-label="Open Cortex Assist"
      >
        <span className="mobile-nav__icon" aria-hidden>
          ✦
        </span>
        <span className="mobile-nav__label">Assist</span>
      </button>
    </nav>
  );
}
