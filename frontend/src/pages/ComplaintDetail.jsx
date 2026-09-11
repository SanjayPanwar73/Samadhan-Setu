import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import api, { getApiError } from "../services/api";
import { useAuth } from "../contexts/AuthContext";
import useResource from "../hooks/useResource";
import { getHomeRouteForRole } from "../utils/auth";
import { formatDate, isOverdue } from "../utils/complaints";
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
  PageSkeleton,
  PriorityBadge,
  StatusBadge,
} from "../components/ui";

const TRANSITIONS = {
  pending: ["in_progress", "rejected"],
  in_progress: ["resolved", "rejected"],
  reopened: ["in_progress"],
  resolved: [],
  rejected: [],
};
const ACTIONS = {
  in_progress: "Mark in progress",
  resolved: "Mark resolved",
  rejected: "Reject complaint",
};

function Detail({ id }) {
  const { user, role } = useAuth();
  const resource = useResource(`/complaints/${id}`);
  const complaint = resource.data;
  const departments = useResource("/admin/departments", {
    enabled: role === "admin",
    collection: true,
  });
  const suggestion = useResource(`/complaints/${id}/suggested-resolution`, {
    enabled: false,
    timeout: 120000,
  });
  const [resolution, setResolution] = useState("");
  const [pendingStatus, setPendingStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [success, setSuccess] = useState("");
  const [rating, setRating] = useState("");
  const [comment, setComment] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [override, setOverride] = useState({ department: "", priority: "" });
  const [review, setReview] = useState(null);
  const [overrideError, setOverrideError] = useState("");
  const canAct =
    role === "admin" ||
    (role === "staff" && complaint?.assigned_to === user?.id);
  const canFeedback =
    complaint?.created_by === user?.id &&
    complaint?.status === "resolved" &&
    !feedbackSent;
  const departmentName =
    complaint?.department_id == null
      ? "Not assigned"
      : departments.data?.find((item) => item.id === complaint.department_id)
          ?.name || `Department #${complaint.department_id}`;

  async function changeStatus(nextStatus) {
    if (busy) return;
    setBusy(true);
    setActionError("");
    setSuccess("");
    try {
      const { data } = await api.patch(`/complaints/${id}/status`, {
        status: nextStatus,
        ...(nextStatus === "resolved" && resolution.trim()
          ? { resolution_text: resolution.trim() }
          : {}),
      });
      resource.setData(data);
      setPendingStatus(null);
      setResolution("");
      setSuccess(`Complaint marked ${nextStatus.replaceAll("_", " ")}.`);
    } catch (error) {
      setActionError(
        getApiError(error, "We couldn’t update the status. Please try again."),
      );
    } finally {
      setBusy(false);
    }
  }
  async function sendFeedback(event) {
    event.preventDefault();
    if (busy) return;
    setActionError("");
    setSuccess("");
    if (!rating) {
      setActionError("Choose a rating before submitting your feedback.");
      return;
    }
    setBusy(true);
    try {
      await api.post(`/complaints/${id}/feedback`, {
        rating: Number(rating),
        comment: comment.trim() || null,
      });
      setFeedbackSent(true);
      setSuccess(
        Number(rating) <= 2
          ? "Thank you for your feedback. Your complaint has been reopened for another review."
          : "Thank you. Your feedback has been recorded.",
      );
      // Feedback does not return a complaint; refresh to receive any reopened
      // status, recalculated priority, and escalation from the backend.
      await resource.refresh();
    } catch (error) {
      setActionError(
        getApiError(error, "We couldn’t submit feedback. Please try again."),
      );
    } finally {
      setBusy(false);
    }
  }
  function openOverride() {
    setOverride({
      department:
        complaint.department_id == null ? "" : String(complaint.department_id),
      priority:
        complaint.priority_score == null
          ? ""
          : String(complaint.priority_score),
    });
    setReview(null);
    setOverrideError("");
    setOverrideOpen(true);
  }
  function reviewOverride(event) {
    event.preventDefault();
    setOverrideError("");
    const payload = {};
    const summary = [];
    if (
      override.department !==
      (complaint.department_id == null ? "" : String(complaint.department_id))
    ) {
      if (!override.department) {
        setOverrideError(
          "Choose a department. An existing department cannot be cleared here.",
        );
        return;
      }
      payload.department_id = Number(override.department);
      summary.push(
        `Department: ${departmentName} → ${departments.data?.find((item) => item.id === payload.department_id)?.name || `#${payload.department_id}`}`,
      );
    }
    if (
      override.priority !== "" &&
      Number(override.priority) !== complaint.priority_score
    ) {
      const value = Number(override.priority);
      if (!Number.isFinite(value) || value < 0 || value > 100) {
        setOverrideError("Priority must be a number from 0 to 100.");
        return;
      }
      payload.priority_score = value;
      summary.push(
        `Priority: ${complaint.priority_score ?? "Unscored"} → ${value}`,
      );
    }
    if (!Object.keys(payload).length) {
      setOverrideError("Change the department or priority before continuing.");
      return;
    }
    setReview({ payload, summary });
  }
  async function confirmOverride() {
    if (busy) return;
    setBusy(true);
    setOverrideError("");
    try {
      const { data } = await api.patch(
        `/complaints/${id}/override`,
        review.payload,
      );
      resource.setData(data);
      setOverrideOpen(false);
      setReview(null);
      setSuccess("The department and priority changes have been saved.");
    } catch (error) {
      setOverrideError(getApiError(error, "We couldn’t save these changes."));
    } finally {
      setBusy(false);
    }
  }

  if (resource.loading && !complaint) return <PageSkeleton />;
  if (!complaint)
    return (
      <Card>
        <ErrorState
          message={resource.error || "This complaint is not available."}
          onRetry={resource.refresh}
        />
        <div className="pb-6 text-center">
          <Link className="btn btn-secondary" to={getHomeRouteForRole(role)}>
            Back to workspace
          </Link>
        </div>
      </Card>
    );
  return (
    <div className="page-stack">
      <Link
        className="inline-flex w-fit items-center gap-2 text-xs text-slate-500 hover:text-brand-600"
        to={getHomeRouteForRole(role)}
      >
        <Icon name="arrowLeft" size={15} />
        Back to workspace
      </Link>
      <PageHeader
        eyebrow={`Complaint #${complaint.id}`}
        title={complaint.title}
        description={`Submitted ${formatDate(complaint.created_at, { time: true })}`}
        actions={<StatusBadge status={complaint.status} />}
      />
      {success && <Alert variant="success">{success}</Alert>}
      {actionError && !pendingStatus && (
        <Alert variant="error">{actionError}</Alert>
      )}
      {resource.error && (
        <Alert variant="error">
          {resource.error}{" "}
          <button className="underline" onClick={resource.refresh}>
            Refresh details
          </button>
        </Alert>
      )}
      {complaint.status === "reopened" && (
        <Alert>This complaint is open again and awaiting further action.</Alert>
      )}
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(280px,1fr)]">
        <div className="space-y-6">
          <Card>
            <div className="panel-heading">
              <h2>What was reported</h2>
              <Icon name="file" size={18} className="text-slate-400" />
            </div>
            <div className="p-6">
              <p className="whitespace-pre-wrap text-sm leading-7 text-slate-600">
                {complaint.description}
              </p>
            </div>
          </Card>
          {canAct && (
            <Card>
              <div className="panel-heading">
                <div>
                  <h2>Move this concern forward</h2>
                  <p>Update the status as work progresses.</p>
                </div>
                <Icon name="checkCircle" size={19} className="text-brand-500" />
              </div>
              <div className="space-y-5 p-6">
                {(TRANSITIONS[complaint.status] || []).length === 0 ? (
                  <p className="text-sm text-slate-500">
                    No further status changes are available for this complaint.
                  </p>
                ) : (
                  <>
                    {TRANSITIONS[complaint.status].includes("resolved") && (
                      <Field
                        label="Resolution note (optional)"
                        htmlFor="resolution"
                        hint="Share the action taken. Clear notes can help with similar concerns in the future."
                      >
                        <textarea
                          id="resolution"
                          className="input"
                          rows={4}
                          maxLength={5000}
                          placeholder="What did you do to resolve this concern?"
                          value={resolution}
                          onChange={(event) =>
                            setResolution(event.target.value)
                          }
                          disabled={busy}
                        />
                      </Field>
                    )}
                    <div className="flex flex-wrap gap-3">
                      {TRANSITIONS[complaint.status].map((next) => (
                        <Button
                          key={next}
                          variant={
                            next === "rejected" ? "secondary" : "primary"
                          }
                          disabled={busy}
                          onClick={() => {
                            setActionError("");
                            if (next === "in_progress") void changeStatus(next);
                            else setPendingStatus(next);
                          }}
                        >
                          <Icon
                            name={next === "rejected" ? "x" : "checkCircle"}
                            size={16}
                          />
                          {ACTIONS[next]}
                        </Button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </Card>
          )}
          {canAct && (
            <Card className="border-brand-100">
              <div className="panel-heading">
                <div>
                  <h2 className="flex items-center gap-2">
                    <Icon
                      name="sparkles"
                      size={17}
                      className="text-brand-500"
                    />
                    Resolution guidance
                  </h2>
                  <p>Learn from similar concerns resolved in the past.</p>
                </div>
              </div>
              <div className="space-y-4 p-6">
                <p className="text-xs leading-6 text-slate-500">
                  Suggestions are advisory. Review the context and decide what
                  is appropriate for this complaint.
                </p>
                {!suggestion.data && (
                  <Button
                    variant="secondary"
                    loading={suggestion.loading}
                    onClick={suggestion.refresh}
                  >
                    <Icon name="sparkles" size={16} />
                    {suggestion.loading
                      ? "Finding guidance…"
                      : "Find resolution guidance"}
                  </Button>
                )}
                {suggestion.error && (
                  <Alert variant="error">{suggestion.error}</Alert>
                )}
                {suggestion.data && (
                  <>
                    {!suggestion.data.retrieved_cases?.length && (
                      <EmptyState
                        icon="file"
                        title="No similar resolutions yet"
                        description="There isn’t enough matching resolved history to offer guidance for this concern."
                      />
                    )}
                    {suggestion.data.generated &&
                      suggestion.data.suggested_action && (
                        <div className="rounded-xl border border-brand-100 bg-brand-50 p-4">
                          <Badge tone="green">
                            AI suggestion · Review before use
                          </Badge>
                          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-600">
                            {suggestion.data.suggested_action}
                          </p>
                        </div>
                      )}
                    {suggestion.data.retrieved_cases?.map((item, index) => (
                      <article
                        key={`${item.complaint_id}-${index}`}
                        className="rounded-lg border border-slate-200 p-4"
                      >
                        <div className="flex flex-wrap justify-between gap-2 text-xs text-slate-500">
                          <span>Past complaint #{item.complaint_id}</span>
                          <Badge>
                            {Math.round(item.similarity * 100)}% similar
                          </Badge>
                        </div>
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">
                          {item.resolution_text}
                        </p>
                      </article>
                    ))}
                  </>
                )}
              </div>
            </Card>
          )}
          {canFeedback && (
            <Card>
              <div className="panel-heading">
                <div>
                  <h2>How did we do?</h2>
                  <p>Your feedback helps improve future resolutions.</p>
                </div>
                <Icon name="users" size={19} className="text-brand-500" />
              </div>
              <form className="space-y-5 p-6" onSubmit={sendFeedback}>
                <fieldset>
                  <legend className="text-sm font-medium text-slate-700">
                    Rate your resolution
                  </legend>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {[1, 2, 3, 4, 5].map((value) => (
                      <label
                        key={value}
                        className={`flex min-h-11 min-w-12 cursor-pointer items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm ${Number(rating) === value ? "border-brand-500 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-500"}`}
                      >
                        <input
                          type="radio"
                          name="rating"
                          value={value}
                          checked={Number(rating) === value}
                          onChange={(event) => setRating(event.target.value)}
                          disabled={busy}
                          aria-label={`${value} out of 5`}
                        />
                        {value}
                      </label>
                    ))}
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    1 = not resolved · 5 = fully satisfied
                  </p>
                </fieldset>
                {Number(rating) > 0 && Number(rating) <= 2 && (
                  <Alert>
                    A rating of 1 or 2 will reopen this complaint for another
                    review.
                  </Alert>
                )}
                <Field
                  label="Anything else to share? (optional)"
                  htmlFor="feedback"
                >
                  <textarea
                    id="feedback"
                    className="input"
                    maxLength={2000}
                    rows={3}
                    placeholder="Tell us what went well or what needs more attention…"
                    value={comment}
                    onChange={(event) => setComment(event.target.value)}
                    disabled={busy}
                  />
                </Field>
                <Button type="submit" loading={busy}>
                  Submit feedback
                </Button>
              </form>
            </Card>
          )}
        </div>
        <aside className="space-y-6">
          <Card>
            <div className="panel-heading">
              <h2>At a glance</h2>
              <Icon name="grid" size={17} className="text-slate-400" />
            </div>
            <dl className="space-y-5 p-6">
              {[
                ["Category", complaint.category || "Awaiting classification"],
                [
                  "Priority",
                  <PriorityBadge
                    key="priority"
                    score={complaint.priority_score}
                  />,
                ],
                ["Department", departmentName],
                [
                  "Assigned to",
                  complaint.assigned_to === user?.id
                    ? "You"
                    : complaint.assigned_to
                      ? `Staff #${complaint.assigned_to}`
                      : "Not assigned",
                ],
                ["Escalation level", complaint.escalation_level],
                [
                  "SLA deadline",
                  complaint.sla_deadline
                    ? formatDate(complaint.sla_deadline, { time: true })
                    : "Not set",
                ],
                [
                  "Sentiment",
                  complaint.sentiment_label?.toLowerCase() || "Not analyzed",
                ],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="flex items-start justify-between gap-5 text-xs"
                >
                  <dt className="shrink-0 text-slate-500">{label}</dt>
                  <dd className="text-right font-medium text-slate-700">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
            {isOverdue(complaint) && (
              <div className="px-6 pb-6">
                <Alert variant="error">
                  This open concern is past its SLA deadline.
                </Alert>
              </div>
            )}
          </Card>
          <Card className="p-6">
            <details>
              <summary className="cursor-pointer text-sm font-semibold text-slate-700">
                Understand the priority
              </summary>
              <p className="mt-3 text-xs leading-6 text-slate-500">
                The latest available scoring breakdown is shown below. An
                administrator can adjust the current score separately.
              </p>
              <div className="mt-5 space-y-4">
                {complaint.priority_breakdown?.components?.length ? (
                  [...complaint.priority_breakdown.components]
                    .sort((a, b) => b.contribution - a.contribution)
                    .map((item) => (
                      <div key={item.name}>
                        <div className="flex items-center justify-between gap-3 text-xs">
                          <span className="capitalize text-slate-600">
                            {item.name.replaceAll("_", " ")}
                          </span>
                          <span className="font-medium text-slate-700">
                            {Number(item.contribution).toFixed(2)} pts
                          </span>
                        </div>
                        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full bg-brand-400"
                            style={{
                              width: `${Math.max(0, Math.min(100, item.contribution))}%`,
                            }}
                          />
                        </div>
                        <p className="mt-1.5 text-[10px] text-slate-500">
                          Value {item.raw_value} · Weight{" "}
                          {Math.round(item.weight * 100)}%
                        </p>
                      </div>
                    ))
                ) : (
                  <p className="text-xs text-slate-500">
                    A priority explanation isn’t available yet.
                  </p>
                )}
              </div>
            </details>
          </Card>
          {role === "admin" && (
            <Card className="p-6">
              <Icon name="shield" size={20} className="text-brand-500" />
              <h2 className="mt-3 text-sm font-semibold text-slate-700">
                Administrative controls
              </h2>
              <p className="mt-2 text-xs leading-6 text-slate-500">
                Adjust the department or priority when this concern needs a
                different approach.
              </p>
              {departments.error && (
                <div className="my-3">
                  <Alert variant="error">
                    {departments.error}{" "}
                    <button className="underline" onClick={departments.refresh}>
                      Retry departments
                    </button>
                  </Alert>
                </div>
              )}
              <Button
                variant="secondary"
                className="mt-4"
                onClick={openOverride}
              >
                Edit department & priority
              </Button>
            </Card>
          )}
        </aside>
      </div>
      <Modal
        open={Boolean(pendingStatus)}
        onClose={() => setPendingStatus(null)}
        busy={busy}
        title={
          pendingStatus === "resolved"
            ? "Mark this complaint resolved?"
            : "Reject this complaint?"
        }
        description={
          pendingStatus === "resolved"
            ? "Confirm that the concern has been addressed. The owner can then share feedback."
            : "Rejection closes this complaint. It cannot be moved to another status from this workspace."
        }
        footer={
          <>
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => setPendingStatus(null)}
            >
              Cancel
            </Button>
            <Button
              variant={pendingStatus === "rejected" ? "danger" : "primary"}
              loading={busy}
              onClick={() => changeStatus(pendingStatus)}
            >
              {pendingStatus === "resolved"
                ? "Confirm resolution"
                : "Confirm rejection"}
            </Button>
          </>
        }
      >
        <p className="text-sm font-medium text-slate-700">
          #{complaint.id} · {complaint.title}
        </p>
        {pendingStatus === "resolved" && resolution.trim() && (
          <p className="mt-3 whitespace-pre-wrap text-xs leading-6 text-slate-500">
            {resolution}
          </p>
        )}
        {actionError && (
          <div className="mt-4">
            <Alert variant="error">{actionError}</Alert>
          </div>
        )}
      </Modal>
      <Modal
        open={overrideOpen}
        onClose={() => setOverrideOpen(false)}
        busy={busy}
        title={review ? "Review your changes" : "Edit department & priority"}
        description="These changes replace the current values for this complaint."
        footer={
          review ? (
            <>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => setReview(null)}
              >
                Back
              </Button>
              <Button loading={busy} onClick={confirmOverride}>
                Confirm changes
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="secondary"
                onClick={() => setOverrideOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" form="override-form">
                Review changes
              </Button>
            </>
          )
        }
      >
        {review ? (
          <ul className="space-y-3 text-sm text-slate-600">
            {review.summary.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : (
          <form
            id="override-form"
            onSubmit={reviewOverride}
            className="space-y-5"
          >
            <Field label="Department" htmlFor="override-department">
              <select
                id="override-department"
                className="input"
                value={override.department}
                onChange={(event) =>
                  setOverride((current) => ({
                    ...current,
                    department: event.target.value,
                  }))
                }
                disabled={departments.loading || Boolean(departments.error)}
              >
                <option value="" disabled={complaint.department_id != null}>
                  Not assigned
                </option>
                {complaint.department_id != null &&
                  !departments.data?.some(
                    (item) => item.id === complaint.department_id,
                  ) && (
                    <option value={complaint.department_id}>
                      {departmentName}
                    </option>
                  )}
                {departments.data?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label="Priority score"
              htmlFor="override-priority"
              hint="A score from 0 to 100. Higher scores indicate greater urgency."
            >
              <input
                id="override-priority"
                type="number"
                className="input"
                min={0}
                max={100}
                step="0.01"
                value={override.priority}
                onChange={(event) =>
                  setOverride((current) => ({
                    ...current,
                    priority: event.target.value,
                  }))
                }
              />
            </Field>
          </form>
        )}
        {overrideError && (
          <div className="mt-4">
            <Alert variant="error">{overrideError}</Alert>
          </div>
        )}
      </Modal>
    </div>
  );
}

export default function ComplaintDetail() {
  const { id } = useParams();
  const { role } = useAuth();
  if (!/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id)))
    return (
      <Card>
        <EmptyState
          icon="search"
          title="That complaint ID isn’t valid"
          description="Open a complaint from your workspace to see its details."
          action={
            <Link to={getHomeRouteForRole(role)} className="btn btn-primary">
              Back to workspace
            </Link>
          }
        />
      </Card>
    );
  return <Detail key={id} id={id} />;
}
