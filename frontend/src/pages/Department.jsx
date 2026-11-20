import { useState } from "react";
import { Link } from "react-router-dom";
import useResource from "../hooks/useResource";
import IssueFilters, { EMPTY_FILTERS } from "../components/IssueFilters";
import IssueQueueTable from "../components/IssueQueueTable";
import { Button, Card, ErrorState, PageHeader, Pagination, StatCard, TableSkeleton } from "../components/ui";
import { toQuery } from "../utils/issues";

const PAGE = 25;

export default function Department() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(0);
  const deptParam = filters.department_id ? `?department_id=${filters.department_id}` : "";
  const summary = useResource(`/reports/department-summary${deptParam}`);
  const departments = useResource("/reference/departments");
  const issues = useResource(`/issues${toQuery({ ...filters, offset: page * PAGE, limit: PAGE })}`);
  const s = summary.data;
  const list = issues.data;
  const apply = (next) => { setFilters(next); setPage(0); };
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Department" title="Issue queue" description="One row per shared issue, ordered by priority."
        actions={<Link className="btn btn-secondary" to="/department/staff">Staff workload</Link>} />
      <div className="stats-grid">
        <StatCard label="Unassigned" value={s?.unassigned} icon="bell" tone="amber" />
        <StatCard label="Critical / high" value={s?.critical_or_high} icon="alertCircle" tone="red" />
        <StatCard label="In progress" value={s?.by_status?.in_progress ?? (s ? 0 : null)} icon="clock" tone="blue" />
        <StatCard label="Awaiting verification" value={s?.by_status?.awaiting_verification ?? (s ? 0 : null)} icon="check" tone="orange" />
        <StatCard label="Resolved (feedback open)" value={s?.by_status?.resolved ?? (s ? 0 : null)} icon="checkCircle" tone="green" />
        <StatCard label="Reopened" value={s?.reopened_issues} icon="refresh" tone="orange" />
        <StatCard label="Overdue" value={s?.overdue} icon="clock" tone="red" />
        <StatCard label="Escalated" value={s?.escalated} icon="shield" tone="red" />
        <StatCard label="Avg resolution" value={s?.avg_resolution_hours != null ? `${s.avg_resolution_hours} h` : null} icon="chart" tone="blue" />
      </div>
      <Card>
        <div className="p-4"><IssueFilters filters={filters} onChange={apply} departments={departments.data || []} /></div>
        {issues.loading && !list ? <TableSkeleton /> : issues.error ? <ErrorState message={issues.error} onRetry={issues.refresh} /> : (
          <>
            <IssueQueueTable issues={list.items} emptyAction={<Button variant="secondary" onClick={() => apply(EMPTY_FILTERS)}>Clear filters</Button>} />
            <Pagination page={page} pageSize={PAGE} count={list.items.length} hasMore={(page + 1) * PAGE < list.total}
              loading={issues.loading} onPrevious={() => setPage((p) => Math.max(0, p - 1))} onNext={() => setPage((p) => p + 1)} />
          </>
        )}
      </Card>
    </div>
  );
}
