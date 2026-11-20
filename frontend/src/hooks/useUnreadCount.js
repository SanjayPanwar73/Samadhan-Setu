import { useCallback, useEffect, useState } from "react";
import api from "../services/api";

export const POLL_MS = 30_000;

/** Polls the unread-notification count; no WebSocket is needed. */
export default function useUnreadCount(intervalMs = POLL_MS) {
  const [count, setCount] = useState(0);
  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/notifications/unread-count");
      setCount(Number(data.unread) || 0);
    } catch {
      /* keep the last known count; the next poll retries */
    }
  }, []);
  useEffect(() => {
    queueMicrotask(refresh);
    const timer = window.setInterval(refresh, intervalMs);
    const onFocus = () => document.visibilityState === "visible" && refresh();
    document.addEventListener("visibilitychange", onFocus);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onFocus);
    };
  }, [refresh, intervalMs]);
  return { count, refresh };
}
