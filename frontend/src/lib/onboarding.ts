const STORAGE_KEY = "cortex_onboarding_v1";

export function hasCompletedOnboarding(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "done";
  } catch {
    return false;
  }
}

export function markOnboardingComplete(): void {
  try {
    localStorage.setItem(STORAGE_KEY, "done");
  } catch {
    // Private browsing — skip persistence.
  }
}
