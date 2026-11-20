"""Complaints: student submission, own views, feedback, and department-admin relinking."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import DomainError
from app.core.roles import has_role
from app.deps import Scope, get_current_user, get_scope, require_role
from app.models.audit_event import AuditEvent
from app.models.complaint import Complaint
from app.models.issue import Issue
from app.models.user import User
from app.models.work import Assignment
from app.routers._common import commit_and_dispatch
from app.schemas.v2 import (
    ComplaintAdminView, ComplaintCreate, ComplaintOwnerView, ComplaintStaffView, FeedbackIn, RelinkIn,
)
from app.services import (
    attachment_service, feedback_service, intake_service, issue_service, notification_service, views,
)
from app.services.privacy import STUDENT_STATUS_LABEL, shared_issue_message

router = APIRouter(prefix="/complaints", tags=["complaints"])


def _load(db: Session, complaint_id: int) -> Complaint:
    c = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if c is None:
        raise HTTPException(404, "Complaint not found")
    return c


@router.post("", status_code=201)
def create_complaint(payload: ComplaintCreate, background: BackgroundTasks, db: Session = Depends(get_db),
                     student: User = Depends(require_role("student"))):
    result = intake_service.submit_complaint(db, student, intake_service.IntakeInput(**payload.model_dump()))
    background.add_task(notification_service.dispatch_pending)
    issue, c = result.issue, result.complaint
    return {
        "complaint_id": c.id, "ticket_no": issue.ticket_no, "outcome": result.outcome,
        "status": issue.status, "status_label": STUDENT_STATUS_LABEL.get(issue.status, issue.status),
        "message": shared_issue_message(issue.report_count), "existing": result.existing,
        "pii_redacted": result.pii_redacted,
        "warning": "Personal details were removed from your text." if result.pii_redacted else None,
    }


@router.get("/me", response_model=list[ComplaintOwnerView])
def my_complaints(offset: int = Query(0, ge=0, le=100_000), limit: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db), student: User = Depends(require_role("student"))):
    rows = (views.owner_query(db).filter(Complaint.created_by == student.id)
            .order_by(Complaint.created_at.desc(), Complaint.id.desc()).offset(offset).limit(limit).all())
    return [views.owner_view(row) for row in rows]


@router.get("/{complaint_id}")
def get_complaint(complaint_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user),
                  scope: Scope = Depends(get_scope)):
    if has_role(user, "student"):
        row = views.owner_query(db).filter(Complaint.id == complaint_id, Complaint.created_by == user.id).first()
        if row is None:
            raise HTTPException(404, "Complaint not found")
        return views.owner_view(row)
    c = _load(db, complaint_id)
    if has_role(user, "staff"):
        mine = db.query(Assignment.id).filter(Assignment.staff_id == user.id,
                                              Assignment.issue_id == c.issue_id).first()
        if not mine:
            raise HTTPException(404, "Complaint not found")
        return views.staff_view(c)
    if has_role(user, "dept_admin", "super_admin") and scope.can_access(c.department_id):
        return views.admin_view(c)
    raise HTTPException(404, "Complaint not found")  # HOD sees aggregates only


_SAFE_ACTIONS = {"complaint_submitted", "status_changed", "resolution_approved", "complaint_relinked"}


@router.get("/{complaint_id}/timeline")
def timeline(complaint_id: int, db: Session = Depends(get_db),
             student: User = Depends(require_role("student"))):
    c = _load(db, complaint_id)
    if c.created_by != student.id:
        raise HTTPException(404, "Complaint not found")
    q = db.query(AuditEvent).filter(AuditEvent.action.in_(_SAFE_ACTIONS))
    if c.issue_id:
        q = q.filter((AuditEvent.complaint_id == c.id) | (AuditEvent.issue_id == c.issue_id))
    else:
        q = q.filter(AuditEvent.complaint_id == c.id)
    events = []
    for e in q.order_by(AuditEvent.id).all():
        if e.action == "complaint_submitted" and e.complaint_id != c.id:
            continue  # other students' submissions are never part of my timeline
        status = (e.after or {}).get("status")
        label = {"complaint_submitted": "Complaint received", "resolution_approved": "Resolution approved",
                 "complaint_relinked": "Linked to a shared issue"}.get(e.action) \
            or STUDENT_STATUS_LABEL.get(status, status or "Updated")
        events.append({"at": e.created_at, "label": label})
    return events


@router.post("/{complaint_id}/attachments", status_code=201)
async def upload_attachment(complaint_id: int, file: UploadFile = File(...), kind: str = Form("evidence"),
                            db: Session = Depends(get_db), student: User = Depends(require_role("student"))):
    c = _load(db, complaint_id)
    if c.created_by != student.id:
        raise HTTPException(404, "Complaint not found")
    att = await attachment_service.save_upload(db, file, owner_type="complaint", owner_id=c.id, kind=kind,
                                               user=student, issue_id=c.issue_id)
    db.commit()
    return {"id": att.id, "mime": att.mime, "size_bytes": att.size_bytes}


@router.post("/{complaint_id}/feedback", status_code=201)
def give_feedback(complaint_id: int, payload: FeedbackIn, background: BackgroundTasks,
                  db: Session = Depends(get_db), student: User = Depends(require_role("student"))):
    c = _load(db, complaint_id)
    if c.created_by != student.id:
        raise HTTPException(404, "Complaint not found")
    fb = feedback_service.submit(db, c, student, rating=payload.rating, comment=payload.comment,
                                 resolved_for_me=payload.resolved_for_me,
                                 still_unresolved=payload.still_unresolved)
    commit_and_dispatch(db, background)
    return {"id": fb.id, "recorded": True, "dissent": bool(fb.still_unresolved)}


@router.post("/{complaint_id}/relink")
def relink_complaint(complaint_id: int, payload: RelinkIn, background: BackgroundTasks,
                     db: Session = Depends(get_db), actor: User = Depends(require_role("dept_admin", "super_admin")),
                     scope: Scope = Depends(get_scope)):
    c = _load(db, complaint_id)
    if not scope.can_access(c.department_id):
        raise HTTPException(404, "Complaint not found")
    target = db.query(Issue).filter(Issue.id == payload.issue_id).first()
    if target is None or not scope.can_access(target.department_id):
        raise HTTPException(404, "Issue not found")
    issue_service.relink(db, c, target, actor, payload.reason)
    commit_and_dispatch(db, background)
    return {"complaint_id": c.id, "issue_id": target.id, "ticket_no": target.ticket_no}
