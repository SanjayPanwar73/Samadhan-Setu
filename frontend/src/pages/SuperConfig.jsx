import { useEffect, useState } from "react";
import api from "../services/api";
import useAction from "../hooks/useAction";
import useResource from "../hooks/useResource";
import Tabs from "../components/Tabs";
import { Alert, Badge, Button, Card, ErrorState, Field, PageHeader, TableSkeleton } from "../components/ui";
import { FACTOR_LABELS } from "../utils/issues";

const TABS = [
  { id: "priority", label: "Priority" },
  { id: "safety", label: "Safety rules" },
  { id: "sla", label: "SLA" },
  { id: "escalation", label: "Escalation" },
];
const BANDS = ["critical", "high", "medium", "low"];
const TRIGGERS = ["immediate", "unassigned_for", "no_progress_for", "sla_breach_risk", "sla_breached"];

/** Same rules the backend enforces: weights are non-negative and sum to exactly 1. */
export function weightsProblem(weights) {
  const values = Object.values(weights).map(Number);
  if (values.some((v) => !Number.isFinite(v) || v < 0)) return "Weights must be zero or more.";
  const sum = values.reduce((a, b) => a + b, 0);
  return Math.abs(sum - 1) > 1e-6 ? `Weights must add up to 1.00 (now ${sum.toFixed(2)}).` : "";
}
export function bandsProblem(b) {
  const v = BANDS.map((k) => Number(b[k]));
  if (v.some((x) => !Number.isFinite(x))) return "Enter a number for every band.";
  if (!(v[0] > v[1] && v[1] > v[2] && v[2] > v[3] && v[3] >= 0 && v[0] <= 100)) return "Band minimums must decrease from Critical to Low and stay within 0–100.";
  return "";
}

function PriorityTab() {
  const config = useResource("/admin/org/priority-config");
  const [weights, setWeights] = useState(null);
  const [bands, setBands] = useState(null);
  const { busy, message, run } = useAction();
  useEffect(() => {
    if (config.data) queueMicrotask(() => { setWeights(config.data.weights); setBands(config.data.bands); });
  }, [config.data]);
  if (config.loading || !weights) return <TableSkeleton rows={4} />;
  if (config.error) return <ErrorState message={config.error} onRetry={config.refresh} />;
  const problem = weightsProblem(weights) || bandsProblem(bands);
  return (
    <form className="space-y-5" onSubmit={async (e) => {
      e.preventDefault();
      if (problem) return;
      const numeric = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, Number(v)]));
      if (await run("save", () => api.put("/admin/org/priority-config", { weights: numeric(weights), bands: numeric(bands) }), "Saved as a new version. Existing assessments keep the version they used.")) config.refresh();
    }}>
      <p className="text-sm text-slate-500">Source: {config.data.source}{config.data.version ? ` · version ${config.data.version}` : ""}. Starting values need calibrating against real incidents.</p>
      {message && <Alert variant={message.variant}>{message.text}</Alert>}
      <div className="grid gap-3 sm:grid-cols-3">
        {Object.keys(weights).map((k) => (
          <Field key={k} label={FACTOR_LABELS[k] || k} htmlFor={`w-${k}`}>
            <input id={`w-${k}`} type="number" step="0.01" min="0" max="1" className="input" value={weights[k]} onChange={(e) => setWeights({ ...weights, [k]: e.target.value })} />
          </Field>))}
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        {BANDS.map((b) => (
          <Field key={b} label={`${b[0].toUpperCase()}${b.slice(1)} from`} htmlFor={`b-${b}`}>
            <input id={`b-${b}`} type="number" min="0" max="100" className="input" value={bands[b]} onChange={(e) => setBands({ ...bands, [b]: e.target.value })} />
          </Field>))}
      </div>
      {problem && <p className="field-error" role="alert">{problem}</p>}
      <Button type="submit" disabled={Boolean(problem)} loading={busy === "save"}>Save new version</Button>
    </form>
  );
}

