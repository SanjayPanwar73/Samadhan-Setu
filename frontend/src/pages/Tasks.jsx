import { useState } from "react";
import { Link } from "react-router-dom";
import useResource from "../hooks/useResource";
import Tabs from "../components/Tabs";
import { BandBadge, SlaIndicator } from "../components/IssueParts";
import { Badge, Card, EmptyState, ErrorState, PageHeader, StatCard, TableSkeleton } from "../components/ui";
import { TASK_STATUS_LABELS } from "../utils/issues";

const TABS = [
  { id: "new", label: "New", match: (t) => t.status === "assigned" },
  { id: "active", label: "In progress", match: (t) => ["acknowledged", "in_progress"].includes(t.status) },
  { id: "review", label: "Awaiting verification", match: (t) => t.status === "awaiting_verification" },
  { id: "overdue", label: "Overdue", match: (t) => t.overdue },
  { id: "done", label: "Completed", match: (t) => t.status === "completed" },
];

export default function Tasks() {
  const { data, loading, error, refresh } = useResource("/tasks?limit=100");
  const [tab, setTab] = useState("new");
  const tasks = data || [];
  const current = TABS.find((t) => t.id === tab);
  const visible = tasks.filter(current.match);
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Staff workspace" title="My tasks" description="Work assigned to you by your department admin." />
      <div className="stats-grid">
        <StatCard label="New" value={tasks.filter(TABS[0].match).length} icon="bell" tone="blue" />
        <StatCard label="In progress" value={tasks.filter(TABS[1].match).length} icon="clock" tone="amber" />
        <StatCard label="Overdue" value={tasks.filter(TABS[3].match).length} icon="alertCircle" tone="red" />
        <StatCard label="Completed" value={tasks.filter(TABS[4].match).length} icon="checkCircle" tone="green" />
      </div>
      <Card>
        <div className="p-4">
          <Tabs tabs={TABS.map(({ id, label }) => ({ id, label }))} value={tab} onChange={setTab} />
        </div>
        {loading ? <TableSkeleton /> : error ? <ErrorState message={error} onRetry={refresh} /> : visible.length === 0 ? (
          <EmptyState icon="check" title="Nothing here" description="No tasks in this section." />
        ) : (
          <ul className="divide-y divide-slate-100" aria-label={`${current.label} tasks`}>
            {visible.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <Link to={`/tasks/${t.id}`} className="font-semibold text-slate-800 hover:text-brand-700">{t.title}</Link>
                  <p className="mt-1 text-xs text-slate-500">{t.ticket_no} · {t.location_path || "—"}{t.is_lead ? " · Lead" : ""}</p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <BandBadge band={t.priority_band} />
                  <SlaIndicator due={t.due_at} active={!["completed", "reassigned", "cancelled"].includes(t.status)} />
                  <Badge tone="blue">{TASK_STATUS_LABELS[t.status] || t.status}</Badge>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
