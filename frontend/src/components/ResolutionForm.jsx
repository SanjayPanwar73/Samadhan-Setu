import { useRef, useState } from "react";
import api, { getApiError } from "../services/api";
import { Alert, Button, Field } from "./ui";

// Every field the backend understands. The category's resolution_schema.required list
// decides which are mandatory; with no schema the backend default applies.
export const RESOLUTION_FIELDS = [
  { key: "what_was_wrong", label: "What was wrong?", multiline: true },
  { key: "root_cause", label: "Root cause", multiline: true },
  { key: "action_taken", label: "Action taken", multiline: true },
  { key: "parts_replaced", label: "Parts or materials replaced" },
  { key: "notes", label: "Notes", multiline: true },
  { key: "public_summary", label: "Summary shown to students", multiline: true, hint: "Keep it short and free of names or private details." },
];
export const DEFAULT_REQUIRED = ["what_was_wrong", "action_taken", "public_summary"];

export function requiredFields(schema) {
  return Array.isArray(schema?.required) ? schema.required : DEFAULT_REQUIRED;
}

/** Returns { field: message } for every missing required field. */
export function validateResolution(values, required) {
  const errors = {};
  required.forEach((key) => {
    if (!String(values[key] ?? "").trim()) errors[key] = "This field is required.";
  });
  return errors;
}

export default function ResolutionForm({ task, onSubmitted }) {
  const required = requiredFields(task.resolution_schema);
  const [values, setValues] = useState({});
  const [followup, setFollowup] = useState(false);
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [evidence, setEvidence] = useState(0);
  const [uploadError, setUploadError] = useState("");
  const fileInput = useRef(null);

  async function attach(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploadError("");
    const body = new FormData();
    body.append("file", file);
    body.append("kind", "after");
    try {
      await api.post(`/tasks/${task.id}/attachments`, body);
      setEvidence((n) => n + 1);
    } catch (e) {
      setUploadError(getApiError(e, "Could not attach the file."));
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    const invalid = validateResolution(values, required);
    if (task.requires_evidence && evidence === 0)
      invalid.evidence = "Attach at least one photo or PDF of the fix.";
    setErrors(invalid);
    setError("");
    if (Object.keys(invalid).length) return;
    setLoading(true);
    try {
      const body = { followup_needed: followup };
      RESOLUTION_FIELDS.forEach(({ key }) => {
        if (values[key]?.trim()) body[key] = values[key].trim();
      });
      const { data } = await api.post(`/tasks/${task.id}/resolve`, body);
      onSubmitted?.(data);
    } catch (requestError) {
      setError(getApiError(requestError, "Could not submit the resolution."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4" noValidate aria-label="Resolution report">
      {error && <Alert variant="error">{error}</Alert>}
      {RESOLUTION_FIELDS.map(({ key, label, multiline, hint }) => (
        <Field
          key={key}
          htmlFor={`res-${key}`}
          label={`${label}${required.includes(key) ? " *" : ""}`}
          hint={hint}
          error={errors[key]}
        >
          {multiline ? (
            <textarea id={`res-${key}`} className="input min-h-20" value={values[key] || ""}
              onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))} aria-invalid={Boolean(errors[key])} />
          ) : (
            <input id={`res-${key}`} className="input" value={values[key] || ""}
              onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))} aria-invalid={Boolean(errors[key])} />
          )}
        </Field>
      ))}
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={followup} onChange={(e) => setFollowup(e.target.checked)} />
        Follow-up work is needed
      </label>
      <Field label={`Evidence${task.requires_evidence ? " *" : " (optional)"}`} htmlFor="res-evidence" error={errors.evidence || uploadError}
        hint={evidence ? `${evidence} file(s) attached` : "Photos of the fix (PNG, JPEG, WebP) or a PDF."}>
        <input id="res-evidence" ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp,application/pdf" onChange={attach} />
      </Field>
      <Button type="submit" loading={loading}>Submit resolution</Button>
    </form>
  );
}
