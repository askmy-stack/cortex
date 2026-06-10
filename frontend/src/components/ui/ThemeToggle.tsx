import { useEffect, useState } from "react";
import { applyTheme, loadTheme, persistTheme, type ThemeMode } from "../../lib/theme";

export function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(() =>
    typeof window === "undefined" ? "dark" : loadTheme(),
  );

  useEffect(() => {
    applyTheme(mode);
  }, [mode]);

  function toggle() {
    const next: ThemeMode = mode === "dark" ? "light" : "dark";
    persistTheme(next);
    setMode(next);
  }

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      title={mode === "dark" ? "Light mode" : "Dark mode"}
    >
      {mode === "dark" ? "☀" : "☾"}
    </button>
  );
}
