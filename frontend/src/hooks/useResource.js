import { useCallback, useEffect, useRef, useState } from "react";
import api, { getApiError } from "../services/api";

export default function useResource(
  endpoint,
  { enabled = true, collection = false, timeout = 60000 } = {},
) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState("");
  const request = useRef(null);
  const refresh = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError("");
    try {
      let result;
      if (collection) {
        result = [];
        for (let offset = 0; offset <= 100000; offset += 100) {
          const response = await api.get(endpoint, {
            params: { offset, limit: 100 },
            signal: controller.signal,
            timeout,
          });
          result.push(...response.data);
          if (response.data.length < 100 || controller.signal.aborted) break;
        }
      } else {
        result = (
          await api.get(endpoint, { signal: controller.signal, timeout })
        ).data;
      }
      if (!controller.signal.aborted) setData(result);
      return controller.signal.aborted ? null : result;
    } catch (requestError) {
      if (!controller.signal.aborted)
        setError(
          getApiError(
            requestError,
            "We couldn’t load this information. Please try again.",
          ),
        );
      return null;
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [endpoint, collection, timeout]);
  useEffect(() => {
    let active = true;
    if (enabled)
      queueMicrotask(() => {
        if (active) void refresh();
      });
    return () => {
      active = false;
      request.current?.abort();
    };
  }, [enabled, refresh]);
  return { data, setData, loading, error, refresh };
}