function SafetyTab() {
  const rules = useResource("/admin/org/safety-rules");
  const [form, setForm] = useState({ name: "", pattern: "", risk_level: 0.8, floor_score: "" });
  const { busy, message, run } = useAction();
  if (rules.loading) return <TableSkeleton rows={4} />;
  if (rules.error) return <ErrorState message={rules.error} onRetry={rules.refresh} />;
  return (
    <div className="space-y-5">
      {message && <Alert variant={message.variant}>{message.text}</Alert>}
      {rules.data[0]?.builtin && <Alert variant="info">These are the built-in rules. Adding your first rule copies them into the database so you can edit them.</Alert>}
      <ul className="divide-y divide-slate-100 text-sm">
        {rules.data.map((r, i) => (
          <li key={r.id ?? `b${i}`} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span><strong>{r.name}</strong> <Badge tone="red">risk {r.risk_level}</Badge>{r.floor_score != null && <Badge className="ml-1" tone="orange">floor {r.floor_score}</Badge>}{r.is_active === false && <Badge className="ml-1">Off</Badge>}
              <code className="mt-1 block text-xs text-slate-500">{r.pattern}</code></span>
            {r.id != null && <Button variant="ghost" loading={busy === `r${r.id}`} onClick={async () => (await run(`r${r.id}`, () => api.patch(`/admin/org/safety-rules/${r.id}`, { is_active: !r.is_active }), "Rule updated.")) && rules.refresh()}>{r.is_active ? "Turn off" : "Turn on"}</Button>}
          </li>))}
      </ul>
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={async (e) => {
        e.preventDefault();
        const body = { name: form.name, pattern: form.pattern, risk_level: Number(form.risk_level), floor_score: form.floor_score === "" ? null : Number(form.floor_score) };
        if (await run("add", () => api.post("/admin/org/safety-rules", body), "Rule added.")) { setForm({ name: "", pattern: "", risk_level: 0.8, floor_score: "" }); rules.refresh(); }
      }}>
        <Field label="Name" htmlFor="sr-name"><input id="sr-name" required className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="Pattern (regular expression, any language)" htmlFor="sr-pat"><input id="sr-pat" required className="input" value={form.pattern} onChange={(e) => setForm({ ...form, pattern: e.target.value })} /></Field>
        <Field label="Risk (0–1)" htmlFor="sr-risk"><input id="sr-risk" type="number" step="0.1" min="0" max="1" className="input" value={form.risk_level} onChange={(e) => setForm({ ...form, risk_level: e.target.value })} /></Field>
        <Field label="Minimum score (optional)" htmlFor="sr-floor"><input id="sr-floor" type="number" min="0" max="100" className="input" value={form.floor_score} onChange={(e) => setForm({ ...form, floor_score: e.target.value })} /></Field>
        <div className="sm:col-span-2"><Button type="submit" loading={busy === "add"}>Add rule</Button></div>
      </form>
    </div>
  );
}

function SlaTab() {
  const policies = useResource("/admin/org/sla-policies");
  const { busy, message, run } = useAction();
  const [edit, setEdit] = useState({});
  if (policies.loading) return <TableSkeleton rows={4} />;
  if (policies.error) return <ErrorState message={policies.error} onRetry={policies.refresh} />;
  const rows = policies.data.filter((p) => p.department_id == null);
  return (
    <div className="space-y-4">
      {message && <Alert variant={message.variant}>{message.text}</Alert>}
      <p className="text-sm text-slate-500">Minutes. Deadlines are measured from the first report and do not reset when priority changes.</p>
      <div className="table-wrap"><table className="data-table"><caption className="sr-only">Global SLA policy</caption>
        <thead><tr><th scope="col">Band</th><th scope="col">Response</th><th scope="col">Resolution</th><th scope="col">No progress</th><th scope="col"><span className="sr-only">Save</span></th></tr></thead>
        <tbody>{rows.map((p) => {
          const v = edit[p.band] || p;
          const set = (k) => (e) => setEdit({ ...edit, [p.band]: { ...v, [k]: Number(e.target.value) } });
          return (
            <tr key={p.band}>
              <td className="capitalize">{p.band}</td>
              {["response_minutes", "resolution_minutes", "no_progress_minutes"].map((k) => <td key={k}><input type="number" min="1" className="input !min-h-9 max-w-28" aria-label={`${p.band} ${k.replace("_minutes", "")}`} value={v[k]} onChange={set(k)} /></td>)}
              <td><Button variant="secondary" loading={busy === p.band} onClick={async () => (await run(p.band, () => api.put("/admin/org/sla-policies", { department_id: null, band: p.band, response_minutes: v.response_minutes, resolution_minutes: v.resolution_minutes, no_progress_minutes: v.no_progress_minutes }), "SLA saved.")) && policies.refresh()}>Save</Button></td>
            </tr>);
        })}</tbody></table></div>
    </div>
  );
}

