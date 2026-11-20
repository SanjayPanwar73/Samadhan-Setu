import { Link } from "react-router-dom";
import { BandBadge, IssueFlags, IssueStatusBadge, SlaIndicator } from "./IssueParts";
import { EmptyState } from "./ui";

const ACTIVE = ["open", "assigned", "in_progress", "awaiting_verification", "reopened"];

/** One row per issue. Individual duplicate complaints never appear as separate rows. */
export default function IssueQueueTable({ issues, emptyAction }) {
  if (!issues.length)
    return <EmptyState icon="search" title="No matching issues" description="Try a different filter." action={emptyAction} />;
  return (
    <div className="table-wrap">
      <table className="data-table">
        <caption className="sr-only">Issues, their priority, status, assignment and SLA</caption>
        <thead>
          <tr>
            <th scope="col">Issue</th>
            <th scope="col">Place</th>
            <th scope="col">Reports</th>
            <th scope="col">Priority</th>
            <th scope="col">Status</th>
            <th scope="col">Assigned</th>
            <th scope="col">SLA</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((i) => (
            <tr key={i.id}>
              <td className="min-w-56 max-w-sm">
                <Link to={`/department/issues/${i.id}`} className="font-semibold text-slate-800 hover:text-brand-700">{i.title}</Link>
                <p className="mt-1 text-xs text-slate-500">{i.ticket_no} · {i.category}</p>
                <IssueFlags flags={i.flags} />
              </td>
              <td className="max-w-48 text-xs text-slate-600">{i.location_path}{i.asset_tag ? ` · ${i.asset_tag}` : ""}</td>
              <td className="text-sm"><strong>{i.report_count}</strong><span className="block text-xs text-slate-500">{i.distinct_reporter_count} student(s)</span></td>
              <td><BandBadge band={i.priority_band} score={i.priority_score} /></td>
              <td><IssueStatusBadge status={i.status} />{i.escalation_level > 0 && <span className="mt-1 block text-xs text-red-700">Escalated ×{i.escalation_level}</span>}</td>
              <td className="max-w-40 text-xs text-slate-600">{i.assignees.length ? i.assignees.join(", ") : <span className="text-slate-400">Unassigned</span>}</td>
              <td><SlaIndicator due={i.sla_resolution_due_at} active={ACTIVE.includes(i.status)} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
