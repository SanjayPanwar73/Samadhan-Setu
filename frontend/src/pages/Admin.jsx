import { useState } from "react";
import { Link } from "react-router-dom";
import api, { getApiError } from "../services/api";
import useResource from "../hooks/useResource";
import usePagedResource from "../hooks/usePagedResource";
import {
  isOpen,
  isOverdue,
  matchesPriority,
  STATUS_OPTIONS,
} from "../utils/complaints";
import ComplaintTable from "../components/ComplaintTable";
import PasswordInput from "../components/PasswordInput";
import Tabs from "../components/Tabs";
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
  StatCard,
  TableSkeleton,
} from "../components/ui";

function TeamPanel({ staff, departments, onCreate }) {
  const workload = useResource("/admin/staff-workload", { collection: true });
  const management = useResource("/admin/management", { collection: true });
  const [query, setQuery] = useState("");
  const names = Object.fromEntries(
    (departments.data || []).map((item) => [item.id, item.name]),
  );
  const counts = Object.fromEntries(
    (workload.data || []).map((item) => [
      item.staff_id,
      item.open_complaint_count,
    ]),
  );
  const members = [...(staff.data || []), ...(management.data || [])].filter(
    (item) =>
      `${item.name} ${item.email}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );
  return (
    <div className="space-y-6">
      <Card>
        <div className="panel-heading">
          <div>
            <h2>Team directory</h2>
            <p>Staff and management accounts across your workspace.</p>
          </div>
          <Button variant="secondary" onClick={onCreate}>
            <Icon name="plus" size={15} />
            Add member
          </Button>
        </div>
        <div className="toolbar">
          <div className="search-field">
            <Icon name="search" size={16} />
            <input
              className="input"
              type="search"
              aria-label="Search team members"
              placeholder="Search name or email…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <span className="text-xs text-slate-500">
            {members.length} members shown
          </span>
        </div>
        {staff.error && (
          <div className="m-5">
            <Alert variant="error">
              {staff.error}{" "}
              <button className="underline" onClick={staff.refresh}>
                Retry staff
              </button>
            </Alert>
          </div>
        )}
        {management.error && (
          <div className="m-5">
            <Alert variant="error">
              {management.error}{" "}
              <button className="underline" onClick={management.refresh}>
                Retry management
              </button>
            </Alert>
          </div>
        )}
        {staff.loading || management.loading ? (
          <TableSkeleton />
        ) : !members.length ? (
          <EmptyState
            icon="users"
            title={
              query ? "No matching team members" : "Bring your team together"
            }
            description={
              query
                ? "Try a different name or email address."
                : "Create staff and management accounts to help resolve concerns."
            }
          />
        ) : (
          <ul className="divide-y divide-slate-100">
            {members.map((item) => (
              <li
                key={item.id}
                className="flex flex-wrap items-center gap-3 p-5"
              >
                <span className="avatar">{item.name.charAt(0)}</span>
                <div className="min-w-0 flex-1">
                  <p className="break-words text-sm font-medium text-slate-700">
                    {item.name}
                  </p>
                  <p className="mt-1 break-all text-xs text-slate-500">
                    {item.email}
                  </p>
                </div>
                <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
                  <span className="hidden text-xs text-slate-500 sm:block">
                    {item.role === "staff"
                      ? names[item.department_id] || "No department"
                      : "Workspace-wide"}
                  </span>
                  <Badge tone={item.role === "staff" ? "green" : "blue"}>
                    {item.role}
                  </Badge>
                  {item.role === "staff" &&
                    !workload.loading &&
                    !workload.error && (
                      <Badge>{counts[item.id] ?? 0} open</Badge>
                    )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card>
        <div className="panel-heading">
          <div>
            <h2>Staff workload</h2>
            <p>
              Open assignments for each staff member, including reopened
              concerns.
            </p>
          </div>
          <Button
            variant="ghost"
            className="icon-button"
            disabled={workload.loading}
            aria-label="Refresh staff workload"
            onClick={workload.refresh}
          >
            <Icon name="refresh" size={16} />
          </Button>
        </div>
        {workload.loading ? (
          <TableSkeleton rows={3} />
        ) : workload.error ? (
          <ErrorState message={workload.error} onRetry={workload.refresh} />
        ) : !workload.data?.length ? (
          <EmptyState
            icon="users"
            title="No staff accounts yet"
            description="Create a staff account to begin assigning concerns."
          />
        ) : (
          <div className="grid gap-4 p-5 sm:grid-cols-2 xl:grid-cols-3">
            {[...workload.data]
              .sort((a, b) => b.open_complaint_count - a.open_complaint_count)
              .map((item) => (
                <div
                  key={item.staff_id}
                  className="rounded-xl border border-slate-200 p-4"
                >
                  <p className="text-sm font-medium text-slate-700">
                    {item.name}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {item.department || "No department"}
                  </p>
                  <p className="mt-4 text-2xl font-semibold tracking-tight text-brand-900">
                    {item.open_complaint_count}
                    <span className="ml-2 text-xs font-normal text-slate-500">
                      open concerns
                    </span>
                  </p>
                </div>
              ))}
          </div>
        )}
      </Card>
    </div>
  );
}

const INITIAL = { name: "", email: "", password: "", department: "" };
export default function Admin() {
  const complaints = usePagedResource("/admin/complaints");
  const departments = useResource("/admin/departments", { collection: true });
  const staff = useResource("/admin/staff", { collection: true });
  const [tab, setTab] = useState("queue");
  const [teamRevision, setTeamRevision] = useState(0);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [priority, setPriority] = useState("all");
  const [department, setDepartment] = useState("all");
  const [sort, setSort] = useState("priority");
  const [assigning, setAssigning] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [accountOpen, setAccountOpen] = useState(false);
  const [accountRole, setAccountRole] = useState("staff");
  const [account, setAccount] = useState(INITIAL);
  const [accountError, setAccountError] = useState("");
  const [creating, setCreating] = useState(false);
  const departmentNames = Object.fromEntries(
    (departments.data || []).map((item) => [item.id, item.name]),
  );
  const visible = complaints.data
    .filter(
      (item) =>
        (status === "all" || item.status === status) &&
        (priority === "all" ||
          matchesPriority(item.priority_score, priority)) &&
        (department === "all" ||
          (department === "unassigned"
            ? item.department_id == null
            : String(item.department_id) === department)) &&
        `${item.id} ${item.title} ${item.category || ""}`
          .toLowerCase()
          .includes(query.trim().toLowerCase()),
    )
    .sort((a, b) =>
      sort === "priority"
        ? (b.priority_score ?? -1) - (a.priority_score ?? -1)
        : new Date(b.created_at) - new Date(a.created_at),
    );
  const ready = !complaints.loading && !complaints.error;
  function openAccount() {
    setAccountOpen(true);
    setAccount(INITIAL);
    setAccountRole("staff");
    setAccountError("");
  }
  async function assign(item, staffId) {
    if (assigning != null || String(item.assigned_to ?? "") === staffId) return;
    setAssigning(item.id);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.patch(`/admin/complaints/${item.id}/assign`, {
        staff_id: staffId === "" ? null : Number(staffId),
      });
      complaints.setData((current) =>
        current.map((row) => (row.id === item.id ? data : row)),
      );
      setSuccess(`Assignment updated for complaint #${item.id}.`);
      setTeamRevision((value) => value + 1);
    } catch (requestError) {
      setError(
        getApiError(requestError, "We couldn’t update this assignment."),
      );
    } finally {
      setAssigning(null);
    }
  }
  function assignment(item) {
    return (
      <select
        className="input !min-h-9 max-w-52 !py-1.5 !text-xs"
        aria-label={`Assign complaint ${item.id}`}
        value={item.assigned_to ?? ""}
        disabled={assigning != null || staff.loading || Boolean(staff.error)}
        onChange={(event) => assign(item, event.target.value)}
      >
        <option value="">Unassigned</option>
        {item.assigned_to != null &&
          !staff.data?.some((member) => member.id === item.assigned_to) && (
            <option value={item.assigned_to}>Staff #{item.assigned_to}</option>
          )}
        {[...(staff.data || [])]
          .sort(
            (a, b) =>
              Number(b.department_id === item.department_id) -
              Number(a.department_id === item.department_id),
          )
          .map((member) => (
            <option key={member.id} value={member.id}>
              {member.name}
              {member.department_id != null &&
              member.department_id === item.department_id
                ? " · Same department"
                : ""}
            </option>
          ))}
      </select>
    );
  }
  async function createAccount(event) {
    event.preventDefault();
    if (creating) return;
    setAccountError("");
    if (!account.name.trim()) {
      setAccountError("Enter the team member’s name.");
      return;
    }
    if (
      account.password.length < 8 ||
      new TextEncoder().encode(account.password).length > 72
    ) {
      setAccountError(
        "Use a password with at least 8 characters and no more than 72 bytes.",
      );
      return;
    }
    setCreating(true);
    try {
      const { data } = await api.post(`/admin/${accountRole}`, {
        name: account.name.trim(),
        email: account.email.trim(),
        password: account.password,
        ...(accountRole === "staff" && account.department
          ? { department_id: Number(account.department) }
          : {}),
      });
      setSuccess(
        `${data.role || accountRole} account created for ${data.email || account.email.trim()}.`,
      );
      setAccountOpen(false);
      setAccount(INITIAL);
      if (accountRole === "staff") await staff.refresh();
      setTeamRevision((value) => value + 1);
    } catch (requestError) {
      setAccountError(
        getApiError(requestError, "We couldn’t create the account."),
      );
    } finally {
      setCreating(false);
    }
  }
  function resetFilters() {
    setQuery("");
    setStatus("all");
    setPriority("all");
    setDepartment("all");
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Workspace operations"
        title="Keep every concern moving."
        description="Coordinate teams, manage assignments, and bring clarity to your resolution workflow."
        actions={
          <>
            <Link className="btn btn-secondary" to="/admin/departments">
              <Icon name="building" size={16} />
              Departments
            </Link>
            <Button onClick={openAccount}>
              <Icon name="plus" size={16} />
              Add team member
            </Button>
          </>
        }
      />
      {success && <Alert variant="success">{success}</Alert>}
      {error && <Alert variant="error">{error}</Alert>}
      <div className="stats-grid">
        <StatCard
          label="Complaints loaded"
          value={ready ? complaints.data.length : null}
          icon="file"
          hint="Summaries cover the loaded queue"
        />
        <StatCard
          label="Open concerns"
          value={ready ? complaints.data.filter(isOpen).length : null}
          icon="clock"
          tone="amber"
          hint="Pending, in progress, and reopened"
        />
        <StatCard
          label="Awaiting assignment"
          value={
            ready
              ? complaints.data.filter(
                  (item) => isOpen(item) && item.assigned_to == null,
                ).length
              : null
          }
          icon="users"
          tone="blue"
          hint="Open concerns with no staff assigned"
        />
        <StatCard
          label="Past SLA deadline"
          value={ready ? complaints.data.filter(isOverdue).length : null}
          icon="alertCircle"
          tone="orange"
          hint="Open concerns needing attention"
        />
      </div>
      <Tabs
        tabs={[
          { id: "queue", label: "Complaint queue" },
          { id: "team", label: "Team & workload" },
        ]}
        value={tab}
        onChange={setTab}
      />
      <div
        id={`panel-${tab}`}
        role="tabpanel"
        aria-labelledby={`tab-${tab}`}
        tabIndex={0}
      >
        {tab === "team" ? (
          <TeamPanel
            key={teamRevision}
            staff={staff}
            departments={departments}
            onCreate={openAccount}
          />
        ) : (
          <Card>
            <div className="panel-heading">
              <div>
                <h2>All complaints</h2>
                <p>
                  Find a concern, review its priority, and assign the right
                  person.
                </p>
              </div>
              <Button
                variant="ghost"
                className="!min-h-8 !px-2 !text-xs"
                disabled={
                  complaints.loading ||
                  complaints.loadingMore ||
                  assigning != null
                }
                onClick={complaints.refresh}
              >
                <Icon name="refresh" size={14} />
                Refresh
              </Button>
            </div>
            <div className="toolbar">
              <div className="search-field">
                <Icon name="search" size={16} />
                <input
                  className="input"
                  type="search"
                  aria-label="Search loaded complaints"
                  placeholder="Search title, category, or ID…"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <select
                  className="input filter-select"
                  aria-label="Filter by status"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                >
                  <option value="all">All statuses</option>
                  {STATUS_OPTIONS.map((value) => (
                    <option key={value} value={value}>
                      {value.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
                <select
                  className="input filter-select"
                  aria-label="Filter by priority"
                  value={priority}
                  onChange={(event) => setPriority(event.target.value)}
                >
                  <option value="all">All priorities</option>
                  {["critical", "high", "medium", "low"].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
                <select
                  className="input filter-select max-w-52"
                  aria-label="Filter by department"
                  value={department}
                  onChange={(event) => setDepartment(event.target.value)}
                  disabled={departments.loading || Boolean(departments.error)}
                >
                  <option value="all">All departments</option>
                  <option value="unassigned">No department</option>
                  {departments.data?.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
                <select
                  className="input filter-select"
                  aria-label="Sort complaints"
                  value={sort}
                  onChange={(event) => setSort(event.target.value)}
                >
                  <option value="priority">Highest priority</option>
                  <option value="recent">Newest first</option>
                </select>
              </div>
            </div>
            {complaints.hasMore && (
              <p className="px-6 pb-3 text-[11px] text-slate-500">
                Search, filters, and summaries cover {complaints.data.length}{" "}
                loaded records. Load more to expand the queue.
              </p>
            )}
            {departments.error && (
              <div className="mx-5 mb-4">
                <Alert variant="error">
                  Department names are unavailable.{" "}
                  <button className="underline" onClick={departments.refresh}>
                    Retry
                  </button>
                </Alert>
              </div>
            )}
            {staff.error && (
              <div className="mx-5 mb-4">
                <Alert variant="error">
                  Assignment options are unavailable.{" "}
                  <button className="underline" onClick={staff.refresh}>
                    Retry staff
                  </button>
                </Alert>
              </div>
            )}
            {complaints.loading ? (
              <TableSkeleton />
            ) : complaints.error && !complaints.data.length ? (
              <ErrorState
                message={complaints.error}
                onRetry={complaints.retry}
              />
            ) : (
              <>
                {complaints.error && (
                  <div className="m-5">
                    <Alert variant="error">
                      {complaints.error}{" "}
                      <button className="underline" onClick={complaints.retry}>
                        Retry
                      </button>
                    </Alert>
                  </div>
                )}
                {!complaints.data.length ? (
                  <EmptyState
                    icon="file"
                    title="No complaints yet"
                    description="Submitted concerns will appear here, ready for your team to review."
                  />
                ) : (
                  <ComplaintTable
                    complaints={visible}
                    departmentNameById={departmentNames}
                    renderAssignment={assignment}
                    emptyAction={
                      <Button variant="secondary" onClick={resetFilters}>
                        Clear filters
                      </Button>
                    }
                  />
                )}
                <div className="pagination">
                  <p>
                    {visible.length} of {complaints.data.length} loaded
                    complaints{!complaints.hasMore && " · All records loaded"}
                  </p>
                  <div className="flex gap-2">
                    {(query ||
                      status !== "all" ||
                      priority !== "all" ||
                      department !== "all") && (
                      <Button variant="ghost" onClick={resetFilters}>
                        Clear filters
                      </Button>
                    )}
                    {complaints.hasMore && (
                      <Button
                        variant="secondary"
                        onClick={complaints.loadMore}
                        loading={complaints.loadingMore}
                        disabled={assigning != null}
                      >
                        Load more
                      </Button>
                    )}
                  </div>
                </div>
              </>
            )}
          </Card>
        )}
      </div>
      <Modal
        open={accountOpen}
        onClose={() => setAccountOpen(false)}
        busy={creating}
        title="Add a team member"
        description="Create an account with the access this person needs."
        footer={
          <>
            <Button
              variant="secondary"
              disabled={creating}
              onClick={() => setAccountOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" form="team-account" loading={creating}>
              Create account
            </Button>
          </>
        }
      >
        <form id="team-account" onSubmit={createAccount} className="space-y-4">
          <Field label="Account role" htmlFor="account-role">
            <select
              id="account-role"
              className="input"
              value={accountRole}
              onChange={(event) => setAccountRole(event.target.value)}
              disabled={creating}
            >
              <option value="staff">Staff — resolve assigned concerns</option>
              <option value="management">
                Management — view analytics and priorities
              </option>
            </select>
          </Field>
          <Field label="Full name" htmlFor="account-name">
            <input
              id="account-name"
              className="input"
              required
              maxLength={120}
              autoComplete="off"
              value={account.name}
              onChange={(event) =>
                setAccount((current) => ({
                  ...current,
                  name: event.target.value,
                }))
              }
              disabled={creating}
            />
          </Field>
          <Field label="Email address" htmlFor="account-email">
            <input
              id="account-email"
              className="input"
              type="email"
              required
              autoComplete="off"
              value={account.email}
              onChange={(event) =>
                setAccount((current) => ({
                  ...current,
                  email: event.target.value,
                }))
              }
              disabled={creating}
            />
          </Field>
          <Field
            label="Initial password"
            htmlFor="account-password"
            hint="Use at least 8 characters. Share credentials privately with the account owner."
          >
            <PasswordInput
              id="account-password"
              required
              minLength={8}
              maxLength={72}
              autoComplete="new-password"
              value={account.password}
              onChange={(event) =>
                setAccount((current) => ({
                  ...current,
                  password: event.target.value,
                }))
              }
              disabled={creating}
            />
          </Field>
          {accountRole === "staff" && (
            <Field label="Department (optional)" htmlFor="account-department">
              <select
                id="account-department"
                className="input"
                value={account.department}
                onChange={(event) =>
                  setAccount((current) => ({
                    ...current,
                    department: event.target.value,
                  }))
                }
                disabled={
                  creating || departments.loading || Boolean(departments.error)
                }
              >
                <option value="">No department</option>
                {departments.data?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
          )}
          {accountError && <Alert variant="error">{accountError}</Alert>}
        </form>
      </Modal>
    </div>
  );
}
