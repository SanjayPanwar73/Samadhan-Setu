"""Transactional outbox + in-app notifications.

Domain code calls ``emit`` inside its own transaction. After commit, ``dispatch_pending``
turns pending events into notification rows. Dispatch failures never touch the
originating change (design section 15)."""

import logging
from collections.abc import Callable
from threading import Lock

from sqlalchemy.orm import Session

from app.core.timeutil import utcnow
from app.models.complaint import Complaint
from app.models.department_membership import DepartmentMembership
from app.models.events import DomainEvent, Notification
from app.models.issue import Issue
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5
_sweep_lock = Lock()

# Only these keys may ever appear in a stored notification payload.
ALLOWED_PAYLOAD_KEYS = {
    "ticket_no", "status", "complaint_id", "issue_id", "public_summary", "count",
    "band", "reason", "rule", "level", "linked", "cycle", "assignment_id",
}


def safe_payload(data: dict | None) -> dict:
    return {k: v for k, v in (data or {}).items() if k in ALLOWED_PAYLOAD_KEYS}


def emit(db: Session, event_type: str, *, issue_id: int | None = None,
         complaint_id: int | None = None, payload: dict | None = None) -> DomainEvent:
    event = DomainEvent(event_type=event_type, issue_id=issue_id, complaint_id=complaint_id,
                        payload=payload or {})
    db.add(event)
    return event


# ------------------------------------------------------------------ recipients
def _role_ids(db: Session, role: UserRole, department_id: int | None) -> list[int]:
    q = db.query(User.id).filter(User.role == role, User.is_active.is_(True))
    if role != UserRole.super_admin:
        q = q.join(DepartmentMembership, DepartmentMembership.user_id == User.id).filter(
            DepartmentMembership.department_id == department_id)
    return [r[0] for r in q.all()]


def dept_admin_ids(db: Session, department_id: int) -> list[int]:
    return _role_ids(db, UserRole.dept_admin, department_id)


def hod_ids(db: Session, department_id: int) -> list[int]:
    return _role_ids(db, UserRole.hod, department_id)


def super_admin_ids(db: Session) -> list[int]:
    return _role_ids(db, UserRole.super_admin, None)


def role_recipients(db: Session, role: str, department_id: int) -> list[int]:
    if role == "dept_admin":
        return dept_admin_ids(db, department_id)
    if role == "hod":
        return hod_ids(db, department_id)
    if role == "super_admin":
        return super_admin_ids(db)
    return []


# --------------------------------------------------------------------- builders
def _n(recipient_id, type_, title, body, *, issue=None, complaint_id=None, payload=None,
       dedupe_key, group_key=None):
    return {
        "recipient_id": recipient_id, "type": type_, "title": title, "body": body,
        "issue_id": issue.id if issue else None, "complaint_id": complaint_id,
        "payload": safe_payload({**(payload or {}), "ticket_no": issue.ticket_no if issue else None}),
        "dedupe_key": dedupe_key, "group_key": group_key,
    }


def _issue(db, event) -> Issue | None:
    return db.query(Issue).filter(Issue.id == event.issue_id).first() if event.issue_id else None


def _complainants(db, issue) -> list[Complaint]:
    return db.query(Complaint).filter(Complaint.issue_id == issue.id).all()


def _h_complaint_submitted(db, ev):
    issue = _issue(db, ev)
    c = db.query(Complaint).filter(Complaint.id == ev.complaint_id).first()
    if not (issue and c):
        return []
    linked = bool((ev.payload or {}).get("linked"))
    body = (f"Your complaint #{c.id} was linked to existing issue {issue.ticket_no}."
            if linked else f"Your complaint #{c.id} was registered as issue {issue.ticket_no}.")
    return [_n(c.created_by, "complaint_submitted", f"Complaint #{c.id} received", body, issue=issue,
               complaint_id=c.id, payload={"complaint_id": c.id, "linked": linked},
               dedupe_key=f"submitted:{c.id}")]


def _h_issue_created(db, ev):
    issue = _issue(db, ev)
    if not issue:
        return []
    return [_n(uid, "issue_created", f"New issue {issue.ticket_no}",
               f"{issue.title} ({issue.priority_band or 'unrated'} priority)", issue=issue,
               payload={"band": issue.priority_band}, dedupe_key=f"issue_created:{issue.id}:{uid}")
            for uid in dept_admin_ids(db, issue.department_id)]


