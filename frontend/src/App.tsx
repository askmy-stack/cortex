import { AppProvider, useApp } from "./context/AppContext";
import { Sidebar } from "./components/layout/Sidebar";
import { AssistantPanel } from "./components/assistant/AssistantPanel";
import { HomeView } from "./views/HomeView";
import { AskView } from "./views/AskView";
import { ExploreView } from "./views/ExploreView";
import { AgentsView } from "./views/AgentsView";
import { ReviewView } from "./views/ReviewView";
import { apiBase } from "./api/client";

function MainContent() {
  const { view } = useApp();

  return (
    <main className="main" id="main">
      {view === "home" && <HomeView />}
      {view === "ask" && <AskView />}
      {view === "explore" && <ExploreView />}
      {view === "agents" && <AgentsView />}
      {view === "review" && <ReviewView />}
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
