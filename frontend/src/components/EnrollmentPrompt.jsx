import { useState } from "react";
import api, { getApiError } from "../services/api";
import { Alert, Button } from "./ui";

/** Shown once to students whose account was migrated from V1 and has no enrollment number. */
export default function EnrollmentPrompt({ onDone }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    if (value.trim().length < 3) {
      setError("Enter your enrollment number (at least 3 characters).");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await api.patch("/auth/me/enrollment", { enrollment_no: value.trim() });
      onDone?.();
    } catch (requestError) {
      setError(getApiError(requestError, "We couldn’t save your enrollment number."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Alert variant="info" title="One more step: add your enrollment number" className="mb-5">
      <form onSubmit={submit} className="mt-2 flex flex-wrap items-end gap-3" aria-label="Add enrollment number">
        <label className="text-sm">
          <span className="sr-only">Enrollment number</span>
          <input className="input" value={value} onChange={(e) => setValue(e.target.value)} maxLength={32}
            placeholder="Enrollment number" autoComplete="off" aria-invalid={Boolean(error)} />
        </label>
        <Button type="submit" loading={loading}>Save</Button>
      </form>
      {error && <p className="field-error mt-2" role="alert">{error}</p>}
    </Alert>
  );
}
