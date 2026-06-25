import { useCallback, useEffect, useState } from "react";
import { fetchHealth } from "../api/client";
import type { Health } from "../types";

export type ApiHealthStatus = "ok" | "degraded" | "unreachable" | "checking";

export function useApiHealth(pollMs = 60_000): {
  status: ApiHealthStatus;
  health: Health | null;
  refresh: () => Promise<void>;
} {
  const [health, setHealth] = useState<Health | null>(null);
  const [status, setStatus] = useState<ApiHealthStatus>("checking");

  const refresh = useCallback(async () => {
    setStatus("checking");
    try {
      const payload = await fetchHealth();
      setHealth(payload);
      const neo4j = payload.dependencies?.neo4j;
      const redis = payload.dependencies?.redis;
      if (payload.status === "ok" && neo4j === "ok" && redis === "ok") {
        setStatus("ok");
      } else {
        setStatus("degraded");
      }
    } catch {
      setHealth(null);
      setStatus("unreachable");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), pollMs);
    return () => window.clearInterval(id);
  }, [refresh, pollMs]);

  return { status, health, refresh };
}
