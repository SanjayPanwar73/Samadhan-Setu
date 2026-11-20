import { ISSUE_STATUS_LABELS } from "../utils/issues";

export const EMPTY_FILTERS = { status: "", band: "", q: "", escalated: "", needs_review: "", unassigned: "", department_id: "" };

export default function IssueFilters({ filters, onChange, departments = [] }) {
  const set = (key) => (e) => onChange({ ...filters, [key]: e.target.value });
  return (
    <div className="toolbar" role="search" aria-label="Filter issues">
      <input className="input max-w-52" type="search" placeholder="Search ticket no." aria-label="Search by ticket number" value={filters.q} onChange={set("q")} />
      <select className="input filter-select" aria-label="Status" value={filters.status} onChange={set("status")}>
        <option value="">All statuses</option>
        {Object.entries(ISSUE_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
      <select className="input filter-select" aria-label="Priority" value={filters.band} onChange={set("band")}>
        <option value="">All priorities</option>
        {["critical", "high", "medium", "low"].map((b) => <option key={b} value={b} className="capitalize">{b}</option>)}
      </select>
      {departments.length > 1 && (
        <select className="input filter-select" aria-label="Department" value={filters.department_id} onChange={set("department_id")}>
          <option value="">All departments</option>
          {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      )}
      <select className="input filter-select" aria-label="Flags" value={filters.needs_review || filters.unassigned || filters.escalated}
        onChange={(e) => {
          const v = e.target.value;
          onChange({ ...filters, needs_review: v === "review" ? "true" : "", unassigned: v === "unassigned" ? "true" : "", escalated: v === "escalated" ? "true" : "" });
        }}>
        <option value="">Any state</option>
        <option value="unassigned">Unassigned</option>
        <option value="escalated">Escalated</option>
        <option value="review">Needs review</option>
      </select>
    </div>
  );
}
