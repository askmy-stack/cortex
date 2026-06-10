const STORAGE_KEY = "cortex_workspace_id";

export function loadStoredWorkspace(): string {
  try {
    return localStorage.getItem(STORAGE_KEY)?.trim() || "local-dev";
  } catch {
    return "local-dev";
  }
}

export function persistWorkspace(id: string): void {
  try {
    const trimmed = id.trim();
    if (trimmed) {
      localStorage.setItem(STORAGE_KEY, trimmed);
    }
  } catch {
    // Private browsing — session-only via React state.
  }
}
