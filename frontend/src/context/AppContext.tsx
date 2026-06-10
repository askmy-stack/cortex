import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { AssistantMessage, DecisionResult, QueryResponse, ViewId } from "../types";
import { WELCOME_MESSAGES, createMessage } from "../lib/assistant";

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
};

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState<ViewId>("home");
  const [workspaceId, setWorkspaceId] = useState("local-dev");
  // Default the guide open on desktop for discovery, collapsed on narrow
  // viewports so it never blocks content (it opens as an overlay drawer there).
  const [assistantOpen, setAssistantOpen] = useState(
    () => typeof window === "undefined" || window.innerWidth > 1100,
  );
  const [messages, setMessages] = useState<AssistantMessage[]>(WELCOME_MESSAGES);
  const [lastQuery, setLastQuery] = useState<QueryResponse | null>(null);
  const [exploreDecisions, setExploreDecisions] = useState<DecisionResult[]>([]);
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);

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
    }),
    [
      view,
      workspaceId,
      assistantOpen,
      messages,
      pushMessage,
      lastQuery,
      exploreDecisions,
      selectedDecisionId,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
