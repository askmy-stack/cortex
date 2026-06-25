/** Human-readable messages for API and network failures. */

export function apiUnreachableMessage(): string {
  return (
    "Cannot reach the Cortex API. Check your Connection settings and confirm the API is running. " +
    "For local development, start the stack and ensure the dashboard can reach port 8000."
  );
}

export function normalizeFetchError(error: unknown): string {
  if (error instanceof Error) {
    const msg = error.message;
    if (
      msg === "Failed to fetch" ||
      msg.includes("NetworkError") ||
      msg.includes("ECONNREFUSED") ||
      msg.includes("Load failed")
    ) {
      return apiUnreachableMessage();
    }
    return msg;
  }
  return String(error);
}

export async function parseHttpError(response: Response): Promise<string> {
  let detail = "";
  try {
    detail = await response.text();
  } catch {
    detail = "";
  }
  const status = `${response.status} ${response.statusText || ""}`.trim();

  if (response.status === 401) {
    return (
      "Authentication required (401). Add your API key in Connection settings. " +
      "When CORTEX_API_KEYS is set on the server, requests without a valid key are rejected."
    );
  }
  if (response.status === 500 && !detail.trim()) {
    return apiUnreachableMessage();
  }
  if (response.status === 503) {
    const base = "Service unavailable (503). Neo4j or another dependency may be down.";
    return detail ? `${base} ${detail.slice(0, 120)}` : base;
  }
  if (response.status === 511 || detail.includes("Tunnel website ahead")) {
    return (
      "API tunnel blocked the request (511). Use same-origin /query via Vercel middleware " +
      "(CORTEX_API_ORIGIN), not a tunnel URL in VITE_API_URL."
    );
  }
  if (!detail) return `Request failed (${status})`;
  return `Request failed (${status}): ${detail.slice(0, 200)}`;
}
