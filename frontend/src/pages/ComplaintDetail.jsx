import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api from "../services/api";
import { getRole, getHomeRouteForRole } from "../utils/auth";

function formatDateTime(isoString) {
  if (!isoString) return "—";
  return new Date(isoString).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const statusStyles = {
  pending: "bg-yellow-100 text-yellow-800",
  in_progress: "bg-blue-100 text-blue-800",
  resolved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
};

function StatusBadge({ status }) {
  const classes = statusStyles[status] || "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium capitalize ${classes}`}>
      {status ? status.replace("_", " ") : "—"}
    </span>
  );
}

const sentimentStyles = {
  POSITIVE: "bg-green-100 text-green-800",
  NEGATIVE: "bg-red-100 text-red-800",
};

// Small tag distinguishing an AI-set value from one an admin has
// manually overridden — the visible half of the transparency requirement.
function SourceTag({ overridden }) {
  return overridden ? (
    <span className="inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-amber-100 text-amber-800 ml-2">
      Overridden
    </span>
  ) : (
    <span className="inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-indigo-100 text-indigo-700 ml-2">
      AI
    </span>
  );
}

// Mirrors VALID_TRANSITIONS in app/routers/complaints.py exactly.
// Kept here (not fetched) since the backend doesn't expose this as
// data — it's enforced server-side regardless of what's shown here;
// this only decides which buttons make sense to offer.
const VALID_TRANSITIONS = {
  pending: ["in_progress", "rejected"],
  in_progress: ["resolved", "rejected"],
  resolved: [],
  rejected: [],
};

const STATUS_ACTION_LABELS = {
  in_progress: "Mark In Progress",
  resolved: "Mark Resolved",
  rejected: "Reject",
};

function ComplaintDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const role = getRole();
  const canUpdateStatus = role === "staff" || role === "admin";
  const isAdmin = role === "admin";

  // Where "back" should go depends on who's viewing — the owner's
  // own list, or a staff/admin's own dashboard.
  const backHref = getHomeRouteForRole(role);

  const [complaint, setComplaint] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const [updatingStatus, setUpdatingStatus] = useState(null); // which status is being submitted, or null
  const [updateError, setUpdateError] = useState("");
  const [updateSuccess, setUpdateSuccess] = useState("");

  // Admin override panel state
  const [departments, setDepartments] = useState([]);
  const [overrideDepartmentId, setOverrideDepartmentId] = useState("");
  const [overridePriorityScore, setOverridePriorityScore] = useState("");
  const [isOverriding, setIsOverriding] = useState(false);
  const [overrideError, setOverrideError] = useState("");
  const [overrideSuccess, setOverrideSuccess] = useState("");
  const [pendingOverride, setPendingOverride] = useState(null); // { department_id?, priority_score?, summary[] } | null

  // Validate the :id param itself before ever calling the API —
  // covers someone typing /complaints/abc directly in the URL.
  const isValidId = /^\d+$/.test(id);

  const fetchComplaint = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      // Matches the backend's ComplaintOut schema exactly. Note: the
      // backend does not return updated_at, sentiment_score, or any
      // similar-issue data on this endpoint, so those are not shown.
      const response = await api.get(`/complaints/${id}`);
      setComplaint(response.data);
    } catch (err) {
      const status = err.response?.status;
      if (status === 404) {
        setError("This complaint doesn't exist.");
      } else if (status === 403) {
        setError("You're not authorized to view this complaint.");
      } else {
        const detail = err.response?.data?.detail;
        setError(typeof detail === "string" ? detail : "Could not load this complaint. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (isValidId) {
      fetchComplaint();
    }
  }, [isValidId, fetchComplaint]);

  // Admin-only: load departments for the override dropdown.
  useEffect(() => {
    if (!isAdmin) return;
    api
      .get("/admin/departments")
      .then((res) => setDepartments(res.data))
      .catch(() => {
        // Non-fatal — the override form just won't have department names/options.
      });
  }, [isAdmin]);

  // Pre-fill the override form with the complaint's current values once loaded.
  useEffect(() => {
    if (!complaint) return;
    setOverrideDepartmentId(complaint.department_id != null ? String(complaint.department_id) : "");
    setOverridePriorityScore(complaint.priority_score != null ? String(complaint.priority_score) : "");
  }, [complaint]);

  async function handleStatusUpdate(newStatus) {
    setUpdateError("");
    setUpdateSuccess("");
    setUpdatingStatus(newStatus);

    try {
      // Matches ComplaintStatusUpdate exactly: { status }. No remarks
      // field exists on this endpoint's schema, so none is sent.
      await api.patch(`/complaints/${id}/status`, { status: newStatus });
      setUpdateSuccess(`Status updated to "${newStatus.replace("_", " ")}".`);
      // Refresh so the page reflects the backend's actual current state
      // (and the new set of valid next transitions) rather than assuming.
      await fetchComplaint();
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 400 && typeof detail === "string") {
        // e.g. "Invalid status transition: pending -> resolved"
        setUpdateError(detail);
      } else if (status === 403) {
        setUpdateError("You're not authorized to update this complaint's status.");
      } else if (typeof detail === "string") {
        setUpdateError(detail);
      } else {
        setUpdateError("Could not update the status. Please try again.");
      }
    } finally {
      setUpdatingStatus(null);
    }
  }

  function handleOverrideFormSubmit(e) {
    e.preventDefault();
    setOverrideError("");
    setOverrideSuccess("");

    const currentDeptId = complaint.department_id != null ? String(complaint.department_id) : "";
    const departmentChanged = overrideDepartmentId !== currentDeptId;

    const parsedPriority = overridePriorityScore === "" ? null : Number(overridePriorityScore);
    const priorityChanged =
      parsedPriority !== null &&
      (complaint.priority_score == null || Math.abs(parsedPriority - complaint.priority_score) > 0.001);

    if (!departmentChanged && !priorityChanged) {
      setOverrideError("Change the department or priority score before saving.");
      return;
    }

    if (parsedPriority !== null && (parsedPriority < 0 || parsedPriority > 100)) {
      setOverrideError("Priority score must be between 0 and 100.");
      return;
    }

    const payload = {};
    const summary = [];

    if (departmentChanged) {
      payload.department_id = overrideDepartmentId === "" ? null : Number(overrideDepartmentId);
      const oldName =
        complaint.department_id != null
          ? departments.find((d) => d.id === complaint.department_id)?.name || `#${complaint.department_id}`
          : "Unassigned";
      const newName =
        payload.department_id != null
          ? departments.find((d) => d.id === payload.department_id)?.name || `#${payload.department_id}`
          : "Unassigned";
      summary.push(`Department: ${oldName} → ${newName}`);
    }

    if (priorityChanged) {
      payload.priority_score = parsedPriority;
      const oldScore = complaint.priority_score != null ? complaint.priority_score.toFixed(2) : "unscored";
      summary.push(`Priority: ${oldScore} → ${parsedPriority.toFixed(2)}`);
    }

    // Backend genuinely requires department_id to be a real department's
    // id (it 404s on an unknown one) — it doesn't support clearing a
    // department back to "unassigned" via this endpoint. Block that
    // client-side with a clear message rather than letting it 404.
    if (departmentChanged && payload.department_id == null) {
      setOverrideError("The backend doesn't support clearing a department back to unassigned via override — pick a real department instead.");
      return;
    }

    setPendingOverride({ payload, summary });
  }

  async function confirmOverride() {
    if (!pendingOverride) return;
    setIsOverriding(true);
    setOverrideError("");
    try {
      // Matches ComplaintOverride exactly: { department_id?, priority_score? }.
      await api.patch(`/complaints/${id}/override`, pendingOverride.payload);
      setOverrideSuccess("Override saved.");
      setPendingOverride(null);
      await fetchComplaint();
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 404 && typeof detail === "string") {
        setOverrideError(detail);
      } else if (status === 400 && typeof detail === "string") {
        setOverrideError(detail);
      } else if (status === 403) {
        setOverrideError("You're not authorized to override this complaint.");
      } else {
        setOverrideError("Could not save the override. Please try again.");
      }
    } finally {
      setIsOverriding(false);
    }
  }


  if (!isValidId) {
    return (
      <div className="bg-white rounded-lg shadow p-6 text-center">
        <p className="text-sm text-red-600">
          "{id}" isn't a valid complaint ID.
        </p>
        <button
          onClick={() => navigate(backHref)}
          className="mt-3 rounded-md bg-slate-800 text-white text-sm font-medium px-4 py-2 hover:bg-slate-700"
        >
          Back
        </button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-6 text-center text-sm text-slate-500">
        Loading complaint #{id}...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6 text-center">
        <p className="text-sm text-red-600">{error}</p>
        <div className="mt-3 flex justify-center gap-3">
          <button
            onClick={fetchComplaint}
            className="rounded-md bg-slate-800 text-white text-sm font-medium px-4 py-2 hover:bg-slate-700"
          >
            Try Again
          </button>
          <button
            onClick={() => navigate(backHref)}
            className="rounded-md border border-slate-300 text-slate-700 text-sm font-medium px-4 py-2 hover:bg-slate-50"
          >
            Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <button
        onClick={() => navigate(backHref)}
        className="text-sm text-slate-500 hover:underline"
      >
        ← Back
      </button>

      {/* Core complaint information, as entered/tracked by the system */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs text-slate-400">Complaint #{complaint.id}</p>
            <h1 className="text-xl font-semibold text-slate-800 mt-0.5">
              {complaint.title}
            </h1>
          </div>
          <StatusBadge status={complaint.status} />
        </div>

        <p className="mt-4 text-sm text-slate-600 whitespace-pre-wrap">
          {complaint.description}
        </p>

        <dl className="mt-4 grid grid-cols-2 gap-y-2 text-sm border-t border-slate-100 pt-4">
          <dt className="text-slate-500">Created</dt>
          <dd className="text-right text-slate-700">{formatDateTime(complaint.created_at)}</dd>
        </dl>
      </div>

      {/* AI-derived information, visually separated for transparency */}
      <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-6">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-lg">🤖</span>
          <h2 className="text-sm font-semibold text-indigo-900">
            AI-Derived Insights
          </h2>
        </div>
        <p className="text-xs text-indigo-700/80 -mt-3 mb-4">
          Automatically generated by SmartResolve's classification, sentiment,
          and priority-scoring pipeline when this complaint was submitted.
        </p>

        <dl className="grid grid-cols-2 gap-y-3 text-sm">
          <dt className="text-indigo-900/70">Category</dt>
          <dd className="text-right text-indigo-950 capitalize font-medium">
            {complaint.category || "Not yet classified"}
          </dd>

          <dt className="text-indigo-900/70">Priority Score</dt>
          <dd className="text-right text-indigo-950 font-medium">
            {complaint.priority_score != null
              ? complaint.priority_score.toFixed(2)
              : "Not yet scored"}
            <SourceTag overridden={complaint.priority_overridden} />
          </dd>

          <dt className="text-indigo-900/70">Sentiment</dt>
          <dd className="text-right">
            {complaint.sentiment_label ? (
              <span
                className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                  sentimentStyles[complaint.sentiment_label] || "bg-slate-100 text-slate-700"
                }`}
              >
                {complaint.sentiment_label.toLowerCase()}
              </span>
            ) : (
              <span className="text-indigo-950/60">Not yet analyzed</span>
            )}
          </dd>

          <dt className="text-indigo-900/70">Department</dt>
          <dd className="text-right text-indigo-950 font-medium">
            {complaint.department_id != null
              ? departments.find((d) => d.id === complaint.department_id)?.name ||
                `Department #${complaint.department_id}`
              : "Not yet assigned"}
            <SourceTag overridden={complaint.department_overridden} />
          </dd>

          <dt className="text-indigo-900/70">Escalation Level</dt>
          <dd className="text-right text-indigo-950 font-medium">
            {complaint.escalation_level}
          </dd>
        </dl>

        {/*
          Note: the backend's GET /complaints/{id} response does not
          currently include similar-issue matches (repeat_count is
          computed internally at submission time but isn't exposed
          on this endpoint), so that section isn't rendered here.
        */}
      </div>

      {/*
        Staff/admin action panel. The backend is the real authority here
        (require_role("staff","admin") on the PATCH endpoint) — this check
        just avoids showing controls to someone who'd get a 403 anyway.
      */}
      {canUpdateStatus && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-sm font-semibold text-slate-800 mb-1">
            Update Status
          </h2>
          <p className="text-xs text-slate-500 mb-4">
            Current status: <span className="font-medium capitalize">{complaint.status.replace("_", " ")}</span>
          </p>

          {(VALID_TRANSITIONS[complaint.status] || []).length === 0 ? (
            <p className="text-sm text-slate-500">
              This complaint is in a final state — no further transitions are allowed.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {VALID_TRANSITIONS[complaint.status].map((nextStatus) => (
                <button
                  key={nextStatus}
                  onClick={() => handleStatusUpdate(nextStatus)}
                  disabled={updatingStatus !== null}
                  className="rounded-md bg-slate-800 text-white text-sm font-medium px-4 py-2 hover:bg-slate-700 disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {updatingStatus === nextStatus
                    ? "Updating..."
                    : STATUS_ACTION_LABELS[nextStatus] || nextStatus}
                </button>
              ))}
            </div>
          )}

          {updateSuccess && (
            <p className="mt-3 text-sm text-green-700 bg-green-50 border border-green-200 rounded-md px-3 py-2">
              {updateSuccess}
            </p>
          )}
          {updateError && (
            <p className="mt-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2" role="alert">
              {updateError}
            </p>
          )}
        </div>
      )}

      {/*
        Admin-only manual override of AI-derived department/priority.
        Backend enforces require_role("admin") on PATCH /complaints/{id}/override —
        this check just avoids showing controls to someone who'd get a 403.
      */}
      {isAdmin && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-6">
          <h2 className="text-sm font-semibold text-amber-900 mb-1">
            Admin Override
          </h2>
          <p className="text-xs text-amber-800/80 mb-4">
            Manually correct the AI-derived department or priority score. Overridden
            values are labeled above and will no longer be treated as AI-generated.
          </p>

          <form onSubmit={handleOverrideFormSubmit} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-amber-900 mb-1">
                Department
              </label>
              <select
                value={overrideDepartmentId}
                onChange={(e) => setOverrideDepartmentId(e.target.value)}
                className="w-full max-w-xs rounded-md border border-amber-300 px-3 py-2 text-sm bg-white"
              >
                <option value="">Unassigned</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-amber-900 mb-1">
                Priority Score (0.00 – 100.00)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={overridePriorityScore}
                onChange={(e) => setOverridePriorityScore(e.target.value)}
                className="w-32 rounded-md border border-amber-300 px-3 py-2 text-sm bg-white"
              />
            </div>

            {overrideError && (
              <p className="text-sm text-red-600" role="alert">
                {overrideError}
              </p>
            )}
            {overrideSuccess && (
              <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-md px-3 py-2">
                {overrideSuccess}
              </p>
            )}

            <button
              type="submit"
              className="rounded-md bg-amber-700 text-white text-sm font-medium px-4 py-2 hover:bg-amber-800"
            >
              Review Override
            </button>
          </form>
        </div>
      )}

      {/* Confirmation before saving an important change, per requirement */}
      {pendingOverride && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-sm w-full">
            <h3 className="text-sm font-semibold text-slate-800">Confirm override</h3>
            <ul className="mt-3 text-sm text-slate-600 list-disc list-inside space-y-1">
              {pendingOverride.summary.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-slate-500">
              This will replace the AI-generated value and be recorded as an admin override.
            </p>

            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setPendingOverride(null)}
                disabled={isOverriding}
                className="rounded-md border border-slate-300 text-slate-700 text-sm font-medium px-4 py-2 hover:bg-slate-50 disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                onClick={confirmOverride}
                disabled={isOverriding}
                className="rounded-md bg-amber-700 text-white text-sm font-medium px-4 py-2 hover:bg-amber-800 disabled:opacity-60"
              >
                {isOverriding ? "Saving..." : "Confirm Override"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ComplaintDetail;
