import { Suspense, lazy } from "react";
import { AppProvider, useApp } from "./context/AppContext";
import { Sidebar } from "./components/layout/Sidebar";
import { AssistantPanel } from "./components/assistant/AssistantPanel";
import { HomeView } from "./views/HomeView";
import { AskView } from "./views/AskView";
import { SkeletonStack } from "./components/ui/Skeleton";
import { apiBase } from "./api/client";

// Heavier secondary views are deferred so the initial bundle stays light.
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

function AppChrome() {
  return (
    <div className="app">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar__brand">
          <span className="topbar__logo" aria-hidden>
            ◈
          </span>
          <div>
            <span className="topbar__name">Cortex</span>
            <span className="topbar__tag">Organizational memory</span>
          </div>
        </div>
        <a className="topbar__api" href={`${apiBase}/docs`} target="_blank" rel="noreferrer">
          API docs
        </a>
      </header>

      <div className="app__body">
        <Sidebar />
        <MainContent />
        <AssistantPanel />
      </div>

      <footer className="footer">
        <p>Cortex · Decisions, not documents · Memory that agents can trust</p>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppChrome />
    </AppProvider>
  );
}
