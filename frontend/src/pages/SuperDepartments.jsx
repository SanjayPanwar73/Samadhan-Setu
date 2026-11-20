import { useState } from "react";
import api from "../services/api";
import useAction from "../hooks/useAction";
import useResource from "../hooks/useResource";
import { Alert, Badge, Button, Card, ErrorState, Field, PageHeader, TableSkeleton } from "../components/ui";

const BLANK_CATEGORY = { name: "", base_severity: 0.3, default_criticality: 0.3, impact_level: 0.3, expected_resolution_hours: 48, requires_verification: false, requires_evidence: false };

export default function SuperDepartments() {
  const departments = useResource("/admin/org/departments");
  const [selected, setSelected] = useState("");
  const categories = useResource(`/admin/org/categories${selected ? `?department_id=${selected}` : ""}`, { enabled: Boolean(selected) });
  const [dept, setDept] = useState({ name: "", code: "", requires_verification_default: false });
  const [cat, setCat] = useState(BLANK_CATEGORY);
  const { busy, message, run } = useAction();
  const num = (key) => (e) => setCat({ ...cat, [key]: Number(e.target.value) });

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Administration" title="Departments and categories" description="Departments are deactivated, never deleted. Categories drive classification, priority inputs and resolution rules." />
      {message && <Alert variant={message.variant}>{message.text}</Alert>}
      <Card className="p-6">
        <h2 className="mb-3 text-lg font-semibold text-slate-800">Add a department</h2>
        <form className="grid gap-4 sm:grid-cols-[1fr_8rem_auto_auto] sm:items-end" onSubmit={async (e) => {
          e.preventDefault();
          if (await run("dept", () => api.post("/admin/org/departments", { ...dept, code: dept.code.toUpperCase() }), "Department created.")) {
            setDept({ name: "", code: "", requires_verification_default: false });
            departments.refresh();
          }
        }}>
          <Field label="Name" htmlFor="d-name"><input id="d-name" className="input" required minLength={2} value={dept.name} onChange={(e) => setDept({ ...dept, name: e.target.value })} /></Field>
          <Field label="Code" htmlFor="d-code" hint="Letters only, e.g. WAT"><input id="d-code" className="input" required minLength={2} maxLength={8} pattern="[A-Za-z]+" value={dept.code} onChange={(e) => setDept({ ...dept, code: e.target.value })} /></Field>
          <label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" checked={dept.requires_verification_default} onChange={(e) => setDept({ ...dept, requires_verification_default: e.target.checked })} />Verify fixes</label>
          <Button type="submit" loading={busy === "dept"}>Add</Button>
        </form>
      </Card>
      <Card>
        {departments.loading ? <TableSkeleton /> : departments.error ? <ErrorState message={departments.error} onRetry={departments.refresh} /> : (
          <div className="table-wrap"><table className="data-table">
            <caption className="sr-only">Departments</caption>
            <thead><tr><th scope="col">Department</th><th scope="col">Code</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>{departments.data.map((d) => (
              <tr key={d.id}>
                <td className="font-medium text-slate-800">{d.name} {d.is_system && <Badge>System</Badge>}</td>
                <td>{d.code}</td>
                <td>{d.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Inactive</Badge>}</td>
                <td className="space-x-2 whitespace-nowrap">
                  <Button variant="secondary" onClick={() => setSelected(String(d.id))}>Categories</Button>
                  {!d.is_system && <Button variant="ghost" loading={busy === `t${d.id}`} onClick={async () => (await run(`t${d.id}`, () => api.patch(`/admin/org/departments/${d.id}`, { is_active: !d.is_active }), d.is_active ? "Deactivated." : "Activated.")) && departments.refresh()}>{d.is_active ? "Deactivate" : "Activate"}</Button>}
                </td>
              </tr>))}</tbody></table></div>
        )}
      </Card>
      {selected && (
        <Card className="p-6">
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Categories · {(departments.data || []).find((d) => String(d.id) === selected)?.name}</h2>
          {categories.error ? <ErrorState message={categories.error} onRetry={categories.refresh} /> : (
            <ul className="mb-6 divide-y divide-slate-100 text-sm">
              {(categories.data || []).map((c) => (
                <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <span><strong>{c.name}</strong> <span className="text-xs text-slate-500">severity {c.base_severity} · criticality {c.default_criticality} · impact {c.impact_level} · {c.expected_resolution_hours} h</span>
                    {c.requires_verification && <Badge className="ml-2" tone="blue">Verified</Badge>}{c.requires_evidence && <Badge className="ml-1" tone="blue">Evidence</Badge>}{!c.is_active && <Badge className="ml-1" tone="red">Inactive</Badge>}</span>
                  <Button variant="ghost" loading={busy === `c${c.id}`} onClick={async () => (await run(`c${c.id}`, () => api.patch(`/admin/org/categories/${c.id}`, { is_active: !c.is_active }), "Category updated.")) && categories.refresh()}>{c.is_active ? "Deactivate" : "Activate"}</Button>
                </li>))}
            </ul>
          )}
          <form className="grid gap-3 sm:grid-cols-3" onSubmit={async (e) => {
            e.preventDefault();
            if (await run("cat", () => api.post("/admin/org/categories", { ...cat, department_id: Number(selected) }), "Category added.")) { setCat(BLANK_CATEGORY); categories.refresh(); }
          }}>
            <Field label="New category" htmlFor="c-name" className="sm:col-span-3"><input id="c-name" className="input" required minLength={2} value={cat.name} onChange={(e) => setCat({ ...cat, name: e.target.value })} /></Field>
            <Field label="Base severity (0–1)" htmlFor="c-sev"><input id="c-sev" type="number" step="0.05" min="0" max="1" className="input" value={cat.base_severity} onChange={num("base_severity")} /></Field>
            <Field label="Criticality (0–1)" htmlFor="c-crit"><input id="c-crit" type="number" step="0.05" min="0" max="1" className="input" value={cat.default_criticality} onChange={num("default_criticality")} /></Field>
            <Field label="Academic impact (0–1)" htmlFor="c-imp"><input id="c-imp" type="number" step="0.05" min="0" max="1" className="input" value={cat.impact_level} onChange={num("impact_level")} /></Field>
            <Field label="Expected resolution (hours)" htmlFor="c-hrs"><input id="c-hrs" type="number" min="1" className="input" value={cat.expected_resolution_hours} onChange={num("expected_resolution_hours")} /></Field>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={cat.requires_verification} onChange={(e) => setCat({ ...cat, requires_verification: e.target.checked })} />Needs verification</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={cat.requires_evidence} onChange={(e) => setCat({ ...cat, requires_evidence: e.target.checked })} />Needs photo evidence</label>
            <div className="sm:col-span-3"><Button type="submit" loading={busy === "cat"}>Add category</Button></div>
          </form>
        </Card>
      )}
    </div>
  );
}
