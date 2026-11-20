import { useState } from "react";
import api, { getApiError } from "../services/api";
import { Alert, Button, Field } from "./ui";

export default function FeedbackForm({ complaintId, onDone }) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [resolved, setResolved] = useState(null); // true | false | null
  const [stillUnresolved, setStillUnresolved] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    if (!rating || resolved === null) {
      setError("Choose a rating and tell us whether the problem is solved for you.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await api.post(`/complaints/${complaintId}/feedback`, {
        rating,
        comment: comment.trim() || null,
        resolved_for_me: resolved,
        still_unresolved: stillUnresolved,
      });
      onDone?.();
    } catch (requestError) {
      setError(getApiError(requestError, "We couldn’t save your feedback."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4" aria-label="Resolution feedback">
      {error && <Alert variant="error">{error}</Alert>}
      <fieldset>
        <legend className="mb-1 text-sm font-medium text-slate-700">How satisfied are you?</legend>
        <div className="flex gap-2" role="radiogroup" aria-label="Rating from 1 to 5">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={rating === n}
              onClick={() => setRating(n)}
              className={`h-10 w-10 rounded-lg border text-sm font-semibold ${rating === n ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 bg-white text-slate-700"}`}
            >
              {n}
            </button>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-1 text-sm font-medium text-slate-700">Is the problem solved for you?</legend>
        <div className="flex gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input type="radio" name="resolved" checked={resolved === true} onChange={() => { setResolved(true); setStillUnresolved(false); }} />
            Yes
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name="resolved" checked={resolved === false} onChange={() => setResolved(false)} />
            No
          </label>
        </div>
      </fieldset>
      {resolved === false && (
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={stillUnresolved} onChange={(e) => setStillUnresolved(e.target.checked)} />
          <span>The issue is still unresolved. Ask the department to look again.</span>
        </label>
      )}
      <Field label="Comments (optional)" htmlFor="fb-comment">
        <textarea id="fb-comment" className="input min-h-24" maxLength={1000} value={comment} onChange={(e) => setComment(e.target.value)} />
      </Field>
      <Button type="submit" loading={loading}>Send feedback</Button>
    </form>
  );
}
