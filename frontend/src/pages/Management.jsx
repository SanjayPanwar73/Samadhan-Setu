import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import api from "../services/api";

const statusStyles = {
  pending: "bg-yellow-100 text-yellow-800",
  in_progress: "bg-blue-100 text-blue-800",
  resolved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  reopened: "bg-orange-100 text-orange-800",
};

function StatusBadge({ status }) {
  const classes = statusStyles[status] || "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${classes}`}>
      {status ? status.replace("_", " ") : "—"}
    </span>
  );
}

// Shared card chrome so every section reads as one consistent dashboard,
// with its own independent loading/error/empty state region.
function DashboardCard({ title, subtitle, onRefresh, isRefreshing, className = "", children }) {
  return (
    <div className={`bg-white rounded-lg shadow p-6 ${className}`}>
      <div className="flex items-start justify-between gap-3 mb-1">
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="shrink-0 rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60"
          >
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>
        )}
      </div>
      {subtitle && <p className="text-xs text-slate-400 mb-4">{subtitle}</p>}
      {children}
    </div>
  );
}

function StateMessage({ loading, loadingText, error, onRetry, empty, emptyText }) {
  if (loading) {
    return <p className="text-center text-sm text-slate-500 py-10">{loadingText}</p>;
  }
  if (error) {
    return (
      <div className="text-center py-10">
        <p className="text-sm text-red-600">{error}</p>
        <button
          onClick={onRetry}
          className="mt-3 rounded-md bg-slate-800 text-white text-sm font-medium px-4 py-2 hover:bg-slate-700"
        >
          Try Again
        </button>
      </div>
    );
  }
  if (empty) {
    return <p className="text-center text-sm text-slate-500 py-10">{emptyText}</p>;
  }
  return null;
}

