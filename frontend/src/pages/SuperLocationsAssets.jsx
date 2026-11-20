import { useEffect, useState } from "react";
import api, { getApiError } from "../services/api";
import useAction from "../hooks/useAction";
import useResource from "../hooks/useResource";
import { LocationPicker } from "../components/pickers";
import { Alert, Badge, Button, Card, Field, PageHeader } from "../components/ui";

const KINDS = ["campus", "building", "wing", "floor", "corridor", "room"];

/** Browses the location tree one level at a time; new nodes are added under the current node. */
function LocationTree() {
  const [trail, setTrail] = useState([]); // [{id, name}]
  const [children, setChildren] = useState([]);
  const [form, setForm] = useState({ kind: "building", name: "" });
  const [loadError, setLoadError] = useState("");
  const { busy, message, run } = useAction();
  const parent = trail.at(-1);

  useEffect(() => {
    let active = true;
    api.get("/reference/locations", { params: parent ? { parent_id: parent.id } : {} })
      .then(({ data }) => active && (setChildren(data), setLoadError("")))
      .catch((e) => active && setLoadError(getApiError(e, "Could not load locations.")));
    return () => { active = false; };
  }, [parent]);

  return (
    <Card className="p-6">
      <h2 className="mb-3 text-lg font-semibold text-slate-800">Locations</h2>
      <nav aria-label="Location path" className="mb-3 flex flex-wrap gap-1 text-sm">
        <button type="button" className="text-brand-700 underline" onClick={() => setTrail([])}>All</button>
        {trail.map((t, i) => <span key={t.id}> / <button type="button" className="text-brand-700 underline" onClick={() => setTrail(trail.slice(0, i + 1))}>{t.name}</button></span>)}
      </nav>
      {loadError && <Alert variant="error">{loadError}</Alert>}
      {message && <Alert variant={message.variant} className="mb-3">{message.text}</Alert>}
      <ul className="mb-4 space-y-1 text-sm">
        {children.length === 0 && <li className="text-slate-500">Nothing under this location yet.</li>}
        {children.map((c) => (
          <li key={c.id} className="flex items-center justify-between gap-2">
            <button type="button" className="text-left hover:text-brand-700" onClick={() => setTrail([...trail, { id: c.id, name: c.name }])}>{c.name} <Badge>{c.kind}</Badge></button>
            <Button variant="ghost" loading={busy === `l${c.id}`} onClick={async () => (await run(`l${c.id}`, () => api.patch(`/admin/org/locations/${c.id}`, { is_active: false }), "Location hidden.")) && setChildren(children.filter((x) => x.id !== c.id))}>Hide</Button>
          </li>))}
      </ul>
      <form className="grid gap-3 sm:grid-cols-[10rem_1fr_auto] sm:items-end" onSubmit={async (e) => {
        e.preventDefault();
        if (!form.name.trim()) return;
        const body = { kind: form.kind, name: form.name.trim(), ...(parent ? { parent_id: parent.id } : {}) };
        if (await run("loc", () => api.post("/admin/org/locations", body), "Location added.")) {
          setForm({ ...form, name: "" });
          const { data } = await api.get("/reference/locations", { params: parent ? { parent_id: parent.id } : {} });
          setChildren(data);
        }
      }}>
        <Field label="Type" htmlFor="loc-kind"><select id="loc-kind" className="input" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>{KINDS.map((k) => <option key={k}>{k}</option>)}</select></Field>
        <Field label={`Add under ${parent ? parent.name : "the top level"}`} htmlFor="loc-name"><input id="loc-name" className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Button type="submit" loading={busy === "loc"}>Add</Button>
      </form>
    </Card>
  );
}

function Assets() {
  const departments = useResource("/admin/org/departments");
  const [deptId, setDeptId] = useState("");
  const assets = useResource(`/admin/org/assets?limit=200${deptId ? `&department_id=${deptId}` : ""}`);
  const [form, setForm] = useState({ asset_type: "", tag: "", name: "", criticality: 3, location_id: null });
  const { busy, message, run } = useAction();
  const depts = (departments.data || []).filter((d) => d.is_active && !d.is_system);
  return (
    <Card className="p-6">
      <h2 className="mb-3 text-lg font-semibold text-slate-800">Assets</h2>
      {message && <Alert variant={message.variant} className="mb-3">{message.text}</Alert>}
      <div className="mb-4 flex items-center gap-2">
        <select className="input filter-select" aria-label="Department" value={deptId} onChange={(e) => setDeptId(e.target.value)}>
          <option value="">All departments</option>
          {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      </div>
      <ul className="mb-6 divide-y divide-slate-100 text-sm">
        {(assets.data || []).map((a) => (
          <li key={a.id} className="flex items-center justify-between gap-2 py-2">
            <span><strong>{a.tag}</strong> · {a.name} <span className="text-xs text-slate-500">{a.asset_type} · criticality {a.criticality}</span>{!a.is_active && <Badge className="ml-2" tone="red">Inactive</Badge>}</span>
            <Button variant="ghost" loading={busy === `a${a.id}`} onClick={async () => (await run(`a${a.id}`, () => api.patch(`/admin/org/assets/${a.id}`, { is_active: !a.is_active }), "Asset updated.")) && assets.refresh()}>{a.is_active ? "Deactivate" : "Activate"}</Button>
          </li>))}
        {assets.data?.length === 0 && <li className="py-2 text-slate-500">No assets.</li>}
      </ul>
      <form className="space-y-4" onSubmit={async (e) => {
        e.preventDefault();
        if (!deptId || !form.location_id) return;
        if (await run("asset", () => api.post("/admin/org/assets", { ...form, department_id: Number(deptId) }), "Asset added.")) {
          setForm({ ...form, tag: "", name: "" }); assets.refresh();
        }
      }}>
        <h3 className="text-sm font-semibold text-slate-700">Add an asset{deptId ? "" : " (choose a department above first)"}</h3>
        <LocationPicker value={form.location_id} onChange={(id) => setForm((f) => ({ ...f, location_id: id }))} />
        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="Type" htmlFor="a-type"><input id="a-type" className="input" required placeholder="water_cooler" value={form.asset_type} onChange={(e) => setForm({ ...form, asset_type: e.target.value })} /></Field>
          <Field label="Tag" htmlFor="a-tag"><input id="a-tag" className="input" required placeholder="WC-W1-C3-01" value={form.tag} onChange={(e) => setForm({ ...form, tag: e.target.value })} /></Field>
          <Field label="Name" htmlFor="a-name"><input id="a-name" className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Criticality (1–5)" htmlFor="a-crit"><input id="a-crit" type="number" min="1" max="5" className="input" value={form.criticality} onChange={(e) => setForm({ ...form, criticality: Number(e.target.value) })} /></Field>
        </div>
        <Button type="submit" loading={busy === "asset"} disabled={!deptId || !form.location_id}>Add asset</Button>
      </form>
    </Card>
  );
}

export default function SuperLocationsAssets() {
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Administration" title="Locations and assets" description="Students pick a location and an asset when they report, which keeps two identical items in one corridor from being merged." />
      <LocationTree />
      <Assets />
    </div>
  );
}
