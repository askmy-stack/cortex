import type { ViewId } from "../types";

const VIEWS: ViewId[] = ["home", "ask", "explore", "agents", "review"];

export type RouteParams = {
  view: ViewId;
  decisionId?: string;
  query?: string;
};

export function parseHash(hash = window.location.hash): RouteParams {
  const raw = hash.replace(/^#/, "");
  const [path, queryString] = raw.split("?");
  const viewRaw = path.split("/")[0];
  const view = VIEWS.includes(viewRaw as ViewId) ? (viewRaw as ViewId) : "home";
  const params = new URLSearchParams(queryString || "");
  return {
    view,
    decisionId: params.get("decision") || undefined,
    query: params.get("q") || undefined,
  };
}

export function viewFromHash(hash = window.location.hash): ViewId {
  return parseHash(hash).view;
}

export function writeViewHash(view: ViewId, params?: { decision?: string; q?: string }): void {
  const search = new URLSearchParams();
  if (params?.decision) search.set("decision", params.decision);
  if (params?.q) search.set("q", params.q);
  const qs = search.toString();
  const next = qs ? `${view}?${qs}` : view;
  const current = window.location.hash.replace(/^#/, "");
  if (current !== next) {
    window.location.hash = next;
  }
}

export function buildDecisionShareUrl(decisionId: string): string {
  const base = `${window.location.origin}${window.location.pathname}`;
  return `${base}#/explore?decision=${encodeURIComponent(decisionId)}`;
}

export function buildAskShareUrl(query: string): string {
  const base = `${window.location.origin}${window.location.pathname}`;
  return `${base}#/ask?q=${encodeURIComponent(query)}`;
}
