import { Link } from "react-router-dom";
import api from "../services/api";
import usePagedResource from "../hooks/usePagedResource";
import useAction from "../hooks/useAction";
import { formatDate } from "../utils/complaints";
import { Alert, Badge, Button, Card, EmptyState, ErrorState, PageHeader, TableSkeleton } from "../components/ui";
import { useAuth } from "../contexts/AuthContext";
import { hasRole } from "../utils/auth";

function targetFor(n, role) {
  if (hasRole(role, "student") && n.complaint_id) return `/complaints/${n.complaint_id}`;
  if (hasRole(role, "staff") && n.issue_id) return "/tasks";
  if (hasRole(role, "dept_admin", "super_admin") && n.issue_id) return `/department/issues/${n.issue_id}`;
  return null;
}

export default function Notifications() {
  const { role } = useAuth();
  const { data, setData, loading, loadingMore, error, hasMore, refresh, loadMore } = usePagedResource("/notifications");
  const { message, run } = useAction();
  const unread = data.filter((n) => !n.is_read).length;

  async function markRead(n) {
    if (n.is_read) return;
    try {
      await api.post(`/notifications/${n.id}/read`);
      setData((rows) => rows.map((r) => (r.id === n.id ? { ...r, is_read: true } : r)));
    } catch { /* leave it unread; the next open retries */ }
  }

  return (
    <div className="page-stack mx-auto max-w-3xl">
      <PageHeader eyebrow="Activity" title="Notifications" description="Updates about your complaints, tasks and issues."
        actions={<Button variant="secondary" disabled={!unread} onClick={async () => (await run("all", () => api.post("/notifications/read-all"))) && refresh()}>Mark all read</Button>} />
      {message && <Alert variant={message.variant}>{message.text}</Alert>}
      <Card>
        {loading ? <TableSkeleton /> : error ? <ErrorState message={error} onRetry={refresh} /> : data.length === 0 ? (
          <EmptyState icon="bell" title="You are all caught up" description="New updates will appear here." />
        ) : (
          <>
            <ul className="divide-y divide-slate-100" aria-label="Notifications">
              {data.map((n) => {
                const to = targetFor(n, role);
                return (
                  <li key={n.id} className={`flex gap-3 p-4 ${n.is_read ? "" : "bg-brand-50/40"}`}>
                    <span className={`mt-2 h-2 w-2 shrink-0 rounded-full ${n.is_read ? "bg-transparent" : "bg-brand-500"}`} aria-hidden="true" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-slate-800">{n.title}{n.count > 1 && <Badge className="ml-2">{n.count}</Badge>}{!n.is_read && <span className="sr-only"> (unread)</span>}</p>
                      <p className="mt-1 text-sm text-slate-600">{n.body}</p>
                      <p className="mt-1 text-xs text-slate-400">{formatDate(n.created_at, { time: true })}</p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      {to && <Link className="text-xs text-brand-700 underline" to={to} onClick={() => markRead(n)}>Open</Link>}
                      {!n.is_read && <button type="button" className="text-xs text-slate-500 underline" onClick={() => markRead(n)}>Mark read</button>}
                    </div>
                  </li>
                );
              })}
            </ul>
            {hasMore && <div className="p-4 text-center"><Button variant="secondary" loading={loadingMore} onClick={loadMore}>Load more</Button></div>}
          </>
        )}
      </Card>
    </div>
  );
}
