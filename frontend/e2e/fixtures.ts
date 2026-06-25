import type { Page } from "@playwright/test";

export const SAMPLE_DECISION = {
  event_id: "e2e-decision-1",
  event_type: "decision",
  content: "Migrate payments to CockroachDB for multi-region scale.",
  made_by: ["dan@acme.example"],
  affects: ["payments-service"],
  rationale: ["Postgres failover gaps in eu-west."],
  importance_score: 0.88,
  trust_score: 0.82,
  extraction_confidence: 0.92,
  source: "slack",
  channel: "C-architecture",
  extracted_at: "2026-05-14T12:00:00Z",
  status: "active",
};

export const SAMPLE_CHAIN_NODE = {
  ...SAMPLE_DECISION,
  content: "Incident #247 triggered the database migration review.",
  event_id: "e2e-trigger-1",
  supersedes_ids: [] as string[],
  triggered_by_id: null as string | null,
};

/** Stub Cortex API routes for preview E2E (no live backend). */
export async function installApiMocks(page: Page): Promise<void> {
  await page.route("**/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        version: "0.1.0",
        uptime_seconds: 42,
        dependencies: { neo4j: "ok", redis: "ok" },
      }),
    });
  });

  await page.route("**/contradictions/pending**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await page.route("**/query", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    const body = route.request().postDataJSON() as { query?: string; workspace_id?: string };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        query: body.query ?? "",
        workspace_id: body.workspace_id ?? "local-dev",
        results: [SAMPLE_DECISION],
        total: 1,
        latency_ms: 18,
      }),
    });
  });

  await page.route("**/decisions/*/chain**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        decision_id: SAMPLE_DECISION.event_id,
        workspace_id: "local-dev",
        nodes: [SAMPLE_CHAIN_NODE, SAMPLE_DECISION],
        total: 2,
      }),
    });
  });
}

export async function dismissOnboarding(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.setItem("cortex_onboarding_v1", "done");
    localStorage.setItem(
      "cortex_settings_v2",
      JSON.stringify({ onboardingComplete: true, workspaceId: "local-dev" }),
    );
  });
}
