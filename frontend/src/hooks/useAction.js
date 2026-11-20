import { useCallback, useState } from "react";
import { getApiError } from "../services/api";

/**
 * Runs an async mutation with busy/message state. `run` resolves to true on success,
 * so callers can chain a refresh: `if (await run("key", () => api.post(...), "Saved.")) reload()`.
 */
export default function useAction() {
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState(null);
  const run = useCallback(async (key, request, success) => {
    setBusy(key);
    setMessage(null);
    try {
      await request();
      if (success) setMessage({ variant: "success", text: success });
      return true;
    } catch (error) {
      setMessage({
        variant: "error",
        text: getApiError(error, "That did not work. Please try again."),
      });
      return false;
    } finally {
      setBusy("");
    }
  }, []);
  return { busy, message, run, clear: () => setMessage(null) };
}
