import { useState } from "react";
import api from "../services/api";
import useAction from "../hooks/useAction";
import useResource from "../hooks/useResource";
import { PriorityBreakdown } from "./IssueParts";
import { Alert, Badge, Button, Field } from "./ui";
import { formatDate } from "../utils/complaints";
import { BAND_TONES } from "../utils/issues";

export function LinkedComplaintsPanel({ complaints, onRelink }) {
  const [moving, setMoving] = useState(null);
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const { busy, message, run } = useAction();
  if (!complaints.length) return <p className="text-sm text-slate-500">No complaints linked.</p>;
  return (
    <div>
      {message && <Alert variant={message.variant} className="mb-3">{message.text}</Alert>}
      <ul className="divide-y divide-slate-100" aria-label="Linked complaints">
        {complaints.map((c) => (
          <li key={c.id} className="py-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium text-slate-800">
                #{c.id} · {c.is_anonymous ? <Badge>Anonymous {c.anon_code}</Badge> : c.submitter_name || "Student"}
              </p>
              <span className="text-xs text-slate-500">
                {formatDate(c.created_at, { time: true })}
                {c.match_score != null && ` · match ${(c.match_score * 100).toFixed(0)}%`}
                {c.link_type && ` · ${c.link_type}`}
              </span>
            </div>
            <p className="mt-1 whitespace-pre-wrap text-slate-600">{c.description}</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {c.has_dissent && <Badge tone="red">Dissent</Badge>}
              {c.classification_disagreement && <Badge tone="amber">AI disagrees with category</Badge>}
            </div>
            <button type="button" className="mt-1 text-xs text-brand-700 underline" onClick={() => setMoving(moving === c.id ? null : c.id)}>
              Move to another issue
            </button>
            {moving === c.id && (
              <form className="mt-2 grid gap-2 sm:grid-cols-[8rem_1fr_auto]" onSubmit={async (e) => {
                e.preventDefault();
                if (!Number(target) || reason.trim().length < 5) return;
                const ok = await run("move", () => api.post(`/complaints/${c.id}/relink`, { issue_id: Number(target), reason: reason.trim() }), "Complaint moved.");
                if (ok) { setMoving(null); setTarget(""); setReason(""); onRelink?.(); }
              }}>
                <input className="input" type="number" min="1" placeholder="Issue id" aria-label="Target issue id" value={target} onChange={(e) => setTarget(e.target.value)} />
                <input className="input" placeholder="Reason (required)" aria-label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} />
                <Button type="submit" loading={busy === "move"}>Move</Button>
              </form>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DuplicateSuggestionCard({ suggestion, onDone }) {
  const { busy, message, run } = useAction();
  const pending = suggestion.status === "pending";
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm">
      <p className="font-semibold text-slate-800">
        Complaint #{suggestion.complaint_id} may belong to {suggestion.candidate_ticket_no}
      </p>
      <p className="mt-1 text-xs text-slate-600">
        Match score {(suggestion.score * 100).toFixed(0)}% · semantic {(suggestion.breakdown?.cosine ?? 0).toFixed(2)}
        {suggestion.breakdown?.ambiguous ? " · several identical items at this location" : ""}
      </p>
      {message && <Alert variant={message.variant} className="mt-2">{message.text}</Alert>}
      {pending ? (
        <div className="mt-3 flex gap-2">
          <Button loading={busy === "accept"} onClick={async () => (await run("accept", () => api.post(`/duplicate-suggestions/${suggestion.id}/accept`), "Merged.")) && onDone?.()}>Merge into {suggestion.candidate_ticket_no}</Button>
          <Button variant="secondary" loading={busy === "reject"} onClick={async () => (await run("reject", () => api.post(`/duplicate-suggestions/${suggestion.id}/reject`), "Kept separate.")) && onDone?.()}>Keep separate</Button>
        </div>
      ) : (
        <Badge className="mt-2">{suggestion.status}</Badge>
      )}
    </div>
  );
}

export function AssignmentPanel({ issue, assignments, onChanged }) {
  const staff = useResource(`/department-staff?department_id=${issue.department_id}`);
  const [selected, setSelected] = useState([]);
  const [lead, setLead] = useState("");
  const [description, setDescription] = useState("");
  const [due, setDue] = useState("");
  const { busy, message, run } = useAction();
  const assignable = ["open", "assigned", "in_progress", "reopened"].includes(issue.status);
  const names = Object.fromEntries((staff.data || []).map((s) => [s.id, s.name]));

  function toggle(id) {
    setSelected((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }
  function refreshAfterAssignment() {
    staff.refresh();
    onChanged?.();
  }
  return (
    <div className="space-y-4">
      {message && <Alert variant={message.variant}>{message.text}</Alert>}
      <ul className="space-y-2 text-sm" aria-label="Assignments">
        {assignments.length === 0 && <li className="text-slate-500">Nobody is assigned yet.</li>}
        {assignments.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3">
            <span>
              {names[a.staff_id] || `Staff #${a.staff_id}`} {a.is_lead && <Badge tone="green">Lead</Badge>}{" "}
              <Badge>{a.status.replaceAll("_", " ")}</Badge>
              {a.reassign_requested && <Badge tone="orange">Reassignment requested</Badge>}
            </span>
            {["assigned", "acknowledged", "in_progress"].includes(a.status) && (
              <select className="input !min-h-9 max-w-44 !py-1.5 !text-xs" aria-label={`Reassign task ${a.id}`} value=""
                onChange={async (e) => e.target.value && (await run("re" + a.id, () => api.patch(`/assignments/${a.id}`, { staff_id: Number(e.target.value) }), "Reassigned.")) && refreshAfterAssignment()}>
                <option value="">Reassign to…</option>
                {(staff.data || []).filter((s) => s.id !== a.staff_id).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            )}
          </li>
        ))}
      </ul>
      {assignable && (
        <form className="space-y-3 rounded-xl border border-slate-200 p-4" onSubmit={async (e) => {
          e.preventDefault();
          if (!selected.length) return;
          const body = { staff_ids: selected, task_description: description.trim() || null };
          if (lead && selected.includes(Number(lead))) body.lead_staff_id = Number(lead);
          if (due) body.due_at = new Date(due).toISOString();
          if (await run("assign", () => api.post(`/issues/${issue.id}/assignments`, body), "Assigned.")) {
            setSelected([]); setLead(""); setDescription(""); setDue(""); refreshAfterAssignment();
          }
        }}>
          <fieldset>
            <legend className="mb-1 text-sm font-medium text-slate-700">Assign staff</legend>
            {staff.loading ? <p className="text-xs text-slate-500">Loading staff…</p> : (staff.data || []).length === 0 ? (
              <p className="text-xs text-slate-500">No staff are registered in this department.</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {(staff.data || []).map((s) => (
                  <label key={s.id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={selected.includes(s.id)} onChange={() => toggle(s.id)} />
                    {s.name} <span className="text-xs text-slate-400">({s.active_tasks} active{s.overdue_tasks ? `, ${s.overdue_tasks} overdue` : ""})</span>
                  </label>
                ))}
              </div>
            )}
          </fieldset>
          {selected.length > 1 && (
            <Field label="Lead assignee" htmlFor="lead">
              <select id="lead" className="input max-w-60" value={lead} onChange={(e) => setLead(e.target.value)}>
                <option value="">First selected</option>
                {selected.map((id) => <option key={id} value={id}>{names[id]}</option>)}
              </select>
            </Field>
          )}
          <Field label="Instructions (optional)" htmlFor="task-desc">
            <textarea id="task-desc" className="input min-h-16" value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <Field label="Due (defaults to the SLA)" htmlFor="task-due">
            <input id="task-due" type="datetime-local" className="input max-w-64" value={due} onChange={(e) => setDue(e.target.value)} />
          </Field>
          <Button type="submit" loading={busy === "assign"} disabled={!selected.length}>Assign</Button>
        </form>
      )}
    </div>
  );
}

export function PriorityPanel({ issue, onChanged }) {
  const [score, setScore] = useState("");
  const [reason, setReason] = useState("");
  const { busy, message, run } = useAction();
  const { assessment, override } = issue.priority;
  return (
    <div className="space-y-4">
      {override && (
        <Alert variant="info" title={`Overridden to ${override.band} (${Number(override.score).toFixed(0)})`}>
          {override.reason}
        </Alert>
      )}
      <PriorityBreakdown assessment={assessment} />
      {message && <Alert variant={message.variant}>{message.text}</Alert>}
      <form className="grid gap-3 rounded-xl border border-slate-200 p-4 sm:grid-cols-[8rem_1fr_auto]" onSubmit={async (e) => {
        e.preventDefault();
        const value = Number(score);
        if (score === "" || !(value >= 0 && value <= 100) || reason.trim().length < 10) return;
        if (await run("override", () => api.post(`/issues/${issue.id}/priority/override`, { score: value, reason: reason.trim() }), "Override saved.")) {
          setScore(""); setReason(""); onChanged?.();
        }
      }}>
        <input className="input" type="number" min="0" max="100" placeholder="Score 0–100" aria-label="Override score" value={score} onChange={(e) => setScore(e.target.value)} />
        <input className="input" placeholder="Reason (at least 10 characters)" aria-label="Override reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        <Button type="submit" loading={busy === "override"}>Override</Button>
      </form>
      {override && (
        <Button variant="secondary" loading={busy === "clear"} onClick={async () => (await run("clear", () => api.delete(`/issues/${issue.id}/priority/override`), "Override cleared.")) && onChanged?.()}>
          Clear override
        </Button>
      )}
    </div>
  );
}

export function ResolutionReview({ resolutions, onChanged }) {
  const [comments, setComments] = useState({});
  const { busy, message, run } = useAction();
  if (!resolutions.length) return <p className="text-sm text-slate-500">No resolution reports yet.</p>;
  return (
    <div className="space-y-4">
      {message && <Alert variant={message.variant}>{message.text}</Alert>}
      {resolutions.map((r) => (
        <div key={r.id} className="rounded-xl border border-slate-200 p-4 text-sm">
          <div className="flex items-center justify-between">
            <p className="font-semibold text-slate-800">Cycle {r.cycle}</p>
            <Badge tone={r.status === "approved" ? "green" : r.status === "rejected" ? "red" : "orange"}>{r.status}</Badge>
          </div>
          <dl className="mt-2 space-y-1 text-slate-600">
            <div><dt className="inline text-xs text-slate-500">Was wrong: </dt><dd className="inline">{r.what_was_wrong || "—"}</dd></div>
            <div><dt className="inline text-xs text-slate-500">Root cause: </dt><dd className="inline">{r.root_cause || "—"}</dd></div>
            <div><dt className="inline text-xs text-slate-500">Action: </dt><dd className="inline">{r.action_taken || "—"}</dd></div>
            <div><dt className="inline text-xs text-slate-500">Parts: </dt><dd className="inline">{r.parts_replaced || "—"}</dd></div>
            <div><dt className="inline text-xs text-slate-500">Shown to students: </dt><dd className="inline">{r.public_summary || "—"}</dd></div>
            {r.followup_needed && <div><Badge tone="amber">Follow-up needed</Badge></div>}
          </dl>
          {r.verifier_comment && <p className="mt-2 text-xs text-slate-500">Verifier: {r.verifier_comment}</p>}
          {r.status === "submitted" && (
            <div className="mt-3 space-y-2">
              <input className="input" placeholder="Comment (required to reject)" aria-label="Verifier comment" value={comments[r.id] || ""} onChange={(e) => setComments({ ...comments, [r.id]: e.target.value })} />
              <div className="flex gap-2">
                <Button loading={busy === "ap" + r.id} onClick={async () => (await run("ap" + r.id, () => api.post(`/resolutions/${r.id}/approve`, { comment: comments[r.id]?.trim() || null }), "Approved.")) && onChanged?.()}>Approve</Button>
                <Button variant="danger" loading={busy === "rj" + r.id} disabled={(comments[r.id] || "").trim().length < 3}
                  onClick={async () => (await run("rj" + r.id, () => api.post(`/resolutions/${r.id}/reject`, { comment: comments[r.id].trim() }), "Sent back to staff.")) && onChanged?.()}>Reject</Button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export function IssueActions({ issue, onChanged }) {
  const [reason, setReason] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const categories = useResource("/reference/categories");
  const { busy, message, run } = useAction();
  const canReject = ["open", "assigned"].includes(issue.status);
  const canReopen = ["resolved", "closed"].includes(issue.status);
  const active = ["open", "assigned", "in_progress", "awaiting_verification", "reopened"].includes(issue.status);
  const ok = reason.trim().length >= 5;
  return (
    <div className="space-y-4">
      {message && <Alert variant={message.variant}>{message.text}</Alert>}
      <Field label="Reason (required for every action below)" htmlFor="action-reason">
        <input id="action-reason" className="input" value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
      {active && (
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Correct the category" htmlFor="reclass">
            <select id="reclass" className="input" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
              <option value="">Choose…</option>
              {(categories.data || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </Field>
          <Button variant="secondary" disabled={!ok || !categoryId} loading={busy === "reclass"}
            onClick={async () => (await run("reclass", () => api.patch(`/issues/${issue.id}/classification`, { category_id: Number(categoryId), reason: reason.trim(), expected_version: issue.version }), "Category corrected.")) && onChanged?.()}>
            Apply
          </Button>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {canReject && <Button variant="danger" disabled={!ok} loading={busy === "reject"} onClick={async () => (await run("reject", () => api.post(`/issues/${issue.id}/reject`, { reason: reason.trim() }), "Issue rejected.")) && onChanged?.()}>Reject as invalid</Button>}
        {canReopen && <Button variant="secondary" disabled={!ok} loading={busy === "reopen"} onClick={async () => (await run("reopen", () => api.post(`/issues/${issue.id}/reopen`, { reason: reason.trim() }), "Issue reopened.")) && onChanged?.()}>Reopen</Button>}
      </div>
    </div>
  );
}

export function HistoryList({ events }) {
  if (!events.length) return <p className="text-sm text-slate-500">No history.</p>;
  return (
    <ol className="space-y-2 text-sm" aria-label="Issue history">
      {events.map((e) => (
        <li key={e.id} className="flex flex-wrap gap-x-3">
          <span className="text-xs text-slate-400">{formatDate(e.at, { time: true })}</span>
          <span className="font-medium text-slate-700">{e.action.replaceAll("_", " ")}</span>
          <span className="text-xs text-slate-500">{e.actor_role}</span>
          {e.after?.status && <Badge tone={BAND_TONES[e.after.status] || "neutral"}>{e.before?.status ? `${e.before.status} → ` : ""}{e.after.status}</Badge>}
          {e.reason && <span className="text-xs italic text-slate-500">“{e.reason}”</span>}
        </li>
      ))}
    </ol>
  );
}