function Management() {
  const [queue, setQueue] = useState([]);
  const [isLoadingQueue, setIsLoadingQueue] = useState(true);
  const [queueError, setQueueError] = useState("");

  const [categoryData, setCategoryData] = useState([]);
  const [isLoadingCategories, setIsLoadingCategories] = useState(true);
  const [categoryError, setCategoryError] = useState("");

  const [resolutionData, setResolutionData] = useState([]);
  const [isLoadingResolution, setIsLoadingResolution] = useState(true);
  const [resolutionError, setResolutionError] = useState("");

  const [slaCount, setSlaCount] = useState(null);
  const [isLoadingSla, setIsLoadingSla] = useState(true);
  const [slaError, setSlaError] = useState("");

  // Each of the four sections below fetches, loads, and errors
  // completely independently — one endpoint failing (network blip,
  // backend bug, etc.) never blocks or blanks out the other three.

  const fetchQueue = useCallback(async () => {
    setIsLoadingQueue(true);
    setQueueError("");
    try {
      // GET /management/priority-queue — already filtered to
      // pending/in_progress and ordered by priority_score desc on
      // the backend. Rendered as-is: no re-sorting or scoring here.
      const response = await api.get("/management/priority-queue");
      setQueue(response.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setQueueError(typeof detail === "string" ? detail : "Could not load the priority queue.");
    } finally {
      setIsLoadingQueue(false);
    }
  }, []);

  const fetchCategoryDistribution = useCallback(async () => {
    setIsLoadingCategories(true);
    setCategoryError("");
    try {
      // GET /management/category-distribution -> [{ category, count }, ...]
      // Already grouped/counted on the backend.
      const response = await api.get("/management/category-distribution");
      setCategoryData(response.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setCategoryError(typeof detail === "string" ? detail : "Could not load category data.");
    } finally {
      setIsLoadingCategories(false);
    }
  }, []);

  const fetchResolutionTrends = useCallback(async () => {
    setIsLoadingResolution(true);
    setResolutionError("");
    try {
      // GET /management/resolution-trends -> [{ category, avg_resolution_days }, ...]
      // Average resolution time grouped by category (resolved complaints
      // only), already computed on the backend — not a date-based series.
      const response = await api.get("/management/resolution-trends");
      setResolutionData(response.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setResolutionError(typeof detail === "string" ? detail : "Could not load resolution trend data.");
    } finally {
      setIsLoadingResolution(false);
    }
  }, []);

  const fetchSlaViolations = useCallback(async () => {
    setIsLoadingSla(true);
    setSlaError("");
    try {
      // GET /management/sla-violations -> { sla_violations_count: number }
      const response = await api.get("/management/sla-violations");
      setSlaCount(response.data.sla_violations_count);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setSlaError(typeof detail === "string" ? detail : "Could not load SLA violation data.");
    } finally {
      setIsLoadingSla(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void fetchQueue();
      void fetchCategoryDistribution();
      void fetchResolutionTrends();
      void fetchSlaViolations();
    });
  }, [fetchQueue, fetchCategoryDistribution, fetchResolutionTrends, fetchSlaViolations]);

  return (
    <div className="min-h-screen bg-slate-50 p-6 lg:p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-800">Management Dashboard</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Live overview of complaint priority, category trends, and SLA health
        </p>
      </header>

      <div className="space-y-6 max-w-7xl">
        {/* SLA violations — prominent full-width banner */}
        <div
          className={`rounded-lg shadow p-6 border ${
            isLoadingSla || slaError
              ? "bg-white border-slate-200"
              : slaCount > 0
              ? "bg-red-50 border-red-200"
              : "bg-green-50 border-green-200"
          }`}
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-800">SLA Violations</h2>
            <button
              onClick={fetchSlaViolations}
              disabled={isLoadingSla}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60 bg-white"
            >
              {isLoadingSla ? "Refreshing..." : "Refresh"}
            </button>
          </div>

          {isLoadingSla && (
            <p className="mt-3 text-sm text-slate-500">Loading SLA violation count...</p>
          )}

          {!isLoadingSla && slaError && (
            <div className="mt-3">
              <p className="text-sm text-red-600">{slaError}</p>
              <button
                onClick={fetchSlaViolations}
                className="mt-3 rounded-md bg-slate-800 text-white text-sm font-medium px-4 py-2 hover:bg-slate-700"
              >
                Try Again
              </button>
            </div>
          )}

          {!isLoadingSla && !slaError && slaCount === 0 && (
            <p className="mt-3 text-4xl font-bold text-green-700">
              0 <span className="text-base font-medium text-green-700/80">— no active SLA breaches</span>
            </p>
          )}

          {!isLoadingSla && !slaError && slaCount > 0 && (
            <p className="mt-3 text-4xl font-bold text-red-700">
              {slaCount} <span className="text-base font-medium text-red-700/80">complaints past their SLA deadline</span>
            </p>
          )}
        </div>

        {/* Charts — side by side on wide screens (readable on a projector), stacked on mobile */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <DashboardCard
            title="Complaints by Category"
            onRefresh={fetchCategoryDistribution}
            isRefreshing={isLoadingCategories}
          >
            <StateMessage
              loading={isLoadingCategories}
              loadingText="Loading category data..."
              error={categoryError}
              onRetry={fetchCategoryDistribution}
              empty={!isLoadingCategories && !categoryError && categoryData.length === 0}
              emptyText="No complaint data available yet."
            />
            {!isLoadingCategories && !categoryError && categoryData.length > 0 && (
              <div className="w-full" style={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={categoryData} margin={{ top: 10, right: 20, left: 0, bottom: 30 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                      dataKey="category"
                      tick={{ fontSize: 12 }}
                      angle={-20}
                      textAnchor="end"
                      interval={0}
                      label={{ value: "Category", position: "insideBottom", offset: -25, fontSize: 12 }}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 12 }}
                      label={{ value: "Complaint Count", angle: -90, position: "insideLeft", fontSize: 12 }}
                    />
                    <Tooltip />
                    <Bar dataKey="count" fill="#1e293b" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </DashboardCard>

          <DashboardCard
            title="Average Resolution Time by Category"
            subtitle="Resolved complaints only — grouped by category, not a date-based trend."
            onRefresh={fetchResolutionTrends}
            isRefreshing={isLoadingResolution}
          >
            <StateMessage
              loading={isLoadingResolution}
              loadingText="Loading resolution trend data..."
              error={resolutionError}
              onRetry={fetchResolutionTrends}
              empty={!isLoadingResolution && !resolutionError && resolutionData.length === 0}
              emptyText="No resolved complaints yet — nothing to show."
            />
            {!isLoadingResolution && !resolutionError && resolutionData.length > 0 && (
              <div className="w-full" style={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={resolutionData} margin={{ top: 10, right: 20, left: 0, bottom: 30 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                      dataKey="category"
                      tick={{ fontSize: 12 }}
                      angle={-20}
                      textAnchor="end"
                      interval={0}
                      label={{ value: "Category", position: "insideBottom", offset: -25, fontSize: 12 }}
                    />
                    <YAxis
                      tick={{ fontSize: 12 }}
                      label={{ value: "Avg. Days to Resolve", angle: -90, position: "insideLeft", fontSize: 12 }}
                    />
                    <Tooltip formatter={(value) => [`${value} days`, "Avg. Resolution Time"]} />
                    <Line
                      type="monotone"
                      dataKey="avg_resolution_days"
                      stroke="#0f766e"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </DashboardCard>
        </div>

        {/* Priority queue — full width, needs the horizontal room */}
        <DashboardCard
          title="Priority Queue — Underlying Issues"
          onRefresh={fetchQueue}
          isRefreshing={isLoadingQueue}
        >
          <StateMessage
            loading={isLoadingQueue}
            loadingText="Loading priority queue..."
            error={queueError}
            onRetry={fetchQueue}
            empty={!isLoadingQueue && !queueError && queue.length === 0}
            emptyText="No active complaints in the priority queue right now."
          />

          {!isLoadingQueue && !queueError && queue.length > 0 && (
            <div className="overflow-x-auto -mx-6">
              <table className="w-full text-sm">
                <thead className="bg-slate-100 text-slate-600 text-left">
                  <tr>
                    <th className="px-6 py-3 font-medium">#</th>
                    <th className="px-6 py-3 font-medium">Complaint</th>
                    <th className="px-6 py-3 font-medium">Category</th>
                    <th className="px-6 py-3 font-medium">Reports</th>
                    <th className="px-6 py-3 font-medium">Priority</th>
                    <th className="px-6 py-3 font-medium">Status</th>
                    <th className="px-6 py-3 font-medium">Escalation Level</th>
                    <th className="px-6 py-3 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {queue.map((c, index) => (
                    <tr key={c.id}>
                      <td className="px-6 py-3 text-slate-400">{index + 1}</td>
                      <td className="px-6 py-3 text-slate-800">
                        <span className="text-slate-400 mr-1">#{c.id}</span>
                        {c.title}
                      </td>
                      <td className="px-6 py-3 text-slate-600 capitalize">{c.category || "—"}</td>
                      <td className="px-6 py-3 text-slate-600">
                        {c.report_count ?? 1}
                      </td>
                      <td className="px-6 py-3 text-slate-600">
                        {c.priority_score != null ? c.priority_score.toFixed(2) : "—"}
                      </td>
                      <td className="px-6 py-3">
                        <StatusBadge status={c.status} />
                      </td>
                      <td className="px-6 py-3 text-slate-600">{c.escalation_level}</td>
                      <td className="px-6 py-3 text-right">
                        <Link to={`/complaints/${c.id}`} className="text-slate-800 font-medium hover:underline">
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DashboardCard>
      </div>
    </div>
  );
}

export default Management;
