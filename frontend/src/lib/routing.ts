import type { ViewId } from "../types";

const VIEWS: ViewId[] = ["home", "ask", "explore", "agents", "review"];

export function viewFromHash(hash = window.location.hash): ViewId {
  const raw = hash.replace(/^#/, "").split("/")[0];
  return VIEWS.includes(raw as ViewId) ? (raw as ViewId) : "home";
}

export function writeViewHash(view: ViewId): void {
  if (window.location.hash.replace(/^#/, "").split("/")[0] !== view) {
    window.location.hash = view;
  }
}
