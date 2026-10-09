import { useCallback, useEffect, useRef, useState } from "react";
import { getHealth, type Health } from "../api/client";

export type Connection = {
  state: "checking" | "connected" | "unavailable";
  health: Health | null;
  error: string | null;
  checkedAt: string | null;
};
export function useBackend() {
  const [connection, setConnection] = useState<Connection>({
    state: "checking",
    health: null,
    error: null,
    checkedAt: null,
  });
  const activeRequest = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setConnection((previous) => ({
      ...previous,
      state: "checking",
      health: null,
      error: null,
    }));
    try {
      const health = await getHealth(controller.signal);
      if (!controller.signal.aborted)
        setConnection({
          state: "connected",
          health,
          error: null,
          checkedAt: new Date().toISOString(),
        });
    } catch (error) {
      if (!controller.signal.aborted)
        setConnection({
          state: "unavailable",
          health: null,
          error:
            error instanceof Error ? error.message : "Connection check failed.",
          checkedAt: new Date().toISOString(),
        });
    }
  }, []);
  useEffect(() => {
    void refresh();
    const interval = setInterval(() => void refresh(), 30000);
    return () => {
      clearInterval(interval);
      activeRequest.current?.abort();
    };
  }, [refresh]);
  return { connection, refresh };
}
