import { useState } from "react";
import { markOnboardingComplete } from "../../lib/onboarding";
import { useApp } from "../../context/AppContext";
import { IconSpark } from "../ui/icons";

type Props = {
  onComplete: () => void;
  onOpenCopilot: () => void;
  onFinishAsk: (workspace: string, query: string) => void;
};

const WORKSPACE_PRESETS = [
  { id: "local-dev", label: "Demo workspace", hint: "Pre-seeded decisions for demos" },
  { id: "oss-tiangolo-fastapi", label: "OSS: FastAPI", hint: "Open-source graph import" },
  { id: "oss-adr", label: "OSS: ADRs", hint: "Architecture decision records" },
] as const;

const DEMO_QUERY = "Why CockroachDB for payments?";

export function OnboardingModal({ onComplete, onOpenCopilot, onFinishAsk }: Props) {
  const { setWorkspaceId, apiKey, setApiKey, saveApiKey } = useApp();
  const [step, setStep] = useState(0);
  const [workspace, setWorkspace] = useState("local-dev");
  const isLast = step === 3;

  function finishToAsk(): void {
    markOnboardingComplete(workspace);
    setWorkspaceId(workspace);
    onComplete();
    onFinishAsk(workspace, DEMO_QUERY);
  }

  function finishToAssist(): void {
    markOnboardingComplete(workspace);
    setWorkspaceId(workspace);
    onComplete();
    onOpenCopilot();
  }

  return (
    <div
      className="onboarding-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
    >
      <div className="onboarding-modal">
        <div className="onboarding-modal__progress" aria-hidden>
          {[0, 1, 2, 3].map((i) => (
            <span key={i} className={`onboarding-dot ${i <= step ? "onboarding-dot--active" : ""}`} />
          ))}
        </div>

        {step === 0 ? (
          <>
            <span className="onboarding-modal__icon" aria-hidden>
              ◈
            </span>
            <h2 id="onboarding-title" className="onboarding-modal__title">
              Your organization's living memory
            </h2>
            <p className="onboarding-modal__body">
              Cortex captures <strong>decisions</strong> — not documents — from Slack, GitHub, Jira,
              and more. Ask natural questions and get answers with who decided, why, and what's
              affected.
            </p>
          </>
        ) : null}

        {step === 1 ? (
          <>
            <h2 id="onboarding-title" className="onboarding-modal__title">
              Choose a workspace
            </h2>
            <p className="onboarding-modal__body">
              Workspaces isolate organizational memory. Start with the demo workspace or pick an OSS
              preset.
            </p>
            <div className="onboarding-workspaces">
              {WORKSPACE_PRESETS.map((w) => (
                <button
                  key={w.id}
                  type="button"
                  className={`onboarding-workspace ${workspace === w.id ? "onboarding-workspace--active" : ""}`}
                  onClick={() => setWorkspace(w.id)}
                >
                  <span className="onboarding-workspace__label">{w.label}</span>
                  <span className="onboarding-workspace__hint">{w.hint}</span>
                </button>
              ))}
            </div>
          </>
        ) : null}

        {step === 2 ? (
          <>
            <h2 id="onboarding-title" className="onboarding-modal__title">
              Try a demo search
            </h2>
            <p className="onboarding-modal__body">
              We'll open Search with a sample question so you can see trust scores, coverage, and
              decision stories in seconds.
            </p>
            <blockquote className="onboarding-query">{DEMO_QUERY}</blockquote>
          </>
        ) : null}

        {step === 3 ? (
          <>
            <h2 id="onboarding-title" className="onboarding-modal__title">
              Connection (optional)
            </h2>
            <p className="onboarding-modal__body">
              The public demo works without a key. If your deployment requires authentication, add
              your API key now — you can always change it under Connection later.
            </p>
            <label className="field-label" htmlFor="onboard-api-key">
              API key
            </label>
            <input
              id="onboard-api-key"
              className="input"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Optional"
              autoComplete="off"
            />
          </>
        ) : null}

        <footer className="onboarding-modal__actions">
          {step > 0 ? (
            <button type="button" className="btn btn--ghost" onClick={() => setStep((s) => s - 1)}>
              Back
            </button>
          ) : (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => {
                markOnboardingComplete(workspace);
                onComplete();
              }}
            >
              Skip tour
            </button>
          )}
          {isLast ? (
            <>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => {
                  if (apiKey.trim()) saveApiKey();
                  finishToAsk();
                }}
              >
                Search memory
              </button>
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => {
                  if (apiKey.trim()) saveApiKey();
                  finishToAssist();
                }}
              >
                <IconSpark size={16} aria-hidden /> Open Assist
              </button>
            </>
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
