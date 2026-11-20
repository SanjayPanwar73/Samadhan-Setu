import { Badge } from "./ui";
import Icon from "./Icon";
import {
  BAND_TONES,
  FACTOR_LABELS,
  ISSUE_STATUS_TONES,
  REVIEW_REASONS,
  formatDuration,
  minutesUntil,
  reasonCodeLabel,
  statusLabel,
} from "../utils/issues";

export function BandBadge({ band, score }) {
  if (!band) return <Badge>Unrated</Badge>;
  return (
    <span
      className="priority-badge"
      title={score != null ? `Priority score: ${Number(score).toFixed(1)} / 100` : undefined}
    >
      <span
        className={`priority-bars priority-${BAND_TONES[band] || "neutral"}`}
        aria-hidden="true"
      >
        <i />
        <i />
        <i />
      </span>
      <span className="capitalize">{band}</span>
      {score != null && (
        <span className="priority-score">{Number(score).toFixed(0)}</span>
      )}
    </span>
  );
}

export function IssueStatusBadge({ status }) {
  return (
    <Badge tone={ISSUE_STATUS_TONES[status] || "neutral"}>
      <span className="status-dot" />
      {statusLabel(status)}
    </Badge>
  );
}

/** Shows time left (or overdue) against a deadline. `now` is injectable for tests. */
export function SlaIndicator({ due, active = true, now }) {
  if (!due || !active) return <span className="text-slate-400">—</span>;
  const minutes = minutesUntil(due, now);
  const overdue = minutes < 0;
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs ${overdue ? "font-semibold text-red-700" : minutes < 120 ? "text-amber-700" : "text-slate-600"}`}
    >
      <Icon name="clock" size={12} />
      {overdue ? `${formatDuration(minutes)} overdue` : `${formatDuration(minutes)} left`}
    </span>
  );
}

/** Flags admins need at a glance: possible duplicate, recurrence, dissent, needs review. */
export function IssueFlags({ flags }) {
  if (!flags) return null;
  const items = [];
  if (flags.possible_duplicate)
    items.push(["Possible duplicate", "amber"]);
  if (flags.recurrence) items.push(["Recurrence", "orange"]);
  if (flags.dissent) items.push(["Dissent", "red"]);
  if (flags.needs_review && !flags.possible_duplicate && !flags.dissent)
    items.push([REVIEW_REASONS[flags.review_reason] || "Needs review", "blue"]);
  if (!items.length) return null;
  return (
    <span className="flex flex-wrap gap-1">
      {items.map(([label, tone]) => (
        <Badge key={label} tone={tone}>
          {label}
        </Badge>
      ))}
    </span>
  );
}

/** Factor bars + reason codes explaining a stored priority assessment. */
export function PriorityBreakdown({ assessment }) {
  if (!assessment) return <p className="text-sm text-slate-500">No assessment yet.</p>;
  const rows = Object.entries(assessment.factors || {})
    .filter(([key]) => !key.startsWith("_"))
    .sort((a, b) => b[1].contribution - a[1].contribution);
  return (
    <div>
      <p className="text-sm text-slate-600">
        Score <strong>{Number(assessment.score).toFixed(1)}</strong> ·{" "}
        <span className="capitalize">{assessment.band}</span>
        <span className="ml-2 text-xs text-slate-400">
          {assessment.algorithm_version} · config {assessment.config_version}
        </span>
      </p>
      <ul className="mt-3 space-y-2" aria-label="Priority factors">
        {rows.map(([key, factor]) => (
          <li key={key} className="text-xs">
            <div className="flex justify-between text-slate-600">
              <span>{FACTOR_LABELS[key] || key}</span>
              <span>
                {Number(factor.value).toFixed(2)} × {factor.weight} ={" "}
                <strong>{Number(factor.contribution).toFixed(1)}</strong>
              </span>
            </div>
            <div
              className="mt-1 h-1.5 rounded-full bg-slate-100"
              role="img"
              aria-label={`${FACTOR_LABELS[key] || key}: ${Math.round(factor.value * 100)}%`}
            >
              <div
                className="h-1.5 rounded-full bg-brand-500"
                style={{ width: `${Math.round(factor.value * 100)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
      {assessment.reason_codes?.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {assessment.reason_codes.map((code) => (
            <Badge key={code} tone={code.startsWith("SAFETY") ? "red" : "neutral"}>
              {reasonCodeLabel(code)}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
