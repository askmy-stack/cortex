/**
 * Vercel Edge Middleware — proxy API routes to CORTEX_API_ORIGIN at runtime.
 *
 * Used when the Vercel project Root Directory is the repo root (`cortex` project).
 * When Root Directory = `frontend`, see frontend/middleware.ts.
 */

export const config = {
  matcher: [
    "/health",
    "/metrics",
    "/query",
    "/inject",
    "/remember",
    "/docs",
    "/openapi.json",
    "/decisions/:path*",
    "/contradictions/:path*",
    "/gdpr/:path*",
    "/webhooks/:path*",
  ],
};

const API_PREFIXES = config.matcher.map((m) => m.replace("/:path*", ""));

function isApiRoute(pathname: string): boolean {
  return API_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export default async function middleware(request: Request): Promise<Response> {
  const origin = String(
    (globalThis as typeof globalThis & { process?: { env?: Record<string, string> } })
      .process?.env?.CORTEX_API_ORIGIN ?? "",
  )
    .trim()
    .replace(/\/$/, "");
  if (!origin) {
    return new Response(
      JSON.stringify({
        detail:
          "CORTEX_API_ORIGIN is not set on Vercel. Add your Railway/Render API URL in Project Settings.",
      }),
      { status: 503, headers: { "content-type": "application/json" } },
    );
  }

  const url = new URL(request.url);
  if (!isApiRoute(url.pathname)) {
    return new Response("Not found", { status: 404 });
  }

  const target = `${origin}${url.pathname}${url.search}`;
  const headers = new Headers(request.headers);
  headers.delete("host");

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
  }

  try {
    return await fetch(target, init);
  } catch (error) {
    const message = error instanceof Error ? error.message : "upstream fetch failed";
    return new Response(
      JSON.stringify({ detail: `API unreachable at ${origin}: ${message}` }),
      { status: 502, headers: { "content-type": "application/json" } },
    );
  }
}
