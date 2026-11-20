import { Link } from "react-router-dom";
import usePagedResource from "../hooks/usePagedResource";
import { formatDate } from "../utils/complaints";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, TableSkeleton } from "../components/ui";
import Icon from "../components/Icon";

export default function Complaints() {
  const { data, loading, loadingMore, error, hasMore, refresh, loadMore } =
    usePagedResource("/complaints/me");
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Your workspace"
        title="My complaints"
        description="Every complaint you have raised, and where it stands."
        actions={<Link className="btn btn-primary" to="/complaints/new"><Icon name="plus" size={16} /> New complaint</Link>}
      />
      <Card>
        {loading ? (
          <TableSkeleton />
        ) : error ? (
          <ErrorState message={error} onRetry={refresh} />
        ) : data.length === 0 ? (
          <EmptyState icon="search" title="No complaints yet" description="When you report a problem it will appear here."
            action={<Link className="btn btn-primary" to="/complaints/new">Raise a complaint</Link>} />
        ) : (
          <>
            <ul className="divide-y divide-slate-100">
              {data.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                  <div className="min-w-0">
                    <Link to={`/complaints/${c.id}`} className="font-semibold text-slate-800 hover:text-brand-700">{c.title}</Link>
                    <p className="mt-1 text-xs text-slate-500">
                      #{c.id}{c.ticket_no ? ` · ${c.ticket_no}` : ""} · {c.department_name || "Awaiting routing"} · {c.location_path || "—"} · {formatDate(c.created_at)}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {c.is_anonymous && <Badge>Anonymous</Badge>}
                    {c.feedback_state === "pending" && <Badge tone="orange">Feedback needed</Badge>}
                    <Badge tone={c.status === "resolved" ? "green" : c.status === "rejected" ? "red" : "blue"}>{c.status_label}</Badge>
                  </div>
                </li>
              ))}
            </ul>
            {hasMore && (
              <div className="p-4 text-center">
                <Button variant="secondary" loading={loadingMore} onClick={loadMore}>Load more</Button>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
