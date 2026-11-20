import { useState } from "react";
import api from "../services/api";
import useAction from "../hooks/useAction";
import useResource from "../hooks/useResource";
import { Alert, Badge, Button, Card, ErrorState, Field, Modal, PageHeader, TableSkeleton } from "../components/ui";
import { ROLE_LABELS } from "../utils/auth";

const ROLES = ["student", "staff", "dept_admin", "hod", "super_admin"];
const SINGLE = ["staff", "dept_admin"];
const NONE = ["student", "super_admin"];

/** Mirrors the backend rule: staff/dept_admin exactly one department, hod at least one, others none. */
export function membershipProblem(role, ids) {
  if (SINGLE.includes(role) && ids.length !== 1) return "Choose exactly one department.";
  if (role === "hod" && ids.length < 1) return "Choose at least one department.";
  if (NONE.includes(role) && ids.length) return "This role has no department.";
  return "";
}

function DepartmentChecks({ departments, value, onChange }) {
  return (
    <div className="flex flex-wrap gap-3" role="group" aria-label="Departments">
      {departments.map((d) => (
        <label key={d.id} className="flex items-center gap-1.5 text-sm">
          <input type="checkbox" checked={value.includes(d.id)} onChange={() => onChange(value.includes(d.id) ? value.filter((x) => x !== d.id) : [...value, d.id])} />
          {d.name}
        </label>
      ))}
    </div>
  );
}

export default function SuperUsers() {
  const users = useResource("/admin/org/users?limit=100");
  const departments = useResource("/admin/org/departments");
  const depts = (departments.data || []).filter((d) => d.is_active && !d.is_system);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "staff", enrollment_no: "", department_ids: [] });
  const [edit, setEdit] = useState(null); // { user, role, ids, reason }
  const { busy, message, run } = useAction();
  const problem = membershipProblem(form.role, form.department_ids);

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Administration" title="Users and roles" description="Every role or membership change is audited." />
      {message && <Alert variant={message.variant}>{message.text}</Alert>}
      <Card className="p-6">
        <h2 className="mb-3 text-lg font-semibold text-slate-800">Add a user</h2>
        <form className="grid gap-4 sm:grid-cols-2" onSubmit={async (e) => {
          e.preventDefault();
          if (problem) return;
          const body = { ...form, enrollment_no: form.enrollment_no || null };
          if (await run("create", () => api.post("/admin/org/users", body), "User created.")) {
            setForm({ name: "", email: "", password: "", role: "staff", enrollment_no: "", department_ids: [] });
            users.refresh();
          }
        }}>
          <Field label="Name" htmlFor="u-name"><input id="u-name" className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Email" htmlFor="u-email"><input id="u-email" type="email" className="input" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Temporary password" htmlFor="u-pass" hint="At least 8 characters."><input id="u-pass" type="password" minLength={8} className="input" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
          <Field label="Role" htmlFor="u-role">
            <select id="u-role" className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value, department_ids: [] })}>
              {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </select>
          </Field>
          {form.role === "student" && <Field label="Enrollment number" htmlFor="u-enr"><input id="u-enr" className="input" required value={form.enrollment_no} onChange={(e) => setForm({ ...form, enrollment_no: e.target.value })} /></Field>}
          {!NONE.includes(form.role) && (
            <Field label="Department" htmlFor="u-dept" error={form.department_ids.length ? problem : ""}>
              <DepartmentChecks departments={depts} value={form.department_ids} onChange={(ids) => setForm({ ...form, department_ids: ids })} />
            </Field>
          )}
          <div className="sm:col-span-2"><Button type="submit" loading={busy === "create"} disabled={Boolean(problem)}>Create user</Button></div>
        </form>
      </Card>

      <Card>
        {users.loading ? <TableSkeleton /> : users.error ? <ErrorState message={users.error} onRetry={users.refresh} /> : (
          <div className="table-wrap">
            <table className="data-table">
              <caption className="sr-only">All users</caption>
              <thead><tr><th scope="col">Name</th><th scope="col">Role</th><th scope="col">Departments</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {users.data.map((u) => (
                  <tr key={u.id}>
                    <td><p className="font-medium text-slate-800">{u.name}</p><p className="text-xs text-slate-500">{u.email}</p></td>
                    <td>{ROLE_LABELS[u.role] || u.role}</td>
                    <td className="text-xs">{u.department_ids.map((id) => (departments.data || []).find((d) => d.id === id)?.name || `#${id}`).join(", ") || "—"}</td>
                    <td>{u.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Inactive</Badge>}</td>
                    <td className="space-x-2 whitespace-nowrap">
                      <Button variant="secondary" onClick={() => setEdit({ user: u, role: u.role, ids: u.department_ids, reason: "" })}>Edit access</Button>
                      <Button variant="ghost" loading={busy === `a${u.id}`} onClick={async () => (await run(`a${u.id}`, () => api.patch(`/admin/org/users/${u.id}`, { is_active: !u.is_active }), u.is_active ? "User deactivated." : "User activated.")) && users.refresh()}>{u.is_active ? "Deactivate" : "Activate"}</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal open={Boolean(edit)} onClose={() => setEdit(null)} title={edit ? `Edit access · ${edit.user.name}` : ""} description="Changing a role or departments requires a reason and is recorded in the audit log."
        footer={edit && (
          <>
            <Button variant="secondary" onClick={() => setEdit(null)}>Cancel</Button>
            <Button loading={busy === "edit"} disabled={edit.reason.trim().length < 5 || Boolean(membershipProblem(edit.role, edit.ids))}
              onClick={async () => {
                const ok = await run("edit", () => edit.role !== edit.user.role
                  // one call: the new role and its departments are validated together
                  ? api.patch(`/admin/org/users/${edit.user.id}`, { role: edit.role, department_ids: edit.ids, reason: edit.reason })
                  : api.put(`/admin/org/users/${edit.user.id}/memberships`, { department_ids: edit.ids, reason: edit.reason }), "Access updated.");
                if (ok) { setEdit(null); users.refresh(); }
              }}>Save</Button>
          </>
        )}>
        {edit && (
          <div className="space-y-4">
            <Field label="Role" htmlFor="e-role">
              <select id="e-role" className="input" value={edit.role} onChange={(e) => setEdit({ ...edit, role: e.target.value, ids: [] })}>
                {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
              </select>
            </Field>
            {!NONE.includes(edit.role) && (
              <Field label="Departments" htmlFor="e-dept" error={membershipProblem(edit.role, edit.ids)}>
                <DepartmentChecks departments={depts} value={edit.ids} onChange={(ids) => setEdit({ ...edit, ids })} />
              </Field>
            )}
            <Field label="Reason (required)" htmlFor="e-reason"><input id="e-reason" className="input" value={edit.reason} onChange={(e) => setEdit({ ...edit, reason: e.target.value })} /></Field>
          </div>
        )}
      </Modal>
    </div>
  );
}
