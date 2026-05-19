/** Three-dot bouncing typing affordance with screen-reader label. */
export function TypingIndicator({ label = "Cortex is thinking" }: { label?: string }) {
  return (
    <span className="typing-indicator" role="status" aria-live="polite" aria-label={label}>
      <span aria-hidden />
      <span aria-hidden />
      <span aria-hidden />
    </span>
  );
}
