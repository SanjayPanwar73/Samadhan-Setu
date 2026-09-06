import { useCallback, useEffect, useState } from "react";
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

// Small color cue for status, purely visual — the text itself is
// still the source of truth.
const statusStyles = {
  pending: "bg-yellow-100 text-yellow-800",
  in_progress: "bg-blue-100 text-blue-800",
  resolved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

function StatusBadge({ status }) {
  const classes = statusStyles[status] || "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${classes}`}>
      {status ? status.replace("_", " ") : "—"}
    </span>
  );
}

function Complaints() {
  const [complaints, setComplaints] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchComplaints = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      // Response items match the backend's ComplaintOut schema exactly:
      // id, title, description, category, priority_score, sentiment_label,
      // status, department_id, created_by, assigned_to, escalation_level,
      // sla_deadline, created_at.
      const response = await api.get("/complaints/me");
      setComplaints(response.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Could not load your complaints. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchComplaints();
  }, [fetchComplaints]);

  return (
    <div>
      <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-medium text-brand-600">Your activity</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">My Complaints</h1>
          <p className="mt-1 text-sm text-slate-500">Track every issue from submission to resolution.</p>
        </div>
        <Link to="/complaints/new" className="inline-flex items-center justify-center rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:-translate-y-0.5 hover:bg-brand-700">
          + Submit New Complaint
        </Link>
      </div>
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["Total", complaints.length, "bg-brand-50 text-brand-700"],
          ["Pending", complaints.filter((c) => c.status === "pending").length, "bg-amber-50 text-amber-700"],
          ["In progress", complaints.filter((c) => c.status === "in_progress").length, "bg-sky-50 text-sky-700"],
          ["Resolved", complaints.filter((c) => c.status === "resolved").length, "bg-emerald-50 text-emerald-700"],
        ].map(([label, value, classes]) => (
          <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className={`mb-3 inline-flex rounded-lg px-2 py-1 text-xs font-semibold ${classes}`}>{label}</div>
            <p className="text-2xl font-bold text-slate-900">{isLoading ? "—" : value}</p>
          </div>
        ))}
      </div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">Recent complaints</h2>
        <button
          onClick={fetchComplaints}
          disabled={isLoading}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-600 shadow-sm hover:bg-slate-50 disabled:opacity-60"
        >
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {isLoading && (
        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500 shadow-sm">
          Loading your complaints...
        </div>
      )}

      {!isLoading && error && (
        <div className="rounded-2xl border border-red-100 bg-red-50 p-8 text-center">
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={fetchComplaints}
            className="mt-3 rounded-md bg-slate-800 text-white text-sm font-medium px-4 py-2 hover:bg-slate-700"
          >
            Try Again
          </button>
        </div>
      )}

      {!isLoading && !error && complaints.length === 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm">
          <p className="text-sm text-slate-500">
            You haven't filed any complaints yet.
          </p>
          <Link
            to="/complaints/new"
            className="mt-3 inline-block rounded-md bg-slate-800 text-white text-sm font-medium px-4 py-2 hover:bg-slate-700"
          >
            File a Complaint
          </Link>
        </div>
      )}

      {!isLoading && !error && complaints.length > 0 && (
        <>
          {/* Table layout on medium+ screens */}
          <div className="hidden overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm md:block">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">ID</th>
                  <th className="px-4 py-3 font-medium">Title</th>
                  <th className="px-4 py-3 font-medium">Category</th>
                  <th className="px-4 py-3 font-medium">Priority</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {complaints.map((c) => (
                  <tr key={c.id}>
                    <td className="px-4 py-3 text-slate-500">#{c.id}</td>
                    <td className="px-4 py-3 text-slate-800">{c.title}</td>
                    <td className="px-4 py-3 text-slate-600 capitalize">
                      {c.category || "—"}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {c.priority_score != null ? c.priority_score.toFixed(2) : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={c.status} />
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

          {/* Card layout on small screens */}
          <div className="space-y-3 md:hidden">
            {complaints.map((c) => (
              <div key={c.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs text-slate-400">#{c.id}</p>
                    <h2 className="text-sm font-medium text-slate-800">{c.title}</h2>
                  </div>
                  <StatusBadge status={c.status} />
                </div>

                <dl className="mt-3 grid grid-cols-2 gap-y-1 text-xs text-slate-500">
                  <dt>Category</dt>
                  <dd className="text-right capitalize">{c.category || "—"}</dd>
                  <dt>Priority</dt>
                  <dd className="text-right">
                    {c.priority_score != null ? c.priority_score.toFixed(2) : "—"}
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

export default Complaints;
