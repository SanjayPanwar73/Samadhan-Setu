import { useState } from "react";
import { Link } from "react-router-dom";
import usePagedResource from "../hooks/usePagedResource";
import { formatDate } from "../utils/complaints";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  TableSkeleton,
  Alert,
} from "../components/ui";
import Icon from "../components/Icon";

export default function Notifications() {
  const {
    data: notifications,
    loading,
    loadingMore,
    error,
    hasMore,
    refresh,
    loadMore,
  } = usePagedResource("/notifications");
  const [query, setQuery] = useState("");
  const term = query.trim().toLowerCase();
  const visible = notifications.filter((item) =>
    `${item.title} ${item.message}`.toLowerCase().includes(term),
  );
  return (
    <div className="page-stack mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Stay in the loop"
        title="Workspace activity"
        description="The latest updates on concerns connected to you, all in one place."
        actions={
          <Button
            variant="secondary"
            disabled={loading || loadingMore}
            onClick={refresh}
          >
            <Icon name="refresh" size={16} />
            Refresh
          </Button>
        }
      />
      <Card>
        <div className="panel-heading">
          <div>
            <h2>Recent updates</h2>
            <p>Current status summaries, ordered by latest activity.</p>
          </div>
          <Badge>
            {notifications.length}
            {hasMore ? "+" : ""} updates
          </Badge>
        </div>
        <div className="toolbar">
          <div className="search-field">
            <Icon name="search" size={16} />
            <input
              type="search"
              className="input"
              aria-label="Search loaded activity"
              placeholder="Search updates…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          {hasMore && (
            <p className="text-xs text-slate-500">
              Search covers loaded updates.
            </p>
          )}
        </div>
        {loading ? (
          <TableSkeleton />
        ) : error && !notifications.length ? (
          <ErrorState message={error} onRetry={refresh} />
        ) : (
          <>
            {error && (
              <div className="mx-5 mb-4">
                <Alert variant="error">{error}</Alert>
              </div>
            )}
            {!notifications.length ? (
              <EmptyState
                icon="bell"
                title="Nothing to catch up on"
                description="As your complaints move forward, their latest updates will appear here."
              />
            ) : !visible.length ? (
              <EmptyState
                icon="search"
                title="No matching updates"
                description="Try another search, or load more activity below."
                action={
                  <Button variant="secondary" onClick={() => setQuery("")}>
                    Clear search
                  </Button>
                }
              />
            ) : (
              <ul className="divide-y divide-slate-100">
                {visible.map((item) => (
                  <li
                    key={item.id}
                    className="group flex items-start gap-3 px-4 py-5 transition-colors hover:bg-brand-50/40 sm:gap-4 sm:px-6"
                  >
                    <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-brand-100 bg-brand-50 text-brand-500">
                      <Icon name="file" size={18} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                        <h3 className="text-sm font-semibold text-slate-700">
                          {item.title}
                        </h3>
                        <time
                          dateTime={item.created_at}
                          className="text-[11px] text-slate-500"
                        >
                          {formatDate(item.created_at, { time: true })}
                        </time>
                      </div>
                      <p className="mt-1.5 text-xs leading-6 text-slate-500">
                        {item.message}
                      </p>
                      {item.complaint_id && (
                        <Link
                          to={`/complaints/${item.complaint_id}`}
                          className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-brand-600 hover:underline"
                        >
                          View complaint <Icon name="arrowRight" size={13} />
                        </Link>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {notifications.length > 0 && (
              <div className="pagination">
                <p aria-live="polite">
                  {visible.length} of {notifications.length} loaded updates
                </p>
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
            )}
          </>
        )}
      </Card>
    </div>
  );
}
