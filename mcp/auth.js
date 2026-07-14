/**
 * Resolve MCP auth configuration from the environment.
 *
 * In production, the legacy `X-Cortex-Roles` header (trusted only in the
 * API's open/dev mode) is a privilege-escalation vector: any process with
 * MCP env access could claim `admin`/`gdpr_officer` without a real key. So
 * MCP tool calls are refused outright when `ENVIRONMENT=production` and no
 * `CORTEX_API_KEY` is configured, rather than silently falling back to the
 * role header.
 */
export function resolveMcpAuth(env = process.env) {
  const environment = (env.ENVIRONMENT ?? "development").trim().toLowerCase();
  const apiKey = (env.CORTEX_API_KEY ?? "").trim();
  const requireApiKey = environment === "production";
  return { environment, apiKey, requireApiKey, blocked: requireApiKey && !apiKey };
}
