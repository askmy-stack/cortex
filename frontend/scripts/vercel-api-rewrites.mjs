#!/usr/bin/env node
/**
 * Inject Vercel rewrites so the dashboard calls /query on the same origin.
 * Vercel proxies to CORTEX_API_ORIGIN server-side — avoids localtunnel 511
 * interstitials and CORS when the API runs on your laptop via cloudflared.
 *
 * Updates frontend/vercel.json (Root Directory = frontend) and repo-root
 * vercel.json (Root Directory = .) when the latter exists.
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = join(frontendRoot, "..");

const origin = String(process.env.CORTEX_API_ORIGIN ?? "")
  .trim()
  .replace(/\/$/, "");

const apiRewrites = origin
  ? [
      { source: "/health", destination: `${origin}/health` },
      { source: "/metrics", destination: `${origin}/metrics` },
      { source: "/query", destination: `${origin}/query` },
      { source: "/inject", destination: `${origin}/inject` },
      { source: "/remember", destination: `${origin}/remember` },
      { source: "/docs", destination: `${origin}/docs` },
      { source: "/openapi.json", destination: `${origin}/openapi.json` },
      { source: "/decisions/:path*", destination: `${origin}/decisions/:path*` },
      { source: "/contradictions/:path*", destination: `${origin}/contradictions/:path*` },
      { source: "/gdpr/:path*", destination: `${origin}/gdpr/:path*` },
      { source: "/webhooks/:path*", destination: `${origin}/webhooks/:path*` },
    ]
  : [];

const spaFallback = { source: "/((?!assets/).*)", destination: "/index.html" };

function applyRewrites(configPath) {
  const base = JSON.parse(readFileSync(configPath, "utf8"));
  base.rewrites = [...apiRewrites, spaFallback];
  writeFileSync(configPath, `${JSON.stringify(base, null, 2)}\n`);
}

const targets = [join(frontendRoot, "vercel.json")];
const rootConfig = join(repoRoot, "vercel.json");
if (existsSync(rootConfig)) {
  targets.push(rootConfig);
}

for (const configPath of targets) {
  applyRewrites(configPath);
}

if (origin) {
  console.log(`vercel.json: proxying API routes → ${origin} (${targets.length} file(s))`);
} else {
  console.log(
    `vercel.json: no CORTEX_API_ORIGIN — SPA only (${targets.length} file(s); use nginx/Vite proxy locally)`,
  );
}
