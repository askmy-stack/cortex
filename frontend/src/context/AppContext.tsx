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
import { viewFromHash, writeViewHash } from "../lib/routing";

type AppContextValue = {
  view: ViewId;
  setView: (view: ViewId) => void;
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
  apiKey: string;
  setApiKey: (key: string) => void;
  saveApiKey: () => void;
};

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [view, setViewState] = useState<ViewId>(() =>
    typeof window === "undefined" ? "home" : viewFromHash(),
  );
  const [workspaceId, setWorkspaceIdState] = useState(() =>
    typeof window === "undefined" ? "local-dev" : loadStoredWorkspace(),
  );
  const [assistantOpen, setAssistantOpen] = useState(
    () => typeof window === "undefined" || window.innerWidth > 1100,
  );
  const [messages, setMessages] = useState<AssistantMessage[]>(WELCOME_MESSAGES);
  const [lastQuery, setLastQuery] = useState<QueryResponse | null>(null);
  const [exploreDecisions, setExploreDecisions] = useState<DecisionResult[]>([]);
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);
  const [apiKey, setApiKeyState] = useState(() => loadStoredApiKey());

  const setView = useCallback((next: ViewId) => {
    setViewState(next);
    writeViewHash(next);
  }, []);

  const setWorkspaceId = useCallback((id: string) => {
    setWorkspaceIdState(id);
    persistWorkspace(id);
  }, []);

  const setApiKey = useCallback((key: string) => {
    setApiKeyState(key);
    setClientApiKey(key);
  }, []);

  const saveApiKey = useCallback(() => {
    persistApiKey(apiKey);
    setClientApiKey(apiKey);
  }, [apiKey]);

  useEffect(() => {
    setClientApiKey(apiKey);
  }, [apiKey]);

  useEffect(() => {
    const onHashChange = () => setViewState(viewFromHash());
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
      apiKey,
      setApiKey,
      saveApiKey,
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
      apiKey,
      setApiKey,
      saveApiKey,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
