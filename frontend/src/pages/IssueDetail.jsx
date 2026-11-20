import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import useResource from "../hooks/useResource";
import Tabs from "../components/Tabs";
import { BandBadge, IssueFlags, IssueStatusBadge, SlaIndicator } from "../components/IssueParts";
import {
  AssignmentPanel, DuplicateSuggestionCard, HistoryList, IssueActions, LinkedComplaintsPanel, PriorityPanel, ResolutionReview,
} from "../components/AdminPanels";
import { Alert, Badge, Card, ErrorState, PageHeader, PageSkeleton } from "../components/ui";
import { formatDate } from "../utils/complaints";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "reports", label: "Reports" },
  { id: "work", label: "Work" },
  { id: "priority", label: "Priority" },
  { id: "history", label: "History" },
];
const ACTIVE = ["open", "assigned", "in_progress", "awaiting_verification", "reopened"];

export default function IssueDetail() {
  const { id } = useParams();
  return <IssuePage key={id} id={id} />;
}

function IssuePage({ id }) {
  const [tab, setTab] = useState("overview");
  const issue = useResource(`/issues/${id}`);
  const complaints = useResource(`/issues/${id}/complaints`, { enabled: tab === "reports" });
  const assignments = useResource(`/issues/${id}/assignments`, { enabled: tab === "work" });
  const resolutions = useResource(`/issues/${id}/resolutions`, { enabled: tab === "work" });
  const suggestions = useResource(`/issues/${id}/duplicate-suggestions`);
  const history = useResource(`/issues/${id}/history`, { enabled: tab === "history" });
  const reload = () => {
    issue.refresh();
    suggestions.refresh();
    if (tab === "reports") complaints.refresh();
    if (tab === "work") {
      assignments.refresh();
      resolutions.refresh();
    }
    if (tab === "history") history.refresh();
  };

  if (issue.loading && !issue.data) return <PageSkeleton />;
  if (issue.error) return <Card><ErrorState message={issue.error} onRetry={issue.refresh} /></Card>;
  const i = issue.data;
  const pending = (suggestions.data || []).filter((s) => s.status === "pending");
  return (
    <div className="page-stack">
      <PageHeader eyebrow={i.ticket_no} title={i.title} actions={<Link className="btn btn-secondary" to="/department">Back to queue</Link>} />
      <div className="flex flex-wrap items-center gap-3">
        <IssueStatusBadge status={i.status} />
        <BandBadge band={i.priority_band} score={i.priority_score} />
        <SlaIndicator due={i.sla_resolution_due_at} active={ACTIVE.includes(i.status)} />
        <IssueFlags flags={i.flags} />
        {i.escalation_level > 0 && <Badge tone="red">Escalated ×{i.escalation_level}</Badge>}
      </div>
      {pending.map((s) => <DuplicateSuggestionCard key={s.id} suggestion={s} onDone={reload} />)}
      <Tabs tabs={TABS} value={tab} onChange={setTab} />

      {tab === "overview" && (
        <Card className="p-6">
          <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <div><dt className="text-xs text-slate-500">Category</dt><dd>{i.category}</dd></div>
            <div><dt className="text-xs text-slate-500">Location</dt><dd>{i.location_path}</dd></div>
            <div><dt className="text-xs text-slate-500">Asset</dt><dd>{i.asset_tag || "None"}</dd></div>
            <div><dt className="text-xs text-slate-500">Reports</dt><dd>{i.report_count} from {i.distinct_reporter_count} student(s)</dd></div>
            <div><dt className="text-xs text-slate-500">First reported</dt><dd>{formatDate(i.first_reported_at, { time: true })}</dd></div>
            <div><dt className="text-xs text-slate-500">Resolution due</dt><dd>{formatDate(i.sla_resolution_due_at, { time: true })}</dd></div>
            {i.recurrence_of_issue_id && <div><dt className="text-xs text-slate-500">Recurrence of</dt><dd><Link className="underline" to={`/department/issues/${i.recurrence_of_issue_id}`}>Issue #{i.recurrence_of_issue_id}</Link></dd></div>}
            {i.reopen_count > 0 && <div><dt className="text-xs text-slate-500">Reopened</dt><dd>{i.reopen_count} time(s)</dd></div>}
            <div className="sm:col-span-2"><dt className="text-xs text-slate-500">Summary</dt><dd className="whitespace-pre-wrap">{i.summary}</dd></div>
          </dl>
          <div className="mt-6 border-t border-slate-100 pt-5"><IssueActions issue={i} onChanged={reload} /></div>
        </Card>
      )}
      {tab === "reports" && (
        <Card className="p-6">
          <h2 className="mb-1 text-lg font-semibold text-slate-800">Linked complaints</h2>
          <p className="mb-4 text-xs text-slate-500">Anonymous complaints show a code, never a name.</p>
          {complaints.error ? <Alert variant="error">{complaints.error}</Alert> : complaints.data
            ? <LinkedComplaintsPanel complaints={complaints.data} onRelink={reload} /> : <PageSkeleton />}
        </Card>
      )}
      {tab === "work" && (
        <div className="space-y-5">
          <Card className="p-6">
            <h2 className="mb-3 text-lg font-semibold text-slate-800">Assignment</h2>
            {assignments.error ? <Alert variant="error">{assignments.error}</Alert> : assignments.data
              ? <AssignmentPanel issue={i} assignments={assignments.data} onChanged={reload} /> : <PageSkeleton />}
          </Card>
          <Card className="p-6">
            <h2 className="mb-3 text-lg font-semibold text-slate-800">Resolution reports</h2>
            {resolutions.error ? <Alert variant="error">{resolutions.error}</Alert> : resolutions.data
              ? <ResolutionReview resolutions={resolutions.data} onChanged={reload} /> : <PageSkeleton />}
          </Card>
        </div>
      )}
      {tab === "priority" && <Card className="p-6"><PriorityPanel issue={i} onChanged={reload} /></Card>}
      {tab === "history" && <Card className="p-6">{history.error ? <Alert variant="error">{history.error}</Alert>
        : history.data ? <HistoryList events={history.data} /> : <PageSkeleton />}</Card>}
    </div>
  );
}
