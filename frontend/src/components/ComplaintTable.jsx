import { Link } from "react-router-dom";
import { EmptyState, PriorityBadge, StatusBadge } from "./ui";
import Icon from "./Icon";
import { formatDate, isOverdue } from "../utils/complaints";

export default function ComplaintTable({
  complaints,
  departmentNameById = {},
  renderAssignment,
  emptyAction,
  showDepartment = true,
}) {
  if (!complaints.length)
    return (
      <EmptyState
        icon="search"
        title="No matching complaints"
        description="Try a different search or clear your filters."
        action={emptyAction}
      />
    );
  const department = (complaint) =>
    complaint.department_id == null
      ? "Not assigned"
      : departmentNameById[complaint.department_id] ||
        `Department #${complaint.department_id}`;
  return (
    <>
      <div className="table-wrap hidden lg:block">
        <table className="data-table">
          <caption className="sr-only">
            Complaints, their priority, status, and assignment
          </caption>
          <thead>
            <tr>
              <th scope="col">Complaint</th>
              <th scope="col">Priority</th>
              <th scope="col">Status</th>
              {showDepartment && <th scope="col">Department</th>}
              {renderAssignment && <th scope="col">Assigned to</th>}
              <th scope="col">Submitted</th>
              <th scope="col">
                <span className="sr-only">Details</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {complaints.map((complaint) => (
              <tr key={complaint.id}>
                <td className="min-w-56 max-w-sm">
                  <Link
                    to={`/complaints/${complaint.id}`}
                    className="font-semibold text-slate-800 hover:text-brand-700"
                  >
                    {complaint.title}
                  </Link>
                  <p className="mt-1 text-xs text-slate-500">
                    #{complaint.id}{" "}
                    <span className="px-1.5 text-slate-300">/</span>{" "}
                    <span className="capitalize">
                      {complaint.category || "Awaiting classification"}
                    </span>
                  </p>
                </td>
                <td>
                  <PriorityBadge score={complaint.priority_score} />
                </td>
                <td>
                  <StatusBadge status={complaint.status} />
                  {isOverdue(complaint) && (
                    <p className="mt-1.5 flex items-center gap-1 text-xs text-red-700">
                      <Icon name="clock" size={12} /> Past SLA deadline
                    </p>
                  )}
                </td>
                {showDepartment && (
                  <td className="max-w-44 text-slate-500">
                    {department(complaint)}
                  </td>
                )}
                {renderAssignment && <td>{renderAssignment(complaint)}</td>}
                <td className="whitespace-nowrap text-slate-500">
                  {formatDate(complaint.created_at)}
                </td>
                <td>
                  <Link
                    to={`/complaints/${complaint.id}`}
                    className="inline-flex rounded-lg p-2 text-slate-400 hover:bg-brand-50 hover:text-brand-700"
                    aria-label={`View complaint ${complaint.id}`}
                  >
                    <Icon name="arrow-right" size={17} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="divide-y divide-slate-100 lg:hidden">
        {complaints.map((complaint) => (
          <article key={complaint.id} className="p-4 sm:p-5">
            <div className="mb-3 flex items-center justify-between gap-3">
              <span className="text-xs font-medium text-slate-500">
                #{complaint.id} · {formatDate(complaint.created_at)}
              </span>
              <StatusBadge status={complaint.status} />
            </div>
            <Link
              to={`/complaints/${complaint.id}`}
              className="block break-words font-semibold leading-6 text-slate-800 hover:text-brand-700"
            >
              {complaint.title}
            </Link>
            <p className="mt-1 text-xs capitalize text-slate-500">
              {complaint.category || "Awaiting classification"}
              {showDepartment && ` · ${department(complaint)}`}
            </p>
            <div className="mt-4 flex items-center justify-between gap-3">
              <PriorityBadge score={complaint.priority_score} />
              <Link
                to={`/complaints/${complaint.id}`}
                className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700"
              >
                View details <Icon name="arrow-right" size={14} />
              </Link>
            </div>
            {isOverdue(complaint) && (
              <p className="mt-3 text-xs font-medium text-red-700">
                Past SLA deadline
              </p>
            )}
            {renderAssignment && (
              <div className="mt-4 border-t border-slate-100 pt-3">
                <p className="mb-2 text-xs font-medium text-slate-500">
                  Assigned to
                </p>
                {renderAssignment(complaint)}
              </div>
            )}
          </article>
        ))}
      </div>
    </>
  );
}
