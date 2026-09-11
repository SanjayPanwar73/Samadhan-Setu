import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import usePagedResource from "../hooks/usePagedResource";
import {
  formatDate,
  isOpen,
  isOverdue,
  matchesPriority,
  STATUS_OPTIONS,
} from "../utils/complaints";
import { getDisplayName } from "../utils/auth";
import ComplaintTable from "./ComplaintTable";
import Icon from "./Icon";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  StatCard,
  StatusBadge,
  TableSkeleton,
} from "./ui";

function WelcomeArt() {
  return (
    <svg
      className="welcome-art"
      viewBox="0 0 200 145"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="108" cy="75" r="64" fill="#e1ecdf" />
      <circle cx="170" cy="35" r="5" fill="#c4d9c3" />
      <circle cx="30" cy="112" r="3" fill="#adcbaa" />
      <g transform="rotate(9 115 72)">
        <rect
          x="83"
          y="21"
          width="77"
          height="103"
          rx="9"
          fill="#cadfcb"
          stroke="#a9c9ae"
        />
      </g>
      <g transform="rotate(-8 100 75)">
        <rect
          x="59"
          y="24"
          width="77"
          height="102"
          rx="9"
          fill="#fff"
          stroke="#c2d7c7"
        />
        <rect x="76" y="43" width="27" height="6" rx="3" fill="#d7e8d8" />
        <path
          d="M77 64h39M77 75h31M77 86h23"
          stroke="#d7e2d7"
          strokeWidth="4"
          strokeLinecap="round"
        />
        <circle cx="118" cy="104" r="19" fill="#39825b" />
        <path
          d="m109 104 6 6 11-12"
          stroke="white"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>
      <path
        d="M165 121V78m0 25c-12 0-19-8-19-17 12 0 19 8 19 17Zm0-11c12 0 17-8 17-17-12 0-17 8-17 17Z"
        stroke="#91b79a"
        strokeWidth="2"
        fill="#c0d7bc"
      />
      <path
        d="M26 128h156"
        stroke="#cbddc9"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function ComplaintWorkspace({ staff = false }) {
  const { user } = useAuth();
  const {
    data: complaints,
    loading,
    loadingMore,
    error,
    hasMore,
    refresh,
    loadMore,
    retry,
  } = usePagedResource(staff ? "/complaints/assigned" : "/complaints/me");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [priority, setPriority] = useState("all");
  const [sort, setSort] = useState(staff ? "priority" : "recent");
  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return complaints
      .filter(
        (item) =>
          (status === "all" || item.status === status) &&
          (priority === "all" ||
            matchesPriority(item.priority_score, priority)) &&
          (!term ||
            `${item.id} ${item.title} ${item.category || ""}`
              .toLowerCase()
              .includes(term)),
      )
      .sort((a, b) =>
        sort === "priority"
          ? (b.priority_score ?? -1) - (a.priority_score ?? -1)
          : new Date(b.created_at) - new Date(a.created_at),
      );
  }, [complaints, query, status, priority, sort]);
  const counts = useMemo(
    () =>
      Object.fromEntries(
        STATUS_OPTIONS.map((value) => [
          value,
          complaints.filter((item) => item.status === value).length,
        ]),
      ),
    [complaints],
  );
  const active = complaints.filter(isOpen).length;
  const overdue = complaints.filter(isOverdue).length;
  const ready = !loading && !error;
  const name = getDisplayName(user).split(" ")[0];
  const filteredActive = Boolean(
    query || status !== "all" || priority !== "all",
  );
  const clearFilters = () => {
    setQuery("");
    setStatus("all");
    setPriority("all");
  };
  const scope = hasMore ? "Across loaded complaints" : "Across your complaints";
  const latest = [...complaints]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 3);
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={staff ? "Your workspace" : "Your overview"}
        title={staff ? "Let’s make progress." : `Welcome back, ${name}.`}
        description={
          staff
            ? "A focused view of the concerns assigned to you. Prioritize, act, and keep things moving."
            : "Every concern matters. Here’s where things stand with yours."
        }
        actions={
          <>
            {staff && (
              <Button
                variant="secondary"
                disabled={loading || loadingMore}
                onClick={refresh}
              >
                <Icon name="refresh" size={16} />
                Refresh
              </Button>
            )}
            {!staff && (
              <Link to="/complaints/new" className="btn btn-primary">
                <Icon name="plus" size={17} />
                New complaint
              </Link>
            )}
          </>
        }
      />
      <div className="welcome-banner">
        <div>
          <Badge tone="green">
            {staff ? "Make an impact" : "Your voice, a clear path forward"}
          </Badge>
          <h2 className="mt-3">
            {staff
              ? "Good resolutions start with the next step."
              : "A better community starts with you."}
          </h2>
          <p>
            {staff
              ? "Review priorities, follow up on open concerns, and share a resolution note to help your team learn."
              : "Report a concern, follow its progress, and help us make things better. We’ll keep everything together, right here."}
          </p>
        </div>
        <WelcomeArt />
      </div>
      <div className="stats-grid">
        <StatCard
          label={
            hasMore
              ? "Complaints loaded"
              : staff
                ? "Assigned complaints"
                : "Total complaints"
          }
          value={ready ? complaints.length : null}
          icon="file"
          hint={
            hasMore
              ? "Load more below to expand this view"
              : staff
                ? "All concerns assigned to you"
                : "All your submitted records"
          }
        />
        <StatCard
          label="Open concerns"
          value={ready ? active : null}
          icon="clock"
          tone="amber"
          hint={
            ready
              ? `${counts.reopened || 0} reopened · ${counts.pending || 0} pending`
              : "Pending, in progress, and reopened"
          }
        />
        <StatCard
          label={staff ? "Past due" : "In progress"}
          value={ready ? (staff ? overdue : counts.in_progress || 0) : null}
          icon={staff ? "alertCircle" : "chart"}
          tone={staff ? "orange" : "blue"}
          hint={
            staff
              ? "Open concerns past their SLA deadline"
              : "Your team is working on these"
          }
        />
        <StatCard
          label="Resolved"
          value={ready ? counts.resolved || 0 : null}
          icon="checkCircle"
          hint={scope}
        />
      </div>
      <Card>
        <div className="panel-heading">
          <div className="flex items-center gap-2.5">
            <h2>{staff ? "Your assigned queue" : "My complaints"}</h2>
            {ready && (
              <Badge>
                {complaints.length}
                {hasMore ? "+" : ""}
              </Badge>
            )}
          </div>
          <Button
            variant="ghost"
            className="!min-h-8 !px-2 !py-1 !text-xs"
            disabled={loading || loadingMore}
            onClick={refresh}
          >
            <Icon name="refresh" size={14} />
            Refresh
          </Button>
        </div>
        <div className="toolbar">
          <div className="search-field">
            <Icon name="search" size={16} />
            <input
              className="input"
              type="search"
              aria-label="Search loaded complaints"
              placeholder="Search by title, category, or ID…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              aria-label="Filter by status"
              className="input filter-select"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="all">All statuses</option>
              {STATUS_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value.replaceAll("_", " ")}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter by priority"
              className="input filter-select"
              value={priority}
              onChange={(event) => setPriority(event.target.value)}
            >
              <option value="all">All priorities</option>
              {["critical", "high", "medium", "low"].map((value) => (
                <option key={value} value={value}>
                  {value[0].toUpperCase() + value.slice(1)}
                </option>
              ))}
            </select>
            <select
              aria-label="Sort complaints"
              className="input filter-select"
              value={sort}
              onChange={(event) => setSort(event.target.value)}
            >
              <option value="recent">Newest first</option>
              <option value="priority">Highest priority</option>
            </select>
          </div>
        </div>
        {hasMore && (
          <p className="px-6 pb-3 text-[11px] text-slate-500">
            Search, filters, and summaries cover {complaints.length} loaded
            records. Load more to include older or lower-priority complaints.
          </p>
        )}
        {loading ? (
          <TableSkeleton />
        ) : error && !complaints.length ? (
          <ErrorState message={error} onRetry={refresh} />
        ) : (
          <>
            {error && (
              <div className="mx-5 mb-4">
                <Alert variant="error">
                  {error}{" "}
                  <button type="button" className="underline" onClick={retry}>
                    Retry
                  </button>
                </Alert>
              </div>
            )}
            {!complaints.length ? (
              <EmptyState
                icon={staff ? "checkCircle" : "file"}
                title={
                  staff
                    ? "Your queue is clear"
                    : "Your first step toward a resolution"
                }
                description={
                  staff
                    ? "When a concern is assigned to you, it will appear here."
                    : "Have something that needs attention? Submit your first complaint and follow its progress here."
                }
                action={
                  !staff && (
                    <Link to="/complaints/new" className="btn btn-primary">
                      <Icon name="plus" size={16} />
                      Submit a complaint
                    </Link>
                  )
                }
              />
            ) : !filtered.length ? (
              <EmptyState
                icon="search"
                title="No matching complaints"
                description="Try a different search or clear your filters. You can also load more records below."
                action={
                  <Button variant="secondary" onClick={clearFilters}>
                    Clear filters
                  </Button>
                }
              />
            ) : (
              <ComplaintTable complaints={filtered} showDepartment={staff} />
            )}
            {complaints.length > 0 && (
              <div className="pagination">
                <p aria-live="polite">
                  Showing {filtered.length} of {complaints.length} loaded
                  complaints{!hasMore && " · All records loaded"}
                </p>
                <div className="flex gap-2">
                  {filteredActive && (
                    <Button variant="ghost" onClick={clearFilters}>
                      Clear filters
                    </Button>
                  )}
                  {hasMore && (
                    <Button
                      variant="secondary"
                      onClick={loadMore}
                      loading={loadingMore}
                    >
                      Load more <Icon name="chevronDown" size={14} />
                    </Button>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </Card>
      {ready && complaints.length > 0 && (
        <div className="dashboard-bottom">
          <Card>
            <div className="panel-heading">
              <div>
                <h2>Resolution snapshot</h2>
                <p>{scope}</p>
              </div>
              <Icon name="chart" size={18} className="text-slate-400" />
            </div>
            <div className="p-6">
              <div className="mb-5 flex items-end justify-between">
                <div>
                  <span className="text-3xl font-semibold tracking-tight text-brand-900">
                    {Math.round(
                      ((counts.resolved || 0) / complaints.length) * 100,
                    )}
                    %
                  </span>
                  <p className="mt-1 text-xs text-slate-500">
                    of loaded concerns resolved
                  </p>
                </div>
                <Badge tone="green">{counts.resolved || 0} resolved</Badge>
              </div>
              <div className="summary-track" aria-hidden="true">
                {STATUS_OPTIONS.filter((value) => counts[value]).map(
                  (value) => (
                    <span
                      key={value}
                      style={{
                        width: `${(counts[value] / complaints.length) * 100}%`,
                        background: {
                          pending: "#e7c76d",
                          in_progress: "#8fb0e3",
                          reopened: "#e5a276",
                          resolved: "#6aa587",
                          rejected: "#d79595",
                        }[value],
                      }}
                    />
                  ),
                )}
              </div>
              <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3">
                {STATUS_OPTIONS.map((value) => (
                  <div
                    key={value}
                    className="flex items-center justify-between text-xs"
                  >
                    <dt className="text-slate-500 capitalize">
                      {value.replaceAll("_", " ")}
                    </dt>
                    <dd className="font-medium text-slate-700">
                      {counts[value] || 0}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </Card>
          <Card>
            <div className="panel-heading">
              <div>
                <h2>Recent submissions</h2>
                <p>The newest concerns in this view</p>
              </div>
              <Icon name="clock" size={18} className="text-slate-400" />
            </div>
            <div className="px-6 py-2">
              {latest.map((item) => (
                <div key={item.id} className="activity-item">
                  <div className="activity-dot">
                    <Icon name="file" size={15} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <Link
                      to={`/complaints/${item.id}`}
                      className="table-link text-xs"
                    >
                      {item.title}
                    </Link>
                    <p className="mt-1 text-[10px] text-slate-500">
                      #{item.id} · Submitted {formatDate(item.created_at)}
                    </p>
                  </div>
                  <StatusBadge status={item.status} />
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