def _h_report_linked(db, ev):
    issue = _issue(db, ev)
    if not issue:
        return []
    urgent = issue.priority_band in ("critical", "high")
    out = []
    for uid in dept_admin_ids(db, issue.department_id):
        body = f"{issue.ticket_no} now has {issue.report_count} reports"
        if urgent:  # urgent issues always raise a fresh alert
            out.append(_n(uid, "report_linked", f"{issue.priority_band.title()} issue updated", body,
                          issue=issue, payload={"count": issue.report_count, "band": issue.priority_band},
                          dedupe_key=f"linked:{issue.id}:{issue.report_count}:{uid}"))
        else:  # routine issues are grouped into one notification per issue
            out.append(_n(uid, "report_linked", f"{issue.ticket_no} has new reports", body, issue=issue,
                          payload={"count": issue.report_count}, dedupe_key=f"linked-group:{issue.id}:{uid}:{ev.id}",
                          group_key=f"linked:{issue.id}"))
    return out


def _h_duplicate_suggested(db, ev):
    issue = _issue(db, ev)
    if not issue:
        return []
    return [_n(uid, "duplicate_suggested", "Possible duplicate",
               f"A new report may belong to {issue.ticket_no}. Please review.", issue=issue,
               dedupe_key=f"dup:{ev.id}:{uid}") for uid in dept_admin_ids(db, issue.department_id)]


def _h_task_assigned(db, ev):
    issue = _issue(db, ev)
    staff_id = (ev.payload or {}).get("staff_id")
    if not (issue and staff_id):
        return []
    return [_n(staff_id, "task_assigned", f"New task {issue.ticket_no}", issue.title, issue=issue,
               payload={"assignment_id": (ev.payload or {}).get("assignment_id")},
               dedupe_key=f"assigned:{(ev.payload or {}).get('assignment_id')}")]


def _admins(db, ev, type_, title, body_key="body"):
    issue = _issue(db, ev)
    if not issue:
        return []
    body = (ev.payload or {}).get(body_key) or issue.title
    return [_n(uid, type_, f"{title} — {issue.ticket_no}", body[:300], issue=issue,
               dedupe_key=f"{type_}:{ev.id}:{uid}") for uid in dept_admin_ids(db, issue.department_id)]


def _h_task_updated(db, ev):
    return _admins(db, ev, ev.event_type, "Task update" if ev.event_type == "task_updated" else "Blocker reported")


def _h_reassignment_requested(db, ev):
    return _admins(db, ev, "reassignment_requested", "Reassignment requested")


def _h_resolution_submitted(db, ev):
    return _admins(db, ev, "resolution_submitted", "Resolution awaiting verification")


def _h_feedback_dissent(db, ev):
    return _admins(db, ev, "feedback_dissent", "Student dissent on resolution")


def _h_status_changed(db, ev):
    issue = _issue(db, ev)
    if not issue:
        return []
    from app.services.privacy import STUDENT_STATUS_LABEL

    status = (ev.payload or {}).get("status", issue.status)
    label = STUDENT_STATUS_LABEL.get(status, status)
    return [_n(c.created_by, "issue_status_changed", f"Complaint #{c.id}: {label}",
               f"{issue.ticket_no} is now: {label}.", issue=issue, complaint_id=c.id,
               payload={"complaint_id": c.id, "status": status},
               dedupe_key=f"status:{c.id}:{status}:{issue.reopen_count}")
            for c in _complainants(db, issue)]


def _h_resolution_approved(db, ev):
    issue = _issue(db, ev)
    if not issue:
        return []
    summary = (ev.payload or {}).get("public_summary") or "The issue has been resolved."
    return [_n(c.created_by, "resolution_approved", f"Complaint #{c.id} resolved",
               f"{issue.ticket_no} was resolved. {summary} Please share your feedback.", issue=issue,
               complaint_id=c.id, payload={"complaint_id": c.id, "status": "resolved",
                                           "public_summary": summary},
               dedupe_key=f"status:{c.id}:resolved:{issue.reopen_count}")
            for c in _complainants(db, issue)]


def _h_issue_reopened(db, ev):
    issue = _issue(db, ev)
    if not issue:
        return []
    out = _h_status_changed(db, DomainEvent(event_type="x", issue_id=issue.id, payload={"status": "reopened"}))
    for uid in dept_admin_ids(db, issue.department_id):
        out.append(_n(uid, "issue_reopened", f"{issue.ticket_no} reopened", issue.title, issue=issue,
                      dedupe_key=f"reopened:{issue.id}:{issue.reopen_count}:{uid}"))
    from app.models.work import Assignment, ACTIVE_ASSIGNMENT_STATUSES
    for a in db.query(Assignment).filter(Assignment.issue_id == issue.id,
                                         Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES)):
        out.append(_n(a.staff_id, "issue_reopened", f"{issue.ticket_no} reopened", issue.title, issue=issue,
                      dedupe_key=f"reopened:{issue.id}:{issue.reopen_count}:{a.staff_id}"))
    return out


