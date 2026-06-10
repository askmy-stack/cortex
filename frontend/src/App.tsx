import { Suspense, lazy, useState } from "react";
import { AppProvider, useApp } from "./context/AppContext";
import { ToastProvider } from "./components/ui/Toast";
import { Sidebar } from "./components/layout/Sidebar";
import { MobileNav } from "./components/layout/MobileNav";
import { AssistantPanel } from "./components/assistant/AssistantPanel";
import { OnboardingModal } from "./components/onboarding/OnboardingModal";
import { HomeView } from "./views/HomeView";
import { AskView } from "./views/AskView";
import { SkeletonStack } from "./components/ui/Skeleton";
import { apiBase } from "./api/client";
import { resolveApiKey } from "./lib/auth";
import { hasCompletedOnboarding } from "./lib/onboarding";
import { BugReportSection } from "./components/layout/BugReportSection";

const ExploreView = lazy(() =>
  import("./views/ExploreView").then((m) => ({ default: m.ExploreView })),
);
const AgentsView = lazy(() =>
  import("./views/AgentsView").then((m) => ({ default: m.AgentsView })),
);
const ReviewView = lazy(() =>
  import("./views/ReviewView").then((m) => ({ default: m.ReviewView })),
);

function ViewFallback() {
  return (
    <div className="lazy-fallback">
      <SkeletonStack rows={4} variant="card" />
    </div>
  );
}

function MainContent() {
  const { view } = useApp();

  return (
    <main className="main" id="main">
      {view === "home" && <HomeView />}
      {view === "ask" && <AskView />}
      {view === "explore" && (
        <Suspense fallback={<ViewFallback />}>
          <ExploreView />
        </Suspense>
      )}
      {view === "agents" && (
        <Suspense fallback={<ViewFallback />}>
          <AgentsView />
        </Suspense>
      )}
      {view === "review" && (
        <Suspense fallback={<ViewFallback />}>
          <ReviewView />
        </Suspense>
      )}
    </main>
  );
}

function TopbarActions() {
  const { apiKey, setAssistantOpen } = useApp();
  const secured = Boolean(resolveApiKey(apiKey));
  return (
    <div className="topbar__actions">
      <button
        type="button"
        className="topbar__copilot-btn"
        onClick={() => setAssistantOpen(true)}
        aria-label="Open Cortex Assist"
      >
        ✦ Assist
      </button>
      <span
        className={`topbar__badge ${secured ? "topbar__badge--secured" : ""}`}
        title={
          secured
            ? "API key configured — secured mode"
            : "Open dev mode — no API key (set in Connection settings)"
        }
      >
        {secured ? "Secured" : "Open"}
      </span>
      <a className="topbar__api" href={`${apiBase}/docs`} target="_blank" rel="noreferrer">
        API
      </a>
    </div>
  );
}

function AppChrome() {
  const { setAssistantOpen } = useApp();
  const [showOnboarding, setShowOnboarding] = useState(
    () => typeof window !== "undefined" && !hasCompletedOnboarding(),
  );

  return (
    <div className="app">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      {showOnboarding ? (
        <OnboardingModal
          onComplete={() => setShowOnboarding(false)}
          onOpenCopilot={() => setAssistantOpen(true)}
        />
      ) : null}
      <header className="topbar">
        <div className="topbar__brand">
          <span className="topbar__logo" aria-hidden>
            ◈
          </span>
          <div>
            <span className="topbar__name">Cortex</span>
            <span className="topbar__tag">Organizational intelligence</span>
          </div>
        </div>
        <TopbarActions />
      </header>

      <div className="app__body">
        <Sidebar />
        <MainContent />
        <AssistantPanel />
      </div>

      <MobileNav />

      <BugReportSection />

      <footer className="footer">
        <p>
          Cortex · <span className="footer__accent">Decisions, not documents</span> · Memory for
          AI-native teams
        </p>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <ToastProvider>
        <AppChrome />
      </ToastProvider>
    </AppProvider>
  );
}
