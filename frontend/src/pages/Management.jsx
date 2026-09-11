import { useState } from "react";
import { Link } from "react-router-dom";
import useResource from "../hooks/useResource";
import usePagedResource from "../hooks/usePagedResource";
import DistributionChart from "../components/DistributionChart";
import Icon from "../components/Icon";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  PriorityBadge,
  StatCard,
  StatusBadge,
  TableSkeleton,
} from "../components/ui";

function ChartCard({ title, description, resource, children }) {
  return (
    <Card>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <Button
          variant="ghost"
          className="icon-button"
          aria-label={`Refresh ${title.toLowerCase()}`}
          disabled={resource.loading}
          onClick={resource.refresh}
        >
          <Icon name="refresh" size={16} />
        </Button>
      </div>
      {resource.loading ? (
        <TableSkeleton rows={4} />
      ) : resource.error ? (
        <ErrorState message={resource.error} onRetry={resource.refresh} />
      ) : (
        children
      )}
    </Card>
  );
}
export default function Management() {
  const categories = useResource("/management/category-distribution");
  const resolution = useResource("/management/resolution-trends");
  const sla = useResource("/management/sla-violations");
  const queue = usePagedResource("/management/priority-queue");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const total = categories.data?.reduce((sum, item) => sum + item.count, 0);
  const visible = queue.data.filter(
    (item) =>
      (status === "all" || item.status === status) &&
      `${item.id} ${item.title} ${item.category || ""}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );
  const loading =
    categories.loading ||
    resolution.loading ||
    sla.loading ||
    queue.loading ||
    queue.loadingMore;
  function refreshAll() {
    void categories.refresh();
    void resolution.refresh();
    void sla.refresh();
    void queue.refresh();
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="The bigger picture"
        title="Resolution insights"
        description="Understand demand, spot overdue concerns, and focus on what needs attention."
        actions={
          <Button variant="secondary" disabled={loading} onClick={refreshAll}>
            <Icon name="refresh" size={16} />
            Refresh insights
          </Button>
        }
      />
      <div className="stats-grid">
        <StatCard
          label="Total complaints"
          value={categories.loading || categories.error ? null : total}
          icon="file"
          hint="Across all categories and statuses"
        />
        <StatCard
          label="Categories represented"
          value={
            categories.loading || categories.error
              ? null
              : categories.data?.length
          }
          icon="building"
          tone="blue"
          hint="From all submitted complaints"
        />
        <StatCard
          label="SLA breaches"
          value={
            sla.loading || sla.error ? null : sla.data?.sla_violations_count
          }
          icon="clock"
          tone="orange"
          hint="Overdue pending / in-progress concerns"
        />
        <StatCard
          label="Priority issues loaded"
          value={queue.loading || queue.error ? null : queue.data.length}
          icon="alertCircle"
          hint="Related reports grouped by the service"
        />
      </div>
      {sla.error && (
        <Alert variant="error">
          SLA summary: {sla.error}{" "}
          <button type="button" onClick={sla.refresh} className="underline">
            Retry
          </button>
        </Alert>
      )}
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <ChartCard
          title="Where concerns arise"
          description="Complaint volume by category · All submissions"
          resource={categories}
        >
          <DistributionChart data={categories.data} />
        </ChartCard>
        <ChartCard
          title="Time to resolution"
          description="Average days by category · Resolved complaints only"
          resource={resolution}
        >
          <DistributionChart
            data={resolution.data}
            valueKey="avg_resolution_days"
            unit="days"
            color="#91a6c6"
            emptyText="Resolution averages will appear once complaints have been resolved."
          />
        </ChartCard>
      </div>
      <Card>
        <div className="panel-heading">
          <div>
            <h2>Priority queue</h2>
            <p>
              Open issues ranked by priority. Similar reports are grouped
              together.
            </p>
          </div>
          <Badge>{queue.data.length} loaded</Badge>
        </div>
        <div className="toolbar">
          <div className="search-field">
            <Icon name="search" size={16} />
            <input
              className="input"
              type="search"
              aria-label="Search loaded priority issues"
              placeholder="Search issues…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <select
            className="input filter-select"
            aria-label="Filter priority queue by status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="all">All open statuses</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In progress</option>
            <option value="reopened">Reopened</option>
          </select>
        </div>
        {queue.loading ? (
          <TableSkeleton />
        ) : queue.error && !queue.data.length ? (
          <ErrorState message={queue.error} onRetry={queue.retry} />
        ) : (
          <>
            {queue.error && (
              <div className="m-5">
                <Alert variant="error">
                  {queue.error}{" "}
                  <button onClick={queue.retry} className="underline">
                    Retry
                  </button>
                </Alert>
              </div>
            )}
            {!visible.length ? (
              <EmptyState
                icon={query || status !== "all" ? "search" : "checkCircle"}
                title={
                  query || status !== "all"
                    ? "No matching issues"
                    : "The priority queue is clear"
                }
                description={
                  query || status !== "all"
                    ? "Try a different search or status filter."
                    : "Active issue groups will appear here as complaints are submitted."
                }
              />
            ) : (
              <>
                <div className="table-wrap hidden md:block">
                  <table className="data-table">
                    <caption className="sr-only">
                      Open issue groups ranked by priority
                    </caption>
                    <thead>
                      <tr>
                        {[
                          "Issue",
                          "Reports",
                          "Priority",
                          "Status",
                          "Escalation",
                          "Details",
                        ].map((label) => (
                          <th key={label} scope="col">
                            {label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {visible.map((item) => (
                        <tr key={item.id}>
                          <td className="max-w-sm">
                            <Link
                              className="table-link"
                              to={`/complaints/${item.id}`}
                            >
                              {item.title}
                            </Link>
                            <p className="mt-1 text-[10px] capitalize text-slate-500">
                              #{item.id} · {item.category || "Unclassified"}
                            </p>
                          </td>
                          <td>{item.report_count ?? 1}</td>
                          <td>
                            <PriorityBadge score={item.priority_score} />
                          </td>
                          <td>
                            <StatusBadge status={item.status} />
                          </td>
                          <td>
                            <Badge
                              tone={
                                item.escalation_level ? "orange" : "neutral"
                              }
                            >
                              Level {item.escalation_level || 0}
                            </Badge>
                          </td>
                          <td>
                            <Link
                              className="btn btn-ghost icon-button"
                              aria-label={`View complaint ${item.id}`}
                              to={`/complaints/${item.id}`}
                            >
                              <Icon name="arrowRight" size={16} />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="divide-y divide-slate-100 md:hidden">
                  {visible.map((item) => (
                    <article key={item.id} className="p-5">
                      <div className="flex justify-between gap-3">
                        <span className="text-xs text-slate-500">
                          #{item.id}
                        </span>
                        <StatusBadge status={item.status} />
                      </div>
                      <Link
                        to={`/complaints/${item.id}`}
                        className="table-link mt-3 text-sm"
                      >
                        {item.title}
                      </Link>
                      <p className="mt-2 text-xs text-slate-500">
                        {item.report_count ?? 1} reports · Escalation level{" "}
                        {item.escalation_level || 0}
                      </p>
                      <div className="mt-3">
                        <PriorityBadge score={item.priority_score} />
                      </div>
                    </article>
                  ))}
                </div>
              </>
            )}
            <div className="pagination">
              <p>
                {visible.length} of {queue.data.length} loaded issue groups ·
                Counts reflect the queue returned by the service.
              </p>
              {queue.hasMore && (
                <Button
                  variant="secondary"
                  onClick={queue.loadMore}
                  loading={queue.loadingMore}
                >
                  Load more
                </Button>
              )}
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
