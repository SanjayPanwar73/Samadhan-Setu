export const BAND_TONES = {
  critical: "red",
  high: "orange",
  medium: "amber",
  low: "neutral",
};

export const ISSUE_STATUS_LABELS = {
  open: "Open",
  assigned: "Assigned",
  in_progress: "In progress",
  awaiting_verification: "Awaiting verification",
  resolved: "Resolved",
  closed: "Closed",
  reopened: "Reopened",
  rejected: "Rejected",
  merged: "Merged",
};

export const ISSUE_STATUS_TONES = {
  open: "amber",
  assigned: "blue",
  in_progress: "blue",
  awaiting_verification: "orange",
  resolved: "green",
  closed: "neutral",
  reopened: "orange",
  rejected: "red",
  merged: "neutral",
};

export const TASK_STATUS_LABELS = {
  assigned: "New",
  acknowledged: "Acknowledged",
  in_progress: "In progress",
  awaiting_verification: "Awaiting verification",
  completed: "Completed",
  reassigned: "Reassigned",
  cancelled: "Cancelled",
};

export const REVIEW_REASONS = {
  possible_duplicate: "Possible duplicate",
  classification_disagreement: "Classification disagreement",
  low_confidence_classification: "Low-confidence classification",
  unclassified_triage: "Unclassified (Triage)",
  embedding_unavailable: "Could not compare with other reports",
  category_mismatch_same_asset: "Different category on the same asset",
  dissent: "Student dissent",
  recurrence_dissent: "Recurred after resolution",
};

export const FACTOR_LABELS = {
  severity: "Severity",
  safety: "Safety / health risk",
  affected_users: "Affected students",
  criticality: "Asset criticality",
  sla_risk: "SLA risk",
  duration: "Time unresolved",
  academic_impact: "Academic impact",
  spread: "Spread",
  recurrence: "Recurrence",
};

export const REASON_CODE_LABELS = {
  SAFETY_FLOOR_APPLIED: "Safety floor applied",
  CRITICAL_GATE_CAPPED: "Capped below Critical (no severity or safety trigger)",
  VOLUME_SATURATED: "Report volume saturated",
  SLA_AT_RISK: "SLA at risk",
  SLA_BREACHED: "SLA breached",
};

export function reasonCodeLabel(code) {
  if (REASON_CODE_LABELS[code]) return REASON_CODE_LABELS[code];
  if (code.startsWith("SAFETY_RULE:"))
    return `Safety rule: ${code.slice(12).replaceAll("_", " ").toLowerCase()}`;
  const match = /^RECURRENCE_(\d+)_IN_90D$/.exec(code);
  if (match) return `${match[1]} earlier issue(s) in the last 90 days`;
  return code;
}

export function statusLabel(status) {
  return ISSUE_STATUS_LABELS[status] || status || "Unknown";
}

export function newRequestId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Builds "?a=1&b=2" from an object, skipping empty values. */
export function toQuery(params) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== "" && value != null && value !== false)
      q.set(key, String(value));
  });
  const text = q.toString();
  return text ? `?${text}` : "";
}

export function minutesUntil(value, now = Date.now()) {
  if (!value) return null;
  return Math.round((new Date(value).getTime() - now) / 60000);
}

export function formatDuration(minutes) {
  const abs = Math.abs(minutes);
  if (abs < 60) return `${abs} min`;
  if (abs < 60 * 48) return `${Math.round(abs / 60)} h`;
  return `${Math.round(abs / 1440)} d`;
}
