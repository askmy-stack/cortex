import { loadSettings, saveSettings } from "./settings";

const LEGACY_KEY = "cortex_onboarding_v1";

export function hasCompletedOnboarding(): boolean {
  try {
    const settings = loadSettings();
    if (settings.onboardingComplete) return true;
    return localStorage.getItem(LEGACY_KEY) === "done";
  } catch {
    return false;
  }
}

export function markOnboardingComplete(workspaceId?: string): void {
  saveSettings({
    onboardingComplete: true,
    ...(workspaceId ? { workspaceId } : {}),
  });
}

export function resetOnboarding(): void {
  saveSettings({ onboardingComplete: false });
  try {
    localStorage.removeItem(LEGACY_KEY);
  } catch {
    // ignore
  }
}
