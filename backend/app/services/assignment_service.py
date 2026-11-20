"""Assignment and task lifecycle (design section 11)."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.timeutil import utcnow
from app.models.issue import Issue
from app.models.user import User
from app.models.work import ACTIVE_ASSIGNMENT_STATUSES, Assignment, TaskUpdate
from app.policies import assert_assignable_staff
from app.services import audit_service, issue_service, notification_service, sla_service

ASSIGNABLE_ISSUE_STATUSES = ("open", "assigned", "in_progress", "reopened")


def assign(db: Session, issue: Issue, actor: User, staff_ids: list[int], *, task_description: str | None,
           due_at: datetime | None, lead_staff_id: int | None = None) -> list[Assignment]:
    if issue.status not in ASSIGNABLE_ISSUE_STATUSES:
        raise DomainError("issue_not_assignable", f"Cannot assign an issue that is {issue.status}", 409)
    if not staff_ids:
        raise DomainError("no_staff", "Select at least one staff member", 422)
    staff_ids = list(dict.fromkeys(staff_ids))
    if lead_staff_id is not None and lead_staff_id not in staff_ids:
        raise DomainError("invalid_lead", "The lead must be one of the selected staff", 422)

    for sid in staff_ids:  # validate everyone first so a bad id leaves no partial state
        assert_assignable_staff(db, sid, issue.department_id)

    current = issue_service.active_assignments(db, issue.id)
    has_lead = any(a.is_lead for a in current)
    by_staff = {a.staff_id: a for a in current}
    if due_at is None:
        due_at = issue.sla_resolution_due_at
    result = []
    for sid in staff_ids:
        if sid in by_staff:                      # repeat call is a no-op
            result.append(by_staff[sid])
            continue
        is_lead = (sid == lead_staff_id) if lead_staff_id is not None else (not has_lead and not result_has_lead(result))
        if is_lead and has_lead:                  # a new explicit lead replaces the old one
            for a in current:
                a.is_lead = False
            has_lead = False
        a = Assignment(issue_id=issue.id, staff_id=sid, assigned_by=actor.id, is_lead=is_lead,
                       task_description=task_description, due_at=due_at,
                       priority_at_assignment=issue.priority_band, status="assigned")
        db.add(a)
        db.flush()
        has_lead = has_lead or is_lead
        result.append(a)
        audit_service.record(db, actor=actor, action="assignment_created", entity_type="assignment",
                             entity_id=a.id, issue_id=issue.id, after={"staff_id": sid, "is_lead": is_lead})
        notification_service.emit(db, "task_assigned", issue_id=issue.id,
                                  payload={"staff_id": sid, "assignment_id": a.id})

    if issue.status in ("open", "reopened"):
        issue_service.transition(db, issue, "assigned", actor)
    else:
        issue.last_progress_at = utcnow()
    return result


def result_has_lead(items: list[Assignment]) -> bool:
    return any(a.is_lead for a in items)


def get_task(db: Session, assignment_id: int, staff: User) -> Assignment:
    a = db.query(Assignment).filter(Assignment.id == assignment_id, Assignment.staff_id == staff.id).first()
    if a is None:
        raise DomainError("not_found", "Task not found", 404)   # never reveal other staff's tasks
    return a


def acknowledge(db: Session, a: Assignment, staff: User) -> Assignment:
    if a.status != "assigned":
        raise DomainError("invalid_transition", f"Task is {a.status}", 409)
    a.status, a.acknowledged_at = "acknowledged", utcnow()
    audit_service.record(db, actor=staff, action="task_acknowledged", entity_type="assignment",
                         entity_id=a.id, issue_id=a.issue_id)
    return a


def start(db: Session, a: Assignment, staff: User) -> Assignment:
    if a.status != "acknowledged":
        raise DomainError("invalid_transition", "Acknowledge the task before starting it", 409)
    a.status, a.started_at = "in_progress", utcnow()
    issue = db.query(Issue).filter(Issue.id == a.issue_id).first()
    if issue.status in ("assigned", "reopened"):
        issue_service.transition(db, issue, "in_progress", staff)
    else:
        issue.last_progress_at = utcnow()
    audit_service.record(db, actor=staff, action="task_started", entity_type="assignment",
                         entity_id=a.id, issue_id=a.issue_id)
    return a


def add_update(db: Session, a: Assignment, staff: User, kind: str, body: str) -> TaskUpdate:
    if kind not in ("progress", "blocker", "note"):
        raise DomainError("invalid_kind", "kind must be progress, blocker or note", 422)
    if a.status not in ACTIVE_ASSIGNMENT_STATUSES:
        raise DomainError("task_closed", "This task is no longer active", 409)
    u = TaskUpdate(assignment_id=a.id, issue_id=a.issue_id, kind=kind, body=body.strip(), created_by=staff.id)
    db.add(u)
    issue = db.query(Issue).filter(Issue.id == a.issue_id).first()
    issue.last_progress_at = utcnow()
    audit_service.record(db, actor=staff, action=f"task_{kind}", entity_type="assignment", entity_id=a.id,
                         issue_id=a.issue_id)
    notification_service.emit(db, "blocker_reported" if kind == "blocker" else "task_updated",
                              issue_id=a.issue_id, payload={"body": body.strip()[:300]})
    db.flush()
    return u


def request_reassignment(db: Session, a: Assignment, staff: User, reason: str) -> Assignment:
    if a.status not in ACTIVE_ASSIGNMENT_STATUSES:
        raise DomainError("task_closed", "This task is no longer active", 409)
    a.reassign_requested, a.reassign_reason = True, reason.strip()
    db.add(TaskUpdate(assignment_id=a.id, issue_id=a.issue_id, kind="reassignment_request",
                      body=reason.strip(), created_by=staff.id))
    audit_service.record(db, actor=staff, action="reassignment_requested", entity_type="assignment",
                         entity_id=a.id, issue_id=a.issue_id, reason=reason)
    notification_service.emit(db, "reassignment_requested", issue_id=a.issue_id, payload={"body": reason[:300]})
    return a


def reassign(db: Session, a: Assignment, actor: User, *, new_staff_id: int | None, due_at: datetime | None) -> Assignment:
    """Admin action: change the due date and/or hand the task to another staff member."""
    if a.status not in ACTIVE_ASSIGNMENT_STATUSES:
        raise DomainError("task_closed", "Only active tasks can be changed", 409)
    issue = db.query(Issue).filter(Issue.id == a.issue_id).first()
    if due_at is not None:
        a.due_at = due_at
        audit_service.record(db, actor=actor, action="assignment_due_changed", entity_type="assignment",
                             entity_id=a.id, issue_id=issue.id, after={"due_at": due_at.isoformat()})
    if new_staff_id is None or new_staff_id == a.staff_id:
        return a
    assert_assignable_staff(db, new_staff_id, issue.department_id)
    if any(x.staff_id == new_staff_id for x in issue_service.active_assignments(db, issue.id)):
        raise DomainError("already_assigned", "That staff member already has a task on this issue", 409)
    a.status = "reassigned"
    new = Assignment(issue_id=issue.id, staff_id=new_staff_id, assigned_by=actor.id, is_lead=a.is_lead,
                     task_description=a.task_description, due_at=due_at or a.due_at,
                     priority_at_assignment=issue.priority_band, status="assigned")
    db.add(new)
    db.flush()
    issue.last_progress_at = utcnow()
    audit_service.record(db, actor=actor, action="assignment_reassigned", entity_type="assignment",
                         entity_id=a.id, issue_id=issue.id, before={"staff_id": a.staff_id},
                         after={"staff_id": new_staff_id, "new_assignment_id": new.id})
    notification_service.emit(db, "task_assigned", issue_id=issue.id,
                              payload={"staff_id": new_staff_id, "assignment_id": new.id})
    if issue.status == "in_progress" and not any(
            x.status in ("in_progress",) for x in issue_service.active_assignments(db, issue.id)):
        pass  # issue stays in_progress; the new assignee still has to acknowledge and start
    return new
