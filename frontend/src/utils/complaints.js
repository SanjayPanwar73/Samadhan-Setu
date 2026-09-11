export const STATUS_OPTIONS = [
  "pending",
  "in_progress",
  "reopened",
  "resolved",
  "rejected",
];

export function formatDate(value, { time = false } = {}) {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(time ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

export function priorityLevel(score) {
  if (score == null || !Number.isFinite(Number(score))) return "unscored";
  if (score >= 90) return "critical";
  if (score >= 70) return "high";
  if (score >= 40) return "medium";
  return "low";
}

export function matchesPriority(score, filter) {
  return filter === "all" || !filter || priorityLevel(score) === filter;
}

export function isOpen(complaint) {
  return ["pending", "in_progress", "reopened"].includes(complaint.status);
}

export function isOverdue(complaint) {
  return (
    isOpen(complaint) &&
    Boolean(complaint.sla_deadline) &&
    new Date(complaint.sla_deadline).getTime() < Date.now()
  );
}
