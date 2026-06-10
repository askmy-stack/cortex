const STORAGE_KEY = "cortex_api_key";

/** Build-time default from Vite; user override in Connection settings wins. */
export function defaultApiKey(): string {
  return String(import.meta.env.VITE_CORTEX_API_KEY ?? "").trim();
}

export function loadStoredApiKey(): string {
  try {
    return localStorage.getItem(STORAGE_KEY)?.trim() ?? "";
  } catch {
    return "";
  }
}

export function persistApiKey(key: string): void {
  try {
    const trimmed = key.trim();
    if (trimmed) {
      localStorage.setItem(STORAGE_KEY, trimmed);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Private browsing or storage disabled — session-only via context state.
  }
}

/** Effective key: stored override, then build-time env default. */
export function resolveApiKey(storedKey: string): string {
  return storedKey.trim() || defaultApiKey();
}

export function authHeaders(apiKey: string): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const key = apiKey.trim();
  if (key) {
    headers.Authorization = `Bearer ${key}`;
  }
  return headers;
}

export function isUnauthorizedMessage(message: string): boolean {
  return message.includes("401") || message.toLowerCase().includes("invalid api key");
}
