#!/usr/bin/env node
/**
 * Inject Vercel rewrites so the dashboard calls /query on the same origin.
 * Vercel proxies to CORTEX_API_ORIGIN server-side — avoids localtunnel 511
 * interstitials and CORS when the API runs on your laptop via cloudflared.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const configPath = join(root, "vercel.json");

const origin = String(process.env.CORTEX_API_ORIGIN ?? "")
  .trim()
  .replace(/\/$/, "");

const base = JSON.parse(readFileSync(configPath, "utf8"));

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

base.rewrites = [
  ...apiRewrites,
  { source: "/((?!assets/).*)", destination: "/index.html" },
];

writeFileSync(configPath, `${JSON.stringify(base, null, 2)}\n`);
if (origin) {
  console.log(`vercel.json: proxying API routes → ${origin}`);
} else {
  console.log("vercel.json: no CORTEX_API_ORIGIN — SPA only (use nginx/Vite proxy locally)");
}
