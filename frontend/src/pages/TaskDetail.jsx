import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import api, { getApiError } from "../services/api";
import useResource from "../hooks/useResource";
import ResolutionForm from "../components/ResolutionForm";
import { BandBadge, SlaIndicator } from "../components/IssueParts";
import { Alert, Badge, Button, Card, ErrorState, Field, PageHeader, PageSkeleton } from "../components/ui";
import { formatDate } from "../utils/complaints";
import { TASK_STATUS_LABELS } from "../utils/issues";

function TaskSuggestion({ id }) {
  const suggestion = useResource(`/tasks/${id}/suggested-resolution`, { enabled: false });
  if (suggestion.data) {
    return <Alert variant="info" title="Suggested approach (advisory)">
      {suggestion.data.suggestion || "No suggested approach is available."}
    </Alert>;
  }
  return <div>
    {suggestion.error && <Alert variant="error">{suggestion.error}</Alert>}
    <Button variant="secondary" loading={suggestion.loading} onClick={suggestion.refresh}>Get suggested approach</Button>
  </div>;
}

export default function TaskDetail() {
  const { id } = useParams();
  const task = useResource(`/tasks/${id}`);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState(null);
  const [note, setNote] = useState({ kind: "progress", body: "" });
  const [reassignReason, setReassignReason] = useState("");

  async function act(name, request, success) {
    setBusy(name);
    setMessage(null);
    try {
      await request();
      setMessage({ variant: "success", text: success });
      await task.refresh();
    } catch (e) {
      setMessage({ variant: "error", text: getApiError(e, "That did not work. Please try again.") });
    } finally {
      setBusy("");
    }
  }

  if (task.loading && !task.data) return <PageSkeleton />;
  if (task.error) return <Card><ErrorState message={task.error} onRetry={task.refresh} /></Card>;
  const t = task.data;
  const active = ["assigned", "acknowledged", "in_progress", "awaiting_verification"].includes(t.status);
  return (
    <div className="page-stack mx-auto max-w-4xl">
      <PageHeader eyebrow={t.ticket_no} title={t.title} actions={<Link className="btn btn-secondary" to="/tasks">All tasks</Link>} />
      {message && <Alert variant={message.variant}>{message.text}</Alert>}
      <Card className="p-6">
        <div className="flex flex-wrap items-center gap-3">
          <Badge tone="blue">{TASK_STATUS_LABELS[t.status] || t.status}</Badge>
          <BandBadge band={t.priority_band} />
          <SlaIndicator due={t.due_at} active={active} />
          {t.is_lead && <Badge tone="green">Lead assignee</Badge>}
          {t.reassign_requested && <Badge tone="orange">Reassignment requested</Badge>}
        </div>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="text-xs text-slate-500">Location</dt><dd>{t.location_path || "—"}</dd></div>
          <div><dt className="text-xs text-slate-500">Reports received</dt><dd>{t.report_count}</dd></div>
          <div className="sm:col-span-2"><dt className="text-xs text-slate-500">Instructions</dt><dd>{t.task_description || "None"}</dd></div>
          {t.summary && <div className="sm:col-span-2"><dt className="text-xs text-slate-500">Summary</dt><dd className="whitespace-pre-wrap">{t.summary}</dd></div>}
        </dl>
        <div className="mt-5 flex flex-wrap gap-3">
          {t.status === "assigned" && (
            <Button loading={busy === "ack"} onClick={() => act("ack", () => api.post(`/tasks/${id}/acknowledge`), "Task acknowledged.")}>Acknowledge</Button>
          )}
          {t.status === "acknowledged" && (
            <Button loading={busy === "start"} onClick={() => act("start", () => api.post(`/tasks/${id}/start`), "Work started.")}>Start work</Button>
          )}
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="mb-3 text-lg font-semibold text-slate-800">What students reported</h2>
        <p className="mb-3 text-xs text-slate-500">Reporter identities are never shown to staff.</p>
        <ul className="space-y-3">
          {t.complaints.map((c) => (
            <li key={c.id} className="rounded-lg border border-slate-200 p-3 text-sm">
              <p className="font-medium text-slate-800">{c.title}</p>
              <p className="mt-1 whitespace-pre-wrap text-slate-600">{c.description}</p>
              <p className="mt-1 text-xs text-slate-400">{formatDate(c.created_at, { time: true })}{c.asset_name ? ` · ${c.asset_name}` : ""}</p>
            </li>
          ))}
        </ul>
      </Card>

      <TaskSuggestion key={id} id={id} />

      {active && t.status !== "assigned" && (
        <Card className="p-6">
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Add an update</h2>
          <form className="space-y-3" onSubmit={(e) => {
            e.preventDefault();
            if (note.body.trim().length < 2) return;
            act("note", () => api.post(`/tasks/${id}/updates`, { kind: note.kind, body: note.body.trim() }), "Update saved.")
              .then(() => setNote((n) => ({ ...n, body: "" })));
          }}>
            <Field label="Type" htmlFor="note-kind">
              <select id="note-kind" className="input max-w-52" value={note.kind} onChange={(e) => setNote({ ...note, kind: e.target.value })}>
                <option value="progress">Progress</option>
                <option value="blocker">Blocker</option>
                <option value="note">Note</option>
              </select>
            </Field>
            <Field label="Details" htmlFor="note-body">
              <textarea id="note-body" className="input min-h-20" value={note.body} onChange={(e) => setNote({ ...note, body: e.target.value })} />
            </Field>
            <Button type="submit" loading={busy === "note"}>Save update</Button>
          </form>
        </Card>
      )}

      {t.updates.length > 0 && (
        <Card className="p-6">
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Update log</h2>
          <ul className="space-y-2 text-sm">
            {t.updates.map((u) => (
              <li key={u.id}><Badge tone={u.kind === "blocker" ? "red" : "neutral"}>{u.kind.replaceAll("_", " ")}</Badge> {u.body}
                <span className="ml-2 text-xs text-slate-400">{formatDate(u.at, { time: true })}</span></li>
            ))}
          </ul>
        </Card>
      )}

      {t.status === "in_progress" && t.is_lead && (
        <Card className="p-6">
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Submit resolution</h2>
          <ResolutionForm task={t} onSubmitted={(r) => {
            setMessage({ variant: "success", text: r.issue_status === "awaiting_verification" ? "Submitted. Your department admin will verify it." : "Submitted. The issue is resolved." });
            task.refresh();
          }} />
        </Card>
      )}
      {t.status === "in_progress" && !t.is_lead && (
        <Alert variant="info">Only the lead assignee can submit the final resolution. Post updates here instead.</Alert>
      )}

      {active && !t.reassign_requested && (
        <Card className="p-6">
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Cannot do this task?</h2>
          <form className="space-y-3" onSubmit={(e) => {
            e.preventDefault();
            if (reassignReason.trim().length < 5) return;
            act("reassign", () => api.post(`/tasks/${id}/request-reassignment`, { reason: reassignReason.trim() }), "Reassignment requested.");
          }}>
            <Field label="Reason" htmlFor="reassign-reason">
              <textarea id="reassign-reason" className="input min-h-16" value={reassignReason} onChange={(e) => setReassignReason(e.target.value)} />
            </Field>
            <Button type="submit" variant="secondary" loading={busy === "reassign"}>Request reassignment</Button>
          </form>
        </Card>
      )}
    </div>
  );
}
