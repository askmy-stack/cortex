/** Human-friendly formatting helpers. */

export function scoreLabel(value: number): string {
  if (value >= 0.85) return "Very high";
  if (value >= 0.7) return "High";
  if (value >= 0.5) return "Moderate";
  if (value >= 0.3) return "Low";
  return "Minimal";
}

export function scorePercent(value: number): number {
  return Math.round(Math.min(1, Math.max(0, value)) * 100);
}

export function formatRelativeTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const diff = Date.now() - date.getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days < 1) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days} days ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function formatSource(source: string): string {
  const labels: Record<string, string> = {
    slack: "Slack",
    github: "GitHub",
    jira: "Jira",
    linear: "Linear",
    manual: "Captured manually",
    meeting: "Meeting",
    cicd: "CI/CD",
  };
  return labels[source] ?? source;
}

export function truncate(text: string, max = 120): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max).trim()}…`;
}