def _h_escalated(db, ev):
    issue = _issue(db, ev)
    if not issue:
        return []
    p = ev.payload or {}
    return [_n(uid, "escalated", f"Escalation — {issue.ticket_no}", (p.get("reason") or "Escalated")[:300],
               issue=issue, payload={"level": p.get("level"), "rule": p.get("rule")},
               dedupe_key=f"esc:{ev.id}:{uid}") for uid in (p.get("recipient_ids") or [])]


def _h_priority_override(db, ev):
    issue = _issue(db, ev)
    if not issue:
        return []
    reason = (ev.payload or {}).get("reason", "")
    return [_n(uid, "priority_override", f"Priority overridden — {issue.ticket_no}", reason[:300],
               issue=issue, payload={"band": issue.priority_band}, dedupe_key=f"override:{ev.id}:{uid}")
            for uid in hod_ids(db, issue.department_id)]


HANDLERS: dict[str, Callable] = {
    "complaint_submitted": _h_complaint_submitted, "issue_created": _h_issue_created,
    "report_linked": _h_report_linked, "duplicate_suggested": _h_duplicate_suggested,
    "task_assigned": _h_task_assigned, "task_updated": _h_task_updated, "blocker_reported": _h_task_updated,
    "reassignment_requested": _h_reassignment_requested, "resolution_submitted": _h_resolution_submitted,
    "feedback_dissent": _h_feedback_dissent, "issue_status_changed": _h_status_changed,
    "resolution_approved": _h_resolution_approved, "issue_reopened": _h_issue_reopened,
    "escalated": _h_escalated, "priority_override": _h_priority_override,
}


# ----------------------------------------------------------------------- store
def _store(db: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    created = 0
    keys = {(r["recipient_id"], r["dedupe_key"]) for r in rows if not r.get("group_key")}
    existing = set()
    if keys:
        existing = {(n.recipient_id, n.dedupe_key) for n in db.query(Notification).filter(
            Notification.recipient_id.in_({k[0] for k in keys}),
            Notification.dedupe_key.in_({k[1] for k in keys}))}
    for r in rows:
        if r.get("group_key"):
            grouped = (db.query(Notification)
                       .filter(Notification.recipient_id == r["recipient_id"],
                               Notification.group_key == r["group_key"], Notification.is_read.is_(False))
                       .first())
            if grouped:  # upsert: bump the count and refresh the text
                grouped.count += 1
                grouped.body = r["body"]
                grouped.payload = r["payload"]
                grouped.updated_at = utcnow()
                continue
        elif (r["recipient_id"], r["dedupe_key"]) in existing:
            continue  # idempotent retry
        db.add(Notification(**r))
        created += 1
    return created


def process_event(db: Session, event: DomainEvent) -> int:
    handler = HANDLERS.get(event.event_type)
    rows = handler(db, event) if handler else []
    return _store(db, rows)


def dispatch_pending(session_factory=None, limit: int = 200) -> int:
    """Process pending outbox events, one transaction per event. Safe to call repeatedly."""
    # Many actions can finish together. One sweep handles the current batch,
    # and the scheduler picks up events committed after its snapshot.
    if not _sweep_lock.acquire(blocking=False):
        return 0
    try:
        return _dispatch_pending(session_factory, limit)
    finally:
        _sweep_lock.release()


def _dispatch_pending(session_factory, limit: int) -> int:
    from app.core.database import SessionLocal

    db = (session_factory or SessionLocal)()
    done = 0
    try:
        ids = [r[0] for r in db.query(DomainEvent.id).filter(
            DomainEvent.processed_at.is_(None), DomainEvent.attempts < MAX_ATTEMPTS)
            .order_by(DomainEvent.id).limit(limit)]
        for event_id in ids:
            pending = db.query(DomainEvent).filter(DomainEvent.id == event_id, DomainEvent.processed_at.is_(None),
                                                    DomainEvent.attempts < MAX_ATTEMPTS)
            try:
                # Other server processes may have selected the same IDs. Claim
                # the event in the same transaction that stores its notifications.
                if not pending.update({"processed_at": utcnow()}, synchronize_session=False):
                    db.rollback()
                    continue
                process_event(db, db.get(DomainEvent, event_id))
                db.commit()
                done += 1
            except Exception as exc:  # noqa: BLE001 - never let one bad event stop the sweep
                db.rollback()
                logger.exception("notification dispatch failed for event %s", event_id)
                pending.update({"attempts": DomainEvent.attempts + 1, "last_error": str(exc)[:500]},
                               synchronize_session=False)
                db.commit()
        return done
    finally:
        db.close()
