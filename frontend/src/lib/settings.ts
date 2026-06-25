const STORAGE_KEY = "cortex_settings_v2";

export type CortexSettings = {
  onboardingComplete: boolean;
  workspaceId: string;
};

const DEFAULTS: CortexSettings = {
  onboardingComplete: false,
  workspaceId: "local-dev",
};

export function loadSettings(): CortexSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      const legacyOnboarding = localStorage.getItem("cortex_onboarding_v1") === "done";
      const legacyWorkspace = localStorage.getItem("cortex_workspace_id")?.trim();
      return {
        onboardingComplete: legacyOnboarding,
        workspaceId: legacyWorkspace || DEFAULTS.workspaceId,
      };
    }
    const parsed = JSON.parse(raw) as Partial<CortexSettings>;
    return {
      onboardingComplete: Boolean(parsed.onboardingComplete),
      workspaceId: String(parsed.workspaceId || DEFAULTS.workspaceId),
    };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveSettings(patch: Partial<CortexSettings>): CortexSettings {
  const next = { ...loadSettings(), ...patch };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    if (next.onboardingComplete) {
      localStorage.setItem("cortex_onboarding_v1", "done");
    }
    if (next.workspaceId) {
      localStorage.setItem("cortex_workspace_id", next.workspaceId);
    }
  } catch {
    // Private browsing — skip persistence.
  }
  return next;
}

/** True when the dashboard is served from a public demo host (not localhost). */
export function isLiveDemoHost(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return (
    host.endsWith(".vercel.app") ||
    host.endsWith(".pages.dev") ||
    host.endsWith(".onrender.com") ||
    host.includes("cortex")
  );
}
