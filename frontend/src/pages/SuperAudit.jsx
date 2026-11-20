import { useState } from "react";
import useResource from "../hooks/useResource";
import { Button, Card, ErrorState, Field, PageHeader, Pagination, TableSkeleton } from "../components/ui";
import { formatDate } from "../utils/complaints";
import { toQuery } from "../utils/issues";

const PAGE = 50;

export default function SuperAudit() {
  const [filters, setFilters] = useState({ entity_type: "", entity_id: "", actor_id: "", issue_id: "" });
  const [page, setPage] = useState(0);
  const audit = useResource(`/admin/org/audit${toQuery({ ...filters, offset: page * PAGE, limit: PAGE + 1 })}`);
  const rows = (audit.data || []).slice(0, PAGE);
  const set = (key) => (e) => { setFilters({ ...filters, [key]: e.target.value }); setPage(0); };
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Administration" title="Audit trail" description="Append-only. Every status change, assignment, override, role change and identity reveal is recorded." />
      <Card className="p-4">
        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="Entity type" htmlFor="au-type"><select id="au-type" className="input" value={filters.entity_type} onChange={set("entity_type")}><option value="">Any</option>{["issue", "complaint", "assignment", "resolution_report", "user", "department", "category", "asset", "location", "priority_config", "safety_rule", "sla_policy", "escalation_rule"].map((t) => <option key={t}>{t}</option>)}</select></Field>
          <Field label="Entity id" htmlFor="au-eid"><input id="au-eid" type="number" min="1" className="input" value={filters.entity_id} onChange={set("entity_id")} /></Field>
          <Field label="Actor id" htmlFor="au-actor"><input id="au-actor" type="number" min="1" className="input" value={filters.actor_id} onChange={set("actor_id")} /></Field>
          <Field label="Issue id" htmlFor="au-issue"><input id="au-issue" type="number" min="1" className="input" value={filters.issue_id} onChange={set("issue_id")} /></Field>
        </div>
      </Card>
      <Card>
        {audit.loading && !audit.data ? <TableSkeleton /> : audit.error ? <ErrorState message={audit.error} onRetry={audit.refresh} /> : (
          <>
            <div className="table-wrap"><table className="data-table"><caption className="sr-only">Audit events</caption>
              <thead><tr><th scope="col">When</th><th scope="col">Action</th><th scope="col">Actor</th><th scope="col">Entity</th><th scope="col">Change</th></tr></thead>
              <tbody>{rows.map((e) => (
                <tr key={e.id}>
                  <td className="whitespace-nowrap text-xs">{formatDate(e.created_at, { time: true })}</td>
                  <td className="font-medium">{e.action.replaceAll("_", " ")}{e.reason && <p className="text-xs font-normal italic text-slate-500">“{e.reason}”</p>}</td>
                  <td className="text-xs">{e.actor_role}{e.actor_id ? ` #${e.actor_id}` : ""}</td>
                  <td className="text-xs">{e.entity_type} #{e.entity_id}{e.issue_id ? ` · issue ${e.issue_id}` : ""}</td>
                  <td className="max-w-sm text-xs text-slate-600">{e.before && <code>{JSON.stringify(e.before)}</code>}{e.before && e.after && " → "}{e.after && <code>{JSON.stringify(e.after)}</code>}</td>
                </tr>))}</tbody></table></div>
            <Pagination page={page} pageSize={PAGE} count={rows.length} hasMore={(audit.data || []).length > PAGE} loading={audit.loading}
              onPrevious={() => setPage((p) => Math.max(0, p - 1))} onNext={() => setPage((p) => p + 1)} />
          </>
        )}
      </Card>
      <div><Button variant="ghost" onClick={audit.refresh}>Refresh</Button></div>
    </div>
  );
}
