import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { AssistantMessage, DecisionResult, QueryResponse, ViewId } from "../types";
import { WELCOME_MESSAGES, createMessage } from "../lib/assistant";
import { loadStoredApiKey, persistApiKey } from "../lib/auth";
import { setClientApiKey } from "../api/client";
import { loadStoredWorkspace, persistWorkspace } from "../lib/workspace";
import { loadSettings, saveSettings } from "../lib/settings";
import { parseHash, writeViewHash } from "../lib/routing";
import { resetOnboarding } from "../lib/onboarding";

type AppContextValue = {
  view: ViewId;
  setView: (view: ViewId, params?: { decision?: string; q?: string }) => void;
  workspaceId: string;
  setWorkspaceId: (id: string) => void;
  assistantOpen: boolean;
  setAssistantOpen: (open: boolean) => void;
  messages: AssistantMessage[];
  pushMessage: (role: AssistantMessage["role"], content: string) => void;
  lastQuery: QueryResponse | null;
  setLastQuery: (result: QueryResponse | null) => void;
  exploreDecisions: DecisionResult[];
  setExploreDecisions: (decisions: DecisionResult[]) => void;
  selectedDecisionId: string | null;
  setSelectedDecisionId: (id: string | null) => void;
  detailDecisionId: string | null;
  setDetailDecisionId: (id: string | null) => void;
  pendingAskQuery: string | null;
  setPendingAskQuery: (q: string | null) => void;
  apiKey: string;
  setApiKey: (key: string) => void;
  saveApiKey: () => void;
  clearApiKey: () => void;
  showOnboarding: boolean;
  setShowOnboarding: (open: boolean) => void;
  replayOnboarding: () => void;
};

const AppContext = createContext<AppContextValue | null>(null);

function initialWorkspace(): string {
  if (typeof window === "undefined") return "local-dev";
  return loadSettings().workspaceId || loadStoredWorkspace();
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [view, setViewState] = useState<ViewId>(() =>
    typeof window === "undefined" ? "home" : parseHash().view,
  );
  const [workspaceId, setWorkspaceIdState] = useState(initialWorkspace);
  const [assistantOpen, setAssistantOpen] = useState(
    () => typeof window === "undefined" || window.innerWidth > 1100,
  );
  const [messages, setMessages] = useState<AssistantMessage[]>(WELCOME_MESSAGES);
  const [lastQuery, setLastQuery] = useState<QueryResponse | null>(null);
  const [exploreDecisions, setExploreDecisions] = useState<DecisionResult[]>([]);
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(() =>
    typeof window === "undefined" ? null : parseHash().decisionId ?? null,
  );
  const [detailDecisionId, setDetailDecisionId] = useState<string | null>(null);
  const [pendingAskQuery, setPendingAskQuery] = useState<string | null>(() =>
    typeof window === "undefined" ? null : parseHash().query ?? null,
  );
  const [apiKey, setApiKeyState] = useState(() => loadStoredApiKey());
  const [showOnboarding, setShowOnboarding] = useState(
    () => typeof window !== "undefined" && !loadSettings().onboardingComplete,
  );

  const replayOnboarding = useCallback(() => {
    resetOnboarding();
    setShowOnboarding(true);
  }, []);

  const setView = useCallback(
    (next: ViewId, params?: { decision?: string; q?: string }) => {
      setViewState(next);
      writeViewHash(next, params);
      if (params?.decision) setSelectedDecisionId(params.decision);
      if (params?.q) setPendingAskQuery(params.q);
    },
    [],
  );

  const setWorkspaceId = useCallback((id: string) => {
    setWorkspaceIdState(id);
    persistWorkspace(id);
    saveSettings({ workspaceId: id });
  }, []);

  const setApiKey = useCallback((key: string) => {
    setApiKeyState(key);
    setClientApiKey(key);
  }, []);

  const saveApiKey = useCallback(() => {
    persistApiKey(apiKey);
    setClientApiKey(apiKey);
  }, [apiKey]);

  const clearApiKey = useCallback(() => {
    setApiKeyState("");
    persistApiKey("");
    setClientApiKey("");
  }, []);

  useEffect(() => {
    setClientApiKey(apiKey);
  }, [apiKey]);

  useEffect(() => {
    const onHashChange = () => {
      const route = parseHash();
      setViewState(route.view);
      if (route.decisionId) setSelectedDecisionId(route.decisionId);
      if (route.query) setPendingAskQuery(route.query);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const pushMessage = useCallback((role: AssistantMessage["role"], content: string) => {
    setMessages((prev) => [...prev, createMessage(role, content)]);
  }, []);

  const value = useMemo(
    () => ({
      view,
      setView,
      workspaceId,
      setWorkspaceId,
      assistantOpen,
      setAssistantOpen,
      messages,
      pushMessage,
      lastQuery,
      setLastQuery,
      exploreDecisions,
      setExploreDecisions,
      selectedDecisionId,
      setSelectedDecisionId,
      detailDecisionId,
      setDetailDecisionId,
      pendingAskQuery,
      setPendingAskQuery,
      apiKey,
      setApiKey,
      saveApiKey,
      clearApiKey,
      showOnboarding,
      setShowOnboarding,
      replayOnboarding,
    }),
    [
      view,
      setView,
      workspaceId,
      setWorkspaceId,
      assistantOpen,
      messages,
      pushMessage,
      lastQuery,
      exploreDecisions,
      selectedDecisionId,
      detailDecisionId,
      pendingAskQuery,
      apiKey,
      setApiKey,
      saveApiKey,
      clearApiKey,
      showOnboarding,
      replayOnboarding,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
