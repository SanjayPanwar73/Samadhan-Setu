import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "../services/api";

function formatDate(isoString) {
  if (!isoString) return "—";
  return new Date(isoString).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

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

const STATUS_OPTIONS = ["pending", "in_progress", "reopened", "resolved", "rejected"];
const PRIORITY_OPTIONS = [
  { label: "Critical (90–100)", value: "critical" },
  { label: "High (70–89.99)", value: "high" },
  { label: "Medium (40–69.99)", value: "medium" },
  { label: "Low (0–39.99)", value: "low" },
];

function matchesPriority(score, filterValue) {
  if (score == null) return false;
  if (filterValue === "critical") return score >= 90;
  if (filterValue === "high") return score >= 70 && score < 90;
  if (filterValue === "medium") return score >= 40 && score < 70;
  if (filterValue === "low") return score >= 0 && score < 40;
  return true;
}

function Staff() {
  const [complaints, setComplaints] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");

  const fetchAssigned = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      // GET /complaints/assigned — returns complaints where
      // assigned_to == current staff member's id (ComplaintOut schema).
      const response = await api.get("/complaints/assigned");
      setComplaints(response.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Could not load your assigned complaints. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void fetchAssigned());
  }, [fetchAssigned]);

  const filteredComplaints = useMemo(() => {
    return complaints.filter((c) => {
      const statusOk = statusFilter === "all" || c.status === statusFilter;
      const priorityOk = priorityFilter === "all" || matchesPriority(c.priority_score, priorityFilter);
      return statusOk && priorityOk;
    });
  }, [complaints, statusFilter, priorityFilter]);

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-slate-800">Staff Dashboard</h1>
        <p className="text-sm text-slate-500 mt-0.5">Complaints assigned to you</p>
      </header>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm bg-white"
          >
            <option value="all">All</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s.replace("_", " ")}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Priority</label>
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm bg-white"
          >
            <option value="all">All</option>
            {PRIORITY_OPTIONS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={fetchAssigned}
          disabled={isLoading}
          className="mt-5 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60"
        >
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {isLoading && (
        <div className="bg-white rounded-lg shadow p-6 text-center text-sm text-slate-500">
          Loading assigned complaints...
        </div>
      )}

      {!isLoading && error && (
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={fetchAssigned}
            className="mt-3 rounded-md bg-slate-800 text-white text-sm font-medium px-4 py-2 hover:bg-slate-700"
          >
            Try Again
          </button>
        </div>
      )}

      {!isLoading && !error && complaints.length === 0 && (
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <p className="text-sm text-slate-500">No complaints are assigned to you yet.</p>
        </div>
      )}

      {!isLoading && !error && complaints.length > 0 && filteredComplaints.length === 0 && (
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <p className="text-sm text-slate-500">No complaints match the selected filters.</p>
        </div>
      )}

      {!isLoading && !error && filteredComplaints.length > 0 && (
        <>
          {/* Table on medium+ screens */}
          <div className="hidden md:block bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-100 text-slate-600 text-left">
                <tr>
                  <th className="px-4 py-3 font-medium">ID</th>
                  <th className="px-4 py-3 font-medium">Title</th>
                  <th className="px-4 py-3 font-medium">Priority</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Department</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredComplaints.map((c) => (
                  <tr key={c.id}>
                    <td className="px-4 py-3 text-slate-500">#{c.id}</td>
                    <td className="px-4 py-3 text-slate-800">{c.title}</td>
                    <td className="px-4 py-3 text-slate-600">
                      {c.priority_score != null ? c.priority_score.toFixed(2) : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {c.department_id != null ? `Dept #${c.department_id}` : "—"}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatDate(c.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to={`/complaints/${c.id}`}
                        className="text-slate-800 font-medium hover:underline"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Cards on small screens */}
          <div className="md:hidden space-y-3">
            {filteredComplaints.map((c) => (
              <div key={c.id} className="bg-white rounded-lg shadow p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs text-slate-400">#{c.id}</p>
                    <h2 className="text-sm font-medium text-slate-800">{c.title}</h2>
                  </div>
                  <StatusBadge status={c.status} />
                </div>

                <dl className="mt-3 grid grid-cols-2 gap-y-1 text-xs text-slate-500">
                  <dt>Priority</dt>
                  <dd className="text-right">
                    {c.priority_score != null ? c.priority_score.toFixed(2) : "—"}
                  </dd>
                  <dt>Department</dt>
                  <dd className="text-right">
                    {c.department_id != null ? `Dept #${c.department_id}` : "—"}
                  </dd>
                  <dt>Created</dt>
                  <dd className="text-right">{formatDate(c.created_at)}</dd>
                </dl>

                <Link
                  to={`/complaints/${c.id}`}
                  className="mt-3 block text-center rounded-md border border-slate-300 text-slate-700 text-sm font-medium py-1.5 hover:bg-slate-50"
                >
                  View
                </Link>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default Staff;
