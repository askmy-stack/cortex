import type { ViewId } from "../../types";
import { useApp } from "../../context/AppContext";
import {
  IconAgent,
  IconGraph,
  IconHome,
  IconReview,
  IconSearch,
  IconSpark,
} from "../ui/icons";

const ITEMS: { id: ViewId; label: string; Icon: typeof IconHome }[] = [
  { id: "home", label: "Overview", Icon: IconHome },
  { id: "ask", label: "Search", Icon: IconSearch },
  { id: "explore", label: "Map", Icon: IconGraph },
  { id: "agents", label: "AI", Icon: IconAgent },
  { id: "review", label: "Review", Icon: IconReview },
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
          aria-label={item.label}
        >
          <span className="mobile-nav__icon" aria-hidden>
            <item.Icon size={20} />
          </span>
          <span className="mobile-nav__label">{item.label}</span>
        </button>
      ))}
      <button
        type="button"
        className="mobile-nav__item mobile-nav__item--assist"
        onClick={() => setAssistantOpen(true)}
        aria-label="Open Cortex Assist"
      >
        <span className="mobile-nav__icon" aria-hidden>
          <IconSpark size={20} />
        </span>
        <span className="mobile-nav__label">Assist</span>
      </button>
    </nav>
  );
}
