import type { AssistantMessage, DecisionResult, QueryResponse } from "../types";
import { formatSource, scoreLabel } from "./format";

let messageCounter = 0;

export function createMessage(
  role: AssistantMessage["role"],
  content: string,
): AssistantMessage {
  messageCounter += 1;
  return { id: `msg-${messageCounter}`, role, content, timestamp: Date.now() };
}

export const WELCOME_MESSAGES: AssistantMessage[] = [
  createMessage(
    "assistant",
    "Welcome to Cortex — your organization's living memory. I help you find **why** decisions were made, who was involved, and which systems they affect — without digging through Slack threads or old docs.",
  ),
  createMessage(
    "assistant",
    "Try asking something like *\"Why did we choose CockroachDB for payments?\"* on the **Ask** page. I'll explain what we find in plain language.",
  ),
];

export function summarizeQueryResults(response: QueryResponse): string {
  const { total, latency_ms, query, results } = response;
  if (total === 0) {
    return `I searched your workspace memory for **"${query}"** but didn't find matching decisions yet. If you're on a fresh install, run \`make demo\` to seed example memories, or capture a decision with **Remember** via the API.`;
  }

  const top = results[0];
  const systems = [...new Set(results.flatMap((r) => r.affects))].slice(0, 4);
  const people = [...new Set(results.flatMap((r) => r.made_by))].slice(0, 3);

  let summary = `Found **${total}** relevant decision${total === 1 ? "" : "s"} in ${latency_ms}ms.\n\n`;
  summary += `**Most relevant:** ${top.content}\n`;
  summary += `- Confidence: ${scoreLabel(top.trust_score)} trust · ${scoreLabel(top.importance_score)} importance\n`;
  summary += `- Source: ${formatSource(top.source)}`;
  if (systems.length) summary += `\n- Touches: ${systems.join(", ")}`;
  if (people.length) summary += `\n- People: ${people.join(", ")}`;
  if (top.rationale.length) {
    summary += `\n\n**Why it mattered:** ${top.rationale[0]}`;
  }
  if (total > 1) {
    summary += `\n\nOpen the **Memory map** tab to see relationships and timeline across all ${total} results.`;
  }
  return summary;
}

export function explainDecision(d: DecisionResult): string {
  const lines = [
    `**${d.content}**`,
    `This is recorded as a *${d.event_type}* with ${scoreLabel(d.trust_score)} trust and ${scoreLabel(d.importance_score)} importance.`,
  ];
  if (d.affects.length) lines.push(`It affects: ${d.affects.join(", ")}.`);
  if (d.made_by.length) lines.push(`Decision makers: ${d.made_by.join(", ")}.`);
  if (d.rationale.length) lines.push(`Rationale: ${d.rationale.join(" · ")}`);
  return lines.join("\n");
}

export function injectSummary(
  count: number,
  summary: string,
  tokenEstimate: number,
): string {
  if (count === 0) {
    return "No organizational memory matched this agent context strongly enough to inject. Try broadening the task description or lowering trust thresholds in your deployment.";
  }
  return `I would inject **${count}** decision${count === 1 ? "" : "s"} (~${tokenEstimate} tokens) into an AI agent working on this task:\n\n${summary}`;
}
