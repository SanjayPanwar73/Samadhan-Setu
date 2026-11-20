import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import useResource from "../hooks/useResource";
import { Badge, Card, EmptyState, ErrorState, PageHeader, StatCard, TableSkeleton } from "../components/ui";
import { formatDate } from "../utils/complaints";

/** Head of department: aggregates only. No individual student or complaint data is requested. */
export default function Hod() {
  const { user } = useAuth();
  const departments = useResource("/reference/departments");
  const [deptId, setDeptId] = useState("");
  const q = deptId ? `?department_id=${deptId}` : "";
  const summary = useResource(`/reports/department-summary${q}`);
  const times = useResource(`/reports/resolution-times${q}`);
  const workload = useResource(`/reports/staff-workload${q}`);
  const satisfaction = useResource(`/reports/satisfaction${q}`);
  const repeats = useResource(`/reports/repeat-failures${q}`);
  const trends = useResource(`/reports/trends${q}`);
  const escalations = useResource(`/reports/escalations${q}`);
  const mine = (departments.data || []).filter((d) => !user?.department_ids || user.is_global || user.department_ids.includes(d.id));
  const s = summary.data;
  const maxTrend = Math.max(1, ...(trends.data || []).map((t) => Math.max(t.opened, t.resolved)));
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Head of department" title="Department overview" description="Totals and trends only. Individual students are never shown here."
        actions={mine.length > 1 && (
          <select className="input filter-select" aria-label="Department" value={deptId} onChange={(e) => setDeptId(e.target.value)}>
            <option value="">All my departments</option>
            {mine.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        )} />
      {summary.error ? <Card><ErrorState message={summary.error} onRetry={summary.refresh} /></Card> : (
        <div className="stats-grid">
          <StatCard label="Issues" value={s?.total_issues} icon="grid" tone="blue" hint={s ? `${s.total_reports} reports` : undefined} />
          <StatCard label="Critical / high" value={s?.critical_or_high} icon="alertCircle" tone="red" />
          <StatCard label="Overdue" value={s?.overdue} icon="clock" tone="red" />
          <StatCard label="Escalated" value={s?.escalated} icon="shield" tone="orange" />
          <StatCard label="Avg resolution" value={s?.avg_resolution_hours != null ? `${s.avg_resolution_hours} h` : null} icon="chart" tone="blue" hint={s?.median_resolution_hours != null ? `median ${s.median_resolution_hours} h` : undefined} />
          <StatCard label="Reopen rate" value={s ? `${Math.round(s.reopen_rate * 100)}%` : null} icon="refresh" tone="amber" />
          <StatCard label="Satisfaction" value={satisfaction.data?.satisfaction_rate != null ? `${Math.round(satisfaction.data.satisfaction_rate * 100)}%` : null} icon="checkCircle" tone="green" hint={satisfaction.data?.avg_rating != null ? `avg rating ${satisfaction.data.avg_rating}` : undefined} />
        </div>
      )}
      <Card className="p-6">
        <h2 className="mb-3 text-lg font-semibold text-slate-800">Weekly trend</h2>
        {trends.loading ? <TableSkeleton rows={3} /> : trends.error ? <ErrorState message={trends.error} onRetry={trends.refresh} /> : (
          <table className="data-table"><caption className="sr-only">Issues opened and resolved per week</caption>
            <thead><tr><th scope="col">Week</th><th scope="col">Opened</th><th scope="col">Resolved</th></tr></thead>
            <tbody>{trends.data.map((t) => (
              <tr key={t.weeks_ago}>
                <td>{t.weeks_ago === 0 ? "This week" : `${t.weeks_ago} wk ago`}</td>
                <td><div className="flex items-center gap-2"><div className="h-2 rounded bg-amber-400" style={{ width: `${(t.opened / maxTrend) * 120}px` }} />{t.opened}</div></td>
                <td><div className="flex items-center gap-2"><div className="h-2 rounded bg-green-500" style={{ width: `${(t.resolved / maxTrend) * 120}px` }} />{t.resolved}</div></td>
              </tr>))}</tbody></table>
        )}
      </Card>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Resolution time by category</h2>
          {(times.data || []).length === 0 ? <p className="text-sm text-slate-500">No resolved issues yet.</p> : (
            <table className="data-table"><thead><tr><th scope="col">Category</th><th scope="col">Count</th><th scope="col">Avg h</th><th scope="col">Median h</th></tr></thead>
              <tbody>{times.data.map((r) => <tr key={r.category}><td>{r.category}</td><td>{r.count}</td><td>{r.avg_hours}</td><td>{r.median_hours}</td></tr>)}</tbody></table>
          )}
        </Card>
        <Card className="p-6">
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Staff workload</h2>
          {(workload.data || []).length === 0 ? <p className="text-sm text-slate-500">No assignments yet.</p> : (
            <table className="data-table"><thead><tr><th scope="col">Staff</th><th scope="col">Active</th><th scope="col">Overdue</th><th scope="col">Done</th></tr></thead>
              <tbody>{workload.data.map((r) => <tr key={r.staff_id}><td>{r.name}</td><td>{r.active}</td><td>{r.overdue ? <Badge tone="red">{r.overdue}</Badge> : 0}</td><td>{r.completed}</td></tr>)}</tbody></table>
          )}
        </Card>
        <Card className="p-6">
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Repeated failures (90 days)</h2>
          {(repeats.data || []).length === 0 ? <p className="text-sm text-slate-500">No repeated failures.</p> : (
            <ul className="space-y-1 text-sm">{repeats.data.map((r) => <li key={`${r.kind}-${r.id}`}>{r.kind === "asset" ? "Asset" : "Location"} #{r.id}: <strong>{r.issues_90d}</strong> issues</li>)}</ul>
          )}
        </Card>
        <Card className="p-6">
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Escalation log</h2>
          {(escalations.data || []).length === 0 ? <EmptyState icon="shield" title="No escalations" description="Nothing has needed escalating." /> : (
            <ul className="space-y-2 text-sm">{escalations.data.map((e, idx) => <li key={idx}><span className="text-xs text-slate-400">{formatDate(e.at, { time: true })}</span> Issue #{e.issue_id} · level {e.level} · {e.reason}</li>)}</ul>
          )}
        </Card>
      </div>
    </div>
  );
}
