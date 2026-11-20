"""SLA deadlines and rule-based escalation (design section 14)."""

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.timeutil import as_utc, utcnow
from app.models.issue import ACTIVE_STATUSES, Issue
from app.models.priority import EscalationEvent, EscalationRule, PriorityAssessment, SlaPolicy
from app.services import audit_service, notification_service

logger = logging.getLogger(__name__)

# band -> (response, resolution, no_progress) in minutes
DEFAULT_SLA = {
    "critical": (30, 8 * 60, 2 * 60),
    "high": (4 * 60, 24 * 60, 8 * 60),
    "medium": (24 * 60, 72 * 60, 24 * 60),
    "low": (48 * 60, 120 * 60, 48 * 60),
}

# (key, trigger, band, after_minutes, repeat_minutes, notify_role)
DEFAULT_ESCALATION_RULES = [
    ("immediate_admin", "immediate", "critical", 0, None, "dept_admin"),
    ("immediate_hod", "immediate", "critical", 0, None, "hod"),
    ("unassigned_crit_15", "unassigned_for", "critical", 15, 15, "dept_admin"),
    ("unassigned_crit_30", "unassigned_for", "critical", 30, 30, "hod"),
    ("unassigned_high_4h", "unassigned_for", "high", 240, 720, "hod"),
    ("noprogress_admin", "no_progress_for", "critical,high", None, None, "dept_admin"),
    ("noprogress_hod", "no_progress_for", "critical,high", None, 480, "hod"),
    ("breach_risk", "sla_breach_risk", "any", None, None, "dept_admin"),
    ("breached_hod", "sla_breached", "any", 0, 1440, "hod"),
    ("breached_super_24h", "sla_breached", "any", 1440, 1440, "super_admin"),
]


def sla_for(db: Session, department_id: int, band: str) -> tuple[int, int, int]:
    row = (db.query(SlaPolicy).filter(SlaPolicy.band == band, SlaPolicy.department_id == department_id).first()
           or db.query(SlaPolicy).filter(SlaPolicy.band == band, SlaPolicy.department_id.is_(None)).first())
    if row:
        return row.response_minutes, row.resolution_minutes, row.no_progress_minutes
    return DEFAULT_SLA.get(band, DEFAULT_SLA["medium"])


def apply_deadlines(db: Session, issue: Issue) -> None:
    """Deadlines anchor to the original report time, so they never reset when priority drops."""
    anchor = as_utc(issue.sla_anchor_at or issue.first_reported_at) or utcnow()
    response, resolution, _ = sla_for(db, issue.department_id, issue.priority_band or "medium")
    issue.sla_response_due_at = anchor + timedelta(minutes=response)
    issue.sla_resolution_due_at = anchor + timedelta(minutes=resolution)


def _rules(db: Session, department_id: int) -> list[dict]:
    rows = db.query(EscalationRule).filter(EscalationRule.is_active.is_(True)).all()
    if not rows:
        return [{"id": None, "key": k, "trigger": t, "band": b, "after": a, "repeat": r, "role": role}
                for k, t, b, a, r, role in DEFAULT_ESCALATION_RULES]
    dept = [r for r in rows if r.department_id == department_id]
    chosen = dept or [r for r in rows if r.department_id is None]  # department rules override global
    return [{"id": r.id, "key": f"rule{r.id}", "trigger": r.trigger, "band": r.band,
             "after": r.after_minutes, "repeat": r.repeat_minutes, "role": r.notify_role} for r in chosen]


def _band_matches(rule_band: str, band: str | None) -> bool:
    return rule_band == "any" or (band or "medium") in rule_band.split(",")


def _minutes(since, now) -> float:
    return (now - as_utc(since)).total_seconds() / 60 if since else 0.0


def _triggered(db: Session, issue: Issue, rule: dict, now) -> str | None:
    """Returns a human-readable reason when the rule fires for this issue, else None."""
    trig, band = rule["trigger"], issue.priority_band
    assigned = _has_active_assignment(db, issue.id)
    _, resolution, no_progress = sla_for(db, issue.department_id, band or "medium")
    after = rule["after"]

    if trig == "immediate":
        cur = (db.query(PriorityAssessment).filter(PriorityAssessment.issue_id == issue.id,
                                                   PriorityAssessment.is_current.is_(True)).first())
        if cur and any(c.startswith("SAFETY_") for c in (cur.reason_codes or [])):
            return "Critical safety issue reported"
    elif trig == "unassigned_for" and issue.status in ("open", "reopened") and not assigned:
        anchor = issue.first_reported_at if not issue.reopen_count else issue.last_progress_at
        waited = _minutes(anchor, now)
        if waited >= (after or 0):
            return f"Unassigned for {int(waited)} minutes"
    elif trig == "no_progress_for" and issue.status in ("assigned", "in_progress"):
        idle = _minutes(issue.last_progress_at or issue.first_reported_at, now)
        if idle >= (after if after is not None else no_progress):
            return f"No progress for {int(idle)} minutes"
    elif trig == "sla_breach_risk" and issue.sla_resolution_due_at and issue.first_reported_at:
        start = as_utc(issue.sla_anchor_at or issue.first_reported_at)
        total = (as_utc(issue.sla_resolution_due_at) - start).total_seconds()
        used = (now - start).total_seconds()
        if total > 0 and 0.8 <= used / total and now < as_utc(issue.sla_resolution_due_at):
            return "80% of the resolution SLA has been used"
    elif trig == "sla_breached" and issue.sla_resolution_due_at:
        late = _minutes(issue.sla_resolution_due_at, now)
        if late >= (after or 0) and now >= as_utc(issue.sla_resolution_due_at):
            return "Resolution SLA breached"
    return None


def _has_active_assignment(db: Session, issue_id: int) -> bool:
    from app.services.issue_service import active_assignments

    return bool(active_assignments(db, issue_id))


def run_issue_escalations(db: Session) -> int:
    """Evaluate every active issue; fire each rule once per repeat window. Returns events written."""
    now = utcnow()
    fired = 0
    for issue in db.query(Issue).filter(Issue.status.in_(ACTIVE_STATUSES)).all():
        for rule in _rules(db, issue.department_id):
            if not _band_matches(rule["band"], issue.priority_band):
                continue
            reason = _triggered(db, issue, rule, now)
            if not reason:
                continue
            key = f"{rule['key']}#{issue.reopen_count or 0}"  # a reopen starts a fresh cycle
            last = (db.query(EscalationEvent).filter(EscalationEvent.issue_id == issue.id,
                                                     EscalationEvent.rule_key == key)
                    .order_by(EscalationEvent.id.desc()).first())
            if last is not None and (rule["repeat"] is None or _minutes(last.created_at, now) < rule["repeat"]):
                continue
            recipients = notification_service.role_recipients(db, rule["role"], issue.department_id)
            issue.escalation_level = (issue.escalation_level or 0) + 1
            issue.last_escalated_at = now
            db.add(EscalationEvent(issue_id=issue.id, rule_id=rule["id"], rule_key=key,
                                   level=issue.escalation_level, recipient_ids=recipients, reason=reason))
            audit_service.record(db, actor=None, action="escalated", entity_type="issue", entity_id=issue.id,
                                 issue_id=issue.id, after={"level": issue.escalation_level, "rule": rule["key"],
                                                           "recipients": recipients}, reason=reason)
            notification_service.emit(db, "escalated", issue_id=issue.id,
                                      payload={"reason": reason, "level": issue.escalation_level,
                                               "rule": rule["key"], "recipient_ids": recipients})
            fired += 1
    db.commit()
    return fired