function EscalationTab() {
  const rules = useResource("/admin/org/escalation-rules");
  const [form, setForm] = useState({ band: "any", trigger: "unassigned_for", after_minutes: "", repeat_minutes: "", notify_role: "dept_admin" });
  const { busy, message, run } = useAction();
  if (rules.loading) return <TableSkeleton rows={4} />;
  if (rules.error) return <ErrorState message={rules.error} onRetry={rules.refresh} />;
  return (
    <div className="space-y-5">
      {message && <Alert variant={message.variant}>{message.text}</Alert>}
      {rules.data[0]?.builtin && <Alert variant="info">Built-in rules are in use. Adding a rule replaces them with the rules listed here.</Alert>}
      <ul className="divide-y divide-slate-100 text-sm">
        {rules.data.map((r, i) => (
          <li key={r.id ?? r.key ?? i} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span><strong>{r.trigger.replaceAll("_", " ")}</strong> · band {r.band} · after {r.after_minutes ?? "policy"} min · repeat {r.repeat_minutes ?? "once"} · notify <Badge>{r.notify_role}</Badge>{r.is_active === false && <Badge className="ml-1">Off</Badge>}</span>
            {r.id != null && <Button variant="ghost" loading={busy === `e${r.id}`} onClick={async () => (await run(`e${r.id}`, () => api.patch(`/admin/org/escalation-rules/${r.id}`, { is_active: !r.is_active }), "Rule updated.")) && rules.refresh()}>{r.is_active ? "Turn off" : "Turn on"}</Button>}
          </li>))}
      </ul>
      <form className="grid gap-3 sm:grid-cols-5" onSubmit={async (e) => {
        e.preventDefault();
        const body = { band: form.band, trigger: form.trigger, notify_role: form.notify_role, after_minutes: form.after_minutes === "" ? null : Number(form.after_minutes), repeat_minutes: form.repeat_minutes === "" ? null : Number(form.repeat_minutes) };
        if (await run("add", () => api.post("/admin/org/escalation-rules", body), "Rule added.")) rules.refresh();
      }}>
        <Field label="Band" htmlFor="er-band"><select id="er-band" className="input" value={form.band} onChange={(e) => setForm({ ...form, band: e.target.value })}><option>any</option>{BANDS.map((b) => <option key={b}>{b}</option>)}</select></Field>
        <Field label="Trigger" htmlFor="er-trig"><select id="er-trig" className="input" value={form.trigger} onChange={(e) => setForm({ ...form, trigger: e.target.value })}>{TRIGGERS.map((t) => <option key={t}>{t}</option>)}</select></Field>
        <Field label="After (min)" htmlFor="er-after"><input id="er-after" type="number" min="0" className="input" value={form.after_minutes} onChange={(e) => setForm({ ...form, after_minutes: e.target.value })} /></Field>
        <Field label="Repeat (min)" htmlFor="er-rep"><input id="er-rep" type="number" min="1" className="input" value={form.repeat_minutes} onChange={(e) => setForm({ ...form, repeat_minutes: e.target.value })} /></Field>
        <Field label="Notify" htmlFor="er-role"><select id="er-role" className="input" value={form.notify_role} onChange={(e) => setForm({ ...form, notify_role: e.target.value })}><option>dept_admin</option><option>hod</option><option>super_admin</option></select></Field>
        <div className="sm:col-span-5"><Button type="submit" loading={busy === "add"}>Add rule</Button></div>
      </form>
    </div>
  );
}

export default function SuperConfig() {
  const [tab, setTab] = useState("priority");
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Administration" title="Priority, SLA and escalation" description="Changes are versioned and audited. Weights, SLA values and rules are starting points to calibrate on real incidents." />
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      <Card className="p-6">
        {tab === "priority" && <PriorityTab />}
        {tab === "safety" && <SafetyTab />}
        {tab === "sla" && <SlaTab />}
        {tab === "escalation" && <EscalationTab />}
      </Card>
    </div>
  );
}
