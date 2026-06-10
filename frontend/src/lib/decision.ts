const ENTITY_PREFIXES = ["person:", "system:"];

/** True when the id refers to a graph entity chip, not a decision node. */
export function isEntityNodeId(id: string): boolean {
  return ENTITY_PREFIXES.some((p) => id.startsWith(p));
}

/**
 * Resolve which decision id should stay focused when a card chip or graph node is clicked.
 */
export function resolveDecisionFocus(
  clickedId: string,
  decisions: { event_id: string }[],
  currentFocusId: string | null,
): string | null {
  if (!isEntityNodeId(clickedId)) {
    return clickedId;
  }
  if (currentFocusId && decisions.some((d) => d.event_id === currentFocusId)) {
    return currentFocusId;
  }
  return decisions[0]?.event_id ?? null;
}
