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

function Admin() {
  const [complaints, setComplaints] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [staff, setStaff] = useState([]);
  const [workload, setWorkload] = useState([]);
  const [assigningId, setAssigningId] = useState(null);
  const [assignmentError, setAssignmentError] = useState("");
  const [accountError, setAccountError] = useState("");
  const [accountMessage, setAccountMessage] = useState("");
  const [creatingRole, setCreatingRole] = useState(null);
  const [accountForms, setAccountForms] = useState({
    staff: { name: "", email: "", password: "", department_id: "" },
    management: { name: "", email: "", password: "", department_id: "" },
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [sortByPriority, setSortByPriority] = useState(true);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      // GET /admin/complaints — all complaints, ComplaintOut schema,
      // already ordered by priority_score desc on the backend.
      // GET /admin/departments — [{ id, name, category }, ...]
      const [complaintsRes, departmentsRes, staffRes, workloadRes] = await Promise.all([
        api.get("/admin/complaints"),
        api.get("/admin/departments"),
        api.get("/admin/staff"),
        api.get("/admin/staff-workload"),
      ]);
      setComplaints(complaintsRes.data);
      setDepartments(departmentsRes.data);
      setStaff(staffRes.data);
      setWorkload(workloadRes.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Could not load complaints. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  async function handleAssign(complaintId, staffId) {
    setAssigningId(complaintId);
    setAssignmentError("");
    try {
      const response = await api.patch(`/admin/complaints/${complaintId}/assign`, {
        staff_id: staffId === "" ? null : Number(staffId),
      });
      setComplaints((current) =>
        current.map((complaint) =>
          complaint.id === complaintId ? response.data : complaint
        )
      );
    } catch (err) {
      setAssignmentError(err.response?.data?.detail || "Could not update assignment.");
    } finally {
      setAssigningId(null);
    }
  }

  async function handleCreateAccount(role) {
    const form = accountForms[role];
    setCreatingRole(role);
    setAccountError("");
    setAccountMessage("");
    try {
      const response = await api.post(`/admin/${role}`, {
        name: form.name,
        email: form.email,
        password: form.password,
        ...(role === "staff" && form.department_id
          ? { department_id: Number(form.department_id) }
          : {}),
      });
      setAccountForms((current) => ({
        ...current,
        [role]: { name: "", email: "", password: "", department_id: "" },
      }));
      setAccountMessage(`${response.data.role} account created for ${response.data.email}.`);
      await fetchData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setAccountError(typeof detail === "string" ? detail : "Could not create the account.");
    } finally {
      setCreatingRole(null);
    }
  }

  function updateAccountForm(role, field, value) {
    setAccountForms((current) => ({
      ...current,
      [role]: { ...current[role], [field]: value },
    }));
  }

  useEffect(() => {
    queueMicrotask(() => void fetchData());
  }, [fetchData]);

  const departmentNameById = useMemo(() => {
    const map = {};
    departments.forEach((d) => {
      map[d.id] = d.name;
    });
    return map;
  }, [departments]);

  const visibleComplaints = useMemo(() => {
    let result = complaints.filter((c) => {
      const statusOk = statusFilter === "all" || c.status === statusFilter;
      const priorityOk = priorityFilter === "all" || matchesPriority(c.priority_score, priorityFilter);
      const departmentOk =
        departmentFilter === "all" ||
        (departmentFilter === "unassigned"
          ? c.department_id == null
          : String(c.department_id) === departmentFilter);
      return statusOk && priorityOk && departmentOk;
    });

    if (sortByPriority) {
      result = [...result].sort((a, b) => (b.priority_score ?? -1) - (a.priority_score ?? -1));
    }

    return result;
  }, [complaints, statusFilter, priorityFilter, departmentFilter, sortByPriority]);

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <header className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Admin Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5">All complaints across the system</p>
        </div>
        <Link
          to="/admin/departments"
          className="text-sm rounded-md border border-slate-300 px-3 py-1.5 font-medium text-slate-700 hover:bg-slate-100"
        >
          Manage Departments
        </Link>
      </header>

      <section className="mb-6 rounded-lg bg-white p-4 shadow">
        <h2 className="text-sm font-semibold text-slate-800">Account Management</h2>
        <p className="mt-1 text-xs text-slate-500">
          Only administrators can create Staff or Management accounts. The server assigns the role.
        </p>
        {(accountError || accountMessage) && (
          <p className={`mt-3 text-sm ${accountError ? "text-red-600" : "text-green-600"}`} role="alert">
            {accountError || accountMessage}
          </p>
        )}
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {["staff", "management"].map((role) => {
            const form = accountForms[role];
            return (
              <form
                key={role}
                onSubmit={(event) => {
                  event.preventDefault();
                  void handleCreateAccount(role);
                }}
                className="rounded-md border border-slate-200 p-3"
              >
                <h3 className="text-sm font-medium capitalize text-slate-700">
                  Create {role}
                </h3>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <input
                    required
                    value={form.name}
                    onChange={(event) => updateAccountForm(role, "name", event.target.value)}
                    placeholder="Full name"
                    className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                  />
                  <input
                    required
                    type="email"
                    value={form.email}
                    onChange={(event) => updateAccountForm(role, "email", event.target.value)}
                    placeholder="Email"
                    className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                  />
                  <input
                    required
                    minLength={8}
                    maxLength={72}
                    type="password"
                    value={form.password}
                    onChange={(event) => updateAccountForm(role, "password", event.target.value)}
                    placeholder="Temporary password"
                    className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                  />
                  {role === "staff" && (
                    <select
                      value={form.department_id}
                      onChange={(event) => updateAccountForm(role, "department_id", event.target.value)}
                      className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                    >
                      <option value="">No department</option>
                      {departments.map((department) => (
                        <option key={department.id} value={department.id}>
                          {department.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <button
                  type="submit"
                  disabled={creatingRole === role}
                  className="mt-3 rounded-md bg-slate-800 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-60"
                >
                  {creatingRole === role ? "Creating..." : `Create ${role}`}
                </button>
              </form>
            );
          })}
        </div>
      </section>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 mb-4">
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
        {assignmentError && (
          <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {assignmentError}
          </p>
        )}

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

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Department</label>
          <select
            value={departmentFilter}
            onChange={(e) => setDepartmentFilter(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm bg-white"
          >
            <option value="all">All</option>
            <option value="unassigned">Unassigned</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-600 pb-1.5">
          <input
            type="checkbox"
            checked={sortByPriority}
            onChange={(e) => setSortByPriority(e.target.checked)}
          />
          Sort by priority
        </label>

        <button
          onClick={fetchData}
          disabled={isLoading}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60"
        >
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {isLoading && (
        <div className="bg-white rounded-lg shadow p-6 text-center text-sm text-slate-500">
          Loading complaints...
        </div>
      )}

      {!isLoading && error && (
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={fetchData}
            className="mt-3 rounded-md bg-slate-800 text-white text-sm font-medium px-4 py-2 hover:bg-slate-700"
          >
            Try Again
          </button>
        </div>
      )}

      {!isLoading && !error && complaints.length === 0 && (
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <p className="text-sm text-slate-500">No complaints have been filed yet.</p>
        </div>
      )}

      {!isLoading && !error && (
        <div className="mb-4 rounded-lg bg-white p-4 shadow">
          <h2 className="text-sm font-semibold text-slate-800">Staff Workload</h2>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {[...workload].sort((a, b) => b.open_complaint_count - a.open_complaint_count).map((member) => (
              <div key={member.staff_id} className="rounded-md border border-slate-200 p-3">
                <p className="text-sm font-medium text-slate-800">{member.name}</p>
                <p className="text-xs text-slate-500">{member.department || "No department"}</p>
                <p className="mt-1 text-lg font-semibold text-orange-600">{member.open_complaint_count}</p>
                <p className="text-[11px] text-slate-500">open complaints</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!isLoading && !error && complaints.length > 0 && visibleComplaints.length === 0 && (
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <p className="text-sm text-slate-500">No complaints match the selected filters.</p>
        </div>
      )}

      {!isLoading && !error && visibleComplaints.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-slate-600 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">ID</th>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Priority</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Department</th>
                <th className="px-4 py-3 font-medium">Assigned Staff</th>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {visibleComplaints.map((c) => (
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
                    {c.department_id != null
                      ? departmentNameById[c.department_id] || `Dept #${c.department_id}`
                      : "Unassigned"}
                  </td>
                  <td className="px-4 py-3">
                    <select
                      aria-label={`Assign complaint ${c.id}`}
                      value={c.assigned_to ?? ""}
                      disabled={assigningId === c.id}
                      onChange={(e) => handleAssign(c.id, e.target.value)}
                      className="max-w-48 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700 disabled:opacity-60"
                    >
                      <option value="">Unassigned</option>
                      {[...staff]
                        .sort(
                          (a, b) =>
                            Number(b.department_id === c.department_id) -
                            Number(a.department_id === c.department_id)
                        )
                        .map((member) => (
                          <option key={member.id} value={member.id}>
                            {member.name}
                            {member.department_id === c.department_id ? " (department)" : ""}
                          </option>
                        ))}
                    </select>
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
      )}
    </div>
  );
}

export default Admin;
