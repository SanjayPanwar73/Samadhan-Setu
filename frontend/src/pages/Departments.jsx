import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../services/api";

const emptyForm = { name: "", category: "" };

function Departments() {
  const [departments, setDepartments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  // Add-department form
  const [form, setForm] = useState(emptyForm);
  const [formError, setFormError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");

  // Inline edit state: which department id is being edited, and its draft values
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(emptyForm);
  const [editError, setEditError] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState(null); // department object, or null
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  const fetchDepartments = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      // GET /admin/departments -> [{ id, name, category }, ...]
      const response = await api.get("/admin/departments");
      setDepartments(response.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Could not load departments. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void fetchDepartments());
  }, [fetchDepartments]);

  function getErrorDetail(err, fallback) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) return detail[0].msg || fallback;
    return fallback;
  }

  async function handleCreate(e) {
    e.preventDefault();
    setFormError("");
    setSuccessMessage("");

    if (!form.name.trim() || !form.category.trim()) {
      setFormError("Please fill in both name and category.");
      return;
    }

    setIsSaving(true);
    try {
      // Matches DepartmentCreate exactly: { name, category }.
      await api.post("/admin/departments", { name: form.name.trim(), category: form.category.trim() });
      setForm(emptyForm);
      setSuccessMessage(`Department "${form.name.trim()}" created.`);
      await fetchDepartments();
    } catch (err) {
      setFormError(getErrorDetail(err, "Could not create the department. Please try again."));
    } finally {
      setIsSaving(false);
    }
  }

  function startEdit(dept) {
    setEditingId(dept.id);
    setEditForm({ name: dept.name, category: dept.category });
    setEditError("");
  }

  function cancelEdit() {
    setEditingId(null);
    setEditForm(emptyForm);
    setEditError("");
  }

  async function handleUpdate(e, deptId) {
    e.preventDefault();
    setEditError("");

    if (!editForm.name.trim() || !editForm.category.trim()) {
      setEditError("Name and category can't be empty.");
      return;
    }

    setIsUpdating(true);
    try {
      // Matches DepartmentUpdate: both fields optional, but we send both here.
      await api.put(`/admin/departments/${deptId}`, {
        name: editForm.name.trim(),
        category: editForm.category.trim(),
      });
      setEditingId(null);
      setSuccessMessage("Department updated.");
      await fetchDepartments();
    } catch (err) {
      setEditError(getErrorDetail(err, "Could not update the department. Please try again."));
    } finally {
      setIsUpdating(false);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleteError("");
    setIsDeleting(true);
    try {
      await api.delete(`/admin/departments/${deleteTarget.id}`);
      setSuccessMessage(`Department "${deleteTarget.name}" deleted.`);
      setDeleteTarget(null);
      await fetchDepartments();
    } catch (err) {
      setDeleteError(getErrorDetail(err, "Could not delete the department. Please try again."));
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Department Management</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Departments used to auto-route classified complaints.
          </p>
        </div>
        <Link to="/admin" className="text-sm text-slate-500 hover:underline">
          ← Back to Admin Dashboard
        </Link>
      </header>

      {successMessage && (
        <p className="mb-4 text-sm text-green-700 bg-green-50 border border-green-200 rounded-md px-3 py-2">
          {successMessage}
        </p>
      )}

      {/* Add department form */}
      <div className="bg-white rounded-lg shadow p-6 mb-6 max-w-lg">
        <h2 className="text-sm font-semibold text-slate-800 mb-3">Add Department</h2>
        <form onSubmit={handleCreate} className="space-y-3">
          <div>
            <label htmlFor="deptName" className="block text-xs font-medium text-slate-500 mb-1">
              Name
            </label>
            <input
              id="deptName"
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
            />
          </div>
          <div>
            <label htmlFor="deptCategory" className="block text-xs font-medium text-slate-500 mb-1">
              Category keywords (comma-separated)
            </label>
            <input
              id="deptCategory"
              type="text"
              placeholder="e.g. electricity,power,outage"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
            />
          </div>

          {formError && (
            <p className="text-sm text-red-600" role="alert">
              {formError}
            </p>
          )}

          <button
            type="submit"
            disabled={isSaving}
            className="rounded-md bg-slate-800 text-white text-sm font-medium px-4 py-2 hover:bg-slate-700 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isSaving ? "Adding..." : "Add Department"}
          </button>
        </form>
      </div>

      {/* Departments list */}
      {isLoading && (
        <div className="bg-white rounded-lg shadow p-6 text-center text-sm text-slate-500">
          Loading departments...
        </div>
      )}

      {!isLoading && error && (
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={fetchDepartments}
            className="mt-3 rounded-md bg-slate-800 text-white text-sm font-medium px-4 py-2 hover:bg-slate-700"
          >
            Try Again
          </button>
        </div>
      )}

      {!isLoading && !error && departments.length === 0 && (
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <p className="text-sm text-slate-500">No departments have been created yet.</p>
        </div>
      )}

      {!isLoading && !error && departments.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden max-w-3xl">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-slate-600 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">ID</th>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Category Keywords</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {departments.map((d) => (
                <tr key={d.id}>
                  {editingId === d.id ? (
                    <td colSpan={4} className="px-4 py-3">
                      <form onSubmit={(e) => handleUpdate(e, d.id)} className="flex flex-wrap items-start gap-2">
                        <input
                          type="text"
                          value={editForm.name}
                          onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                          className="rounded-md border border-slate-300 px-2 py-1 text-sm flex-1 min-w-[140px]"
                        />
                        <input
                          type="text"
                          value={editForm.category}
                          onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                          className="rounded-md border border-slate-300 px-2 py-1 text-sm flex-1 min-w-[180px]"
                        />
                        <button
                          type="submit"
                          disabled={isUpdating}
                          className="rounded-md bg-slate-800 text-white text-xs font-medium px-3 py-1.5 hover:bg-slate-700 disabled:opacity-60"
                        >
                          {isUpdating ? "Saving..." : "Save"}
                        </button>
                        <button
                          type="button"
                          onClick={cancelEdit}
                          className="rounded-md border border-slate-300 text-xs font-medium px-3 py-1.5 hover:bg-slate-50"
                        >
                          Cancel
                        </button>
                        {editError && (
                          <p className="w-full text-xs text-red-600 mt-1">{editError}</p>
                        )}
                      </form>
                    </td>
                  ) : (
                    <>
                      <td className="px-4 py-3 text-slate-500">#{d.id}</td>
                      <td className="px-4 py-3 text-slate-800">{d.name}</td>
                      <td className="px-4 py-3 text-slate-600">{d.category}</td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <button
                          onClick={() => startEdit(d)}
                          className="text-slate-700 font-medium hover:underline mr-3"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => {
                            setDeleteError("");
                            setDeleteTarget(d);
                          }}
                          className="text-red-600 font-medium hover:underline"
                        >
                          Delete
                        </button>
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Delete confirmation modal */}
      {deleteTarget && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-sm w-full">
            <h3 className="text-sm font-semibold text-slate-800">Delete department?</h3>
            <p className="text-sm text-slate-600 mt-2">
              Are you sure you want to delete <strong>{deleteTarget.name}</strong>? Any
              complaints currently assigned to it will become unassigned. This can't be undone.
            </p>

            {deleteError && (
              <p className="mt-3 text-sm text-red-600" role="alert">
                {deleteError}
              </p>
            )}

            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setDeleteTarget(null)}
                disabled={isDeleting}
                className="rounded-md border border-slate-300 text-slate-700 text-sm font-medium px-4 py-2 hover:bg-slate-50 disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={isDeleting}
                className="rounded-md bg-red-600 text-white text-sm font-medium px-4 py-2 hover:bg-red-700 disabled:opacity-60"
              >
                {isDeleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Departments;
