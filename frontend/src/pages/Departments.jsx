import { useState } from "react";
import api, { getApiError } from "../services/api";
import useResource from "../hooks/useResource";
import Icon from "../components/Icon";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Modal,
  PageHeader,
  TableSkeleton,
} from "../components/ui";

export default function Departments() {
  const resource = useResource("/admin/departments", { collection: true });
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", category: "" });
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const visible = (resource.data || []).filter((item) =>
    `${item.name} ${item.category}`
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );
  function openEditor(department = { id: null, name: "", category: "" }) {
    setEditing(department);
    setForm({ name: department.name, category: department.category });
    setError("");
  }
  async function save(event) {
    event.preventDefault();
    if (busy) return;
    setError("");
    if (!form.name.trim() || !form.category.trim()) {
      setError("Enter both a department name and category keywords.");
      return;
    }
    setBusy(true);
    try {
      const payload = {
        name: form.name.trim(),
        category: form.category.trim(),
      };
      if (editing.id)
        await api.put(`/admin/departments/${editing.id}`, payload);
      else await api.post("/admin/departments", payload);
      setSuccess(
        `${payload.name} ${editing.id ? "updated" : "created"} successfully.`,
      );
      setEditing(null);
      await resource.refresh();
    } catch (requestError) {
      setError(
        getApiError(
          requestError,
          "We couldn’t save the department. Please try again.",
        ),
      );
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (busy || !deleteTarget) return;
    setBusy(true);
    setError("");
    try {
      await api.delete(`/admin/departments/${deleteTarget.id}`);
      setSuccess(`${deleteTarget.name} has been deleted.`);
      setDeleteTarget(null);
      await resource.refresh();
    } catch (requestError) {
      setError(
        getApiError(requestError, "We couldn’t delete this department."),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Connect concerns with teams"
        title="Departments"
        description="Organize your teams and the categories used to route complaints."
        actions={
          <Button onClick={() => openEditor()}>
            <Icon name="plus" size={16} />
            Add department
          </Button>
        }
      />
      {success && <Alert variant="success">{success}</Alert>}
      <Card>
        <div className="panel-heading">
          <div className="flex items-center gap-3">
            <h2>Department directory</h2>
            {resource.data && <Badge>{resource.data.length}</Badge>}
          </div>
          <Button
            variant="ghost"
            className="icon-button"
            aria-label="Refresh departments"
            disabled={resource.loading}
            onClick={resource.refresh}
          >
            <Icon name="refresh" size={16} />
          </Button>
        </div>
        <div className="toolbar">
          <div className="search-field">
            <Icon name="search" size={16} />
            <input
              className="input"
              type="search"
              aria-label="Search departments"
              placeholder="Search names or keywords…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <span className="text-xs text-slate-500">
            {visible.length} departments
          </span>
        </div>
        {resource.loading ? (
          <TableSkeleton />
        ) : resource.error ? (
          <ErrorState message={resource.error} onRetry={resource.refresh} />
        ) : !visible.length ? (
          <EmptyState
            icon={query ? "search" : "building"}
            title={
              query
                ? "No departments match"
                : "Give every concern a destination"
            }
            description={
              query
                ? "Try another name or keyword."
                : "Add your first department and the category keywords it handles."
            }
            action={
              query ? (
                <Button variant="secondary" onClick={() => setQuery("")}>
                  Clear search
                </Button>
              ) : (
                <Button onClick={() => openEditor()}>
                  <Icon name="plus" size={16} />
                  Add department
                </Button>
              )
            }
          />
        ) : (
          <div className="grid gap-4 border-t border-slate-100 p-4 sm:grid-cols-2 sm:p-6 xl:grid-cols-3">
            {visible.map((item) => (
              <article
                key={item.id}
                className="flex flex-col rounded-xl border border-slate-200 p-5 transition-shadow hover:shadow-sm"
              >
                <div className="flex items-start justify-between">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600">
                    <Icon name="building" size={21} />
                  </span>
                  <Badge>#{item.id}</Badge>
                </div>
                <h3 className="mt-4 break-words text-sm font-semibold text-slate-700">
                  {item.name}
                </h3>
                <p className="mt-3 text-[10px] font-medium uppercase tracking-wider text-slate-500">
                  Routing keywords
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {item.category
                    .split(",")
                    .map((value) => value.trim())
                    .filter(Boolean)
                    .map((value, index) => (
                      <span
                        key={`${value}-${index}`}
                        className="max-w-full break-words rounded-md bg-slate-50 px-2 py-1 text-[11px] text-slate-600"
                      >
                        {value}
                      </span>
                    ))}
                </div>
                <div className="mt-auto flex gap-2 pt-5">
                  <Button
                    variant="secondary"
                    className="flex-1 !min-h-9 !px-2 !text-xs"
                    onClick={() => openEditor(item)}
                  >
                    <Icon name="edit" size={14} />
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    className="icon-button !min-h-9 text-red-600"
                    aria-label={`Delete ${item.name}`}
                    onClick={() => {
                      setDeleteTarget(item);
                      setError("");
                    }}
                  >
                    <Icon name="trash" size={16} />
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>
      <Modal
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        busy={busy}
        title={editing?.id ? "Edit department" : "Add a department"}
        description="Use clear names and category keywords to help complaints reach the right team."
        footer={
          <>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => setEditing(null)}
            >
              Cancel
            </Button>
            <Button type="submit" form="department-form" loading={busy}>
              {editing?.id ? "Save changes" : "Create department"}
            </Button>
          </>
        }
      >
        <form id="department-form" onSubmit={save} className="space-y-5">
          <Field label="Department name" htmlFor="department-name">
            <input
              id="department-name"
              className="input"
              required
              maxLength={120}
              placeholder="e.g. Facilities & maintenance"
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({ ...current, name: event.target.value }))
              }
              disabled={busy}
            />
          </Field>
          <Field
            label="Category keywords"
            htmlFor="department-category"
            hint="Separate keywords with commas, such as electricity, power, lighting."
          >
            <textarea
              id="department-category"
              className="input"
              required
              maxLength={500}
              rows={3}
              placeholder="electricity, power, lighting"
              value={form.category}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  category: event.target.value,
                }))
              }
              aria-describedby="department-category-hint"
              disabled={busy}
            />
          </Field>
          {error && <Alert variant="error">{error}</Alert>}
        </form>
      </Modal>
      <Modal
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        busy={busy}
        title="Delete this department?"
        description="This action cannot be undone."
        footer={
          <>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => setDeleteTarget(null)}
            >
              Keep department
            </Button>
            <Button variant="danger" loading={busy} onClick={remove}>
              Delete department
            </Button>
          </>
        }
      >
        <p className="text-sm leading-7 text-slate-600">
          <strong>{deleteTarget?.name}</strong> will be deleted. Complaints
          currently routed to this department will have no department assigned.
        </p>
        {error && (
          <div className="mt-4">
            <Alert variant="error">{error}</Alert>
          </div>
        )}
      </Modal>
    </div>
  );
}
