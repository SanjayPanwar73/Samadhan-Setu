import { useCallback, useEffect, useRef, useState } from "react";
import api, { getApiError } from "../services/api";

// Fetch one extra record to establish whether another page exists without
// inventing totals or making a second request. Search is scoped to loaded rows.
export default function usePagedResource(endpoint, pageSize = 25) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const count = useRef(0);
  const lastReset = useRef(true);
  const request = useRef(null);
  const fetchPage = useCallback(
    async (reset = false) => {
      lastReset.current = reset;
      request.current?.abort();
      const controller = new AbortController();
      request.current = controller;
      if (reset) setLoading(true);
      else setLoadingMore(true);
      setError("");
      const offset = reset ? 0 : count.current;
      try {
        const response = await api.get(endpoint, {
          params: { offset, limit: pageSize + 1 },
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        const rows = Array.isArray(response.data) ? response.data : [];
        const page = rows.slice(0, pageSize);
        count.current = offset + page.length;
        setData((current) =>
          reset
            ? page
            : [...current, ...page].filter(
                (item, index, items) =>
                  items.findIndex((other) => other.id === item.id) === index,
              ),
        );
        setHasMore(rows.length > pageSize && count.current <= 100000);
      } catch (error) {
        if (!controller.signal.aborted)
          setError(
            getApiError(
              error,
              "We couldn’t load these records. Please try again.",
            ),
          );
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
          setLoadingMore(false);
        }
      }
    },
    [endpoint, pageSize],
  );
  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) void fetchPage(true);
    });
    return () => {
      active = false;
      request.current?.abort();
    };
  }, [fetchPage]);
  return {
    data,
    loading,
    loadingMore,
    error,
    hasMore,
    setData,
    refresh: () => fetchPage(true),
    loadMore: () => fetchPage(false),
    retry: () => fetchPage(lastReset.current),
  };
}
