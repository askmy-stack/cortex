import { useState } from "react";
import { markOnboardingComplete } from "../../lib/onboarding";

type Props = {
  onComplete: () => void;
  onOpenCopilot: () => void;
};

const STEPS = [
  {
    title: "Your organization's living memory",
    body: "Cortex captures decisions — not documents — from Slack, GitHub, Jira, and more. Ask natural questions and get answers with who decided, why, and what's affected.",
    icon: "◈",
  },
  {
    title: "Ask in plain language",
    body: 'Try questions like "Why did we choose CockroachDB for payments?" or "What affects checkout?" Cortex searches structured memory, not scattered threads.',
    icon: "?",
  },
  {
    title: "Meet your Copilot",
    body: "The Cortex Copilot guides you, runs searches, and explains results. Use the memory map to see how people, systems, and decisions connect over time.",
    icon: "✦",
  },
] as const;

export function OnboardingModal({ onComplete, onOpenCopilot }: Props) {
  const [step, setStep] = useState(0);
  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  function finish() {
    markOnboardingComplete();
    onComplete();
    if (isLast) onOpenCopilot();
  }

  return (
    <div className="onboarding-overlay" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
      <div className="onboarding-modal">
        <div className="onboarding-modal__progress" aria-hidden>
          {STEPS.map((_, i) => (
            <span key={i} className={`onboarding-dot ${i <= step ? "onboarding-dot--active" : ""}`} />
          ))}
        </div>
        <span className="onboarding-modal__icon" aria-hidden>
          {current.icon}
        </span>
        <h2 id="onboarding-title" className="onboarding-modal__title">
          {current.title}
        </h2>
        <p className="onboarding-modal__body">{current.body}</p>
        <footer className="onboarding-modal__actions">
          {step > 0 ? (
            <button type="button" className="btn btn--ghost" onClick={() => setStep((s) => s - 1)}>
              Back
            </button>
          ) : (
            <button type="button" className="btn btn--ghost" onClick={finish}>
              Skip tour
            </button>
          )}
          {isLast ? (
            <button type="button" className="btn btn--primary" onClick={finish}>
              Open Copilot
            </button>
          ) : (
            <button type="button" className="btn btn--primary" onClick={() => setStep((s) => s + 1)}>
              Continue
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}
