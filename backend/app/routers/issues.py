"""Department admin / HOD / super admin issue management."""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import joinedload, Session

from app.core.database import get_db
from app.core.errors import DomainError
from app.core.roles import has_role
from app.core.timeutil import utcnow
from app.deps import Scope, get_scope, require_role
from app.models.audit_event import AuditEvent
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.duplicate_suggestion import DuplicateSuggestion
from app.models.issue import ACTIVE_STATUSES, Issue
from app.models.user import User
from app.models.work import Assignment
from app.routers._common import commit_and_dispatch, get_issue_or_404
from app.schemas.v2 import ClassificationPatch, OverrideIn, ReasonIn
from app.services import audit_service, issue_service, notification_service, priority_service, views

router = APIRouter(tags=["issues"])
READERS = ("dept_admin", "hod", "super_admin")
MANAGERS = ("dept_admin", "super_admin")


@router.get("/issues")
def list_issues(
    status: str | None = Query(None, max_length=30), band: str | None = Query(None, max_length=10),
    category_id: int | None = Query(None, ge=1), location_id: int | None = Query(None, ge=1),
    staff_id: int | None = Query(None, ge=1), escalated: bool | None = None, needs_review: bool | None = None,
    unassigned: bool | None = None, q: str | None = Query(None, max_length=40),
    date_from: datetime | None = None, date_to: datetime | None = None,
    department_id: int | None = Query(None, ge=1),
    offset: int = Query(0, ge=0, le=100_000), limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
    _: User = Depends(require_role(*READERS)),
):
    query = db.query(Issue)
    if not scope.is_global:                       # scope is applied in the query, not after loading
        query = query.filter(Issue.department_id.in_(scope.department_ids))
    if department_id:
        query = query.filter(Issue.department_id == department_id)
    if status:
        query = query.filter(Issue.status == status)
    if band:
        query = query.filter(Issue.priority_band == band)
    if category_id:
        query = query.filter(Issue.category_id == category_id)
    if location_id:
        query = query.filter(Issue.location_id == location_id)
    if escalated is not None:
        query = query.filter(Issue.escalation_level > 0 if escalated else Issue.escalation_level == 0)
    if needs_review is not None:
        query = query.filter(Issue.needs_review.is_(needs_review))
    if q:
        query = query.filter(Issue.ticket_no.ilike(f"%{q.strip()}%"))
    if date_from:
        query = query.filter(Issue.first_reported_at >= date_from)
    if date_to:
        query = query.filter(Issue.first_reported_at <= date_to)
    if staff_id:
        query = query.filter(Issue.id.in_(db.query(Assignment.issue_id).filter(
            Assignment.staff_id == staff_id, Assignment.status.in_(("assigned", "acknowledged", "in_progress")))))
    if unassigned:
        query = query.filter(Issue.status.in_(("open", "reopened")))
    total = query.count()
    rows = (query.options(joinedload(Issue.category), joinedload(Issue.location), joinedload(Issue.asset))
            .order_by(Issue.priority_score.desc().nullslast(), Issue.id.desc())
            .offset(offset).limit(limit).all())
    return {"total": total, "offset": offset, "limit": limit, "items": views.issue_rows(db, rows)}


@router.get("/issues/{issue_id}")
def get_issue(issue_id: int, db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
              _: User = Depends(require_role(*READERS))):
    return views.issue_detail(db, get_issue_or_404(db, scope, issue_id))


@router.get("/issues/{issue_id}/complaints")
def issue_complaints(issue_id: int, db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
                     _: User = Depends(require_role(*MANAGERS))):
    issue = get_issue_or_404(db, scope, issue_id)
    return [views.admin_view(c) for c in views.linked_complaints(db, issue.id)]


@router.get("/issues/{issue_id}/history")
def issue_history(issue_id: int, offset: int = Query(0, ge=0, le=100_000), limit: int = Query(100, ge=1, le=200),
                  db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
                  _: User = Depends(require_role(*READERS))):
    issue = get_issue_or_404(db, scope, issue_id)
    rows = (db.query(AuditEvent).filter(AuditEvent.issue_id == issue.id).order_by(AuditEvent.id)
            .offset(offset).limit(limit).all())
    # Anonymous submitters are never attributed: complaint_submitted rows carry no actor.
    return [{"id": e.id, "at": e.created_at, "action": e.action, "actor_role": e.actor_role,
             "before": e.before, "after": e.after, "reason": e.reason} for e in rows]


@router.patch("/issues/{issue_id}/classification")
def correct_classification(issue_id: int, payload: ClassificationPatch, background: BackgroundTasks,
                           db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
                           actor: User = Depends(require_role(*MANAGERS))):
    issue = get_issue_or_404(db, scope, issue_id)
    if payload.expected_version is not None and payload.expected_version != issue.version:
        raise DomainError("stale_version", "The issue changed since you opened it; reload and retry", 409)
    if issue.status not in ACTIVE_STATUSES:
        raise DomainError("issue_not_active", "Only active issues can be reclassified", 409)
    cat = db.query(Category).filter(Category.id == payload.category_id, Category.is_active.is_(True)).first()
    if cat is None:
        raise HTTPException(422, "Unknown category")
    if not scope.can_access(cat.department_id):
        raise HTTPException(404, "Category not found")
    before = {"department_id": issue.department_id, "category_id": issue.category_id}
    moved = cat.department_id != issue.department_id
    issue.category_id, issue.department_id = cat.id, cat.department_id
    issue.needs_review, issue.needs_review_reason = False, None
    issue.version += 1
    db.query(Complaint).filter(Complaint.issue_id == issue.id).update(
        {"department_id": cat.department_id, "category_id": cat.id, "category": cat.name},
        synchronize_session=False)
    if moved:
        issue_service.cancel_assignments(db, issue, actor, "issue moved to another department")
        if issue.status in ("assigned", "in_progress", "awaiting_verification"):
            issue.status = "open"          # nobody is assigned any more
            issue_service.propagate_status(db, issue)
        issue.sla_anchor_at = utcnow()     # the SLA clock restarts from the move
        notification_service.emit(db, "issue_created", issue_id=issue.id)
    audit_service.record(db, actor=actor, action="classification_corrected", entity_type="issue",
                         entity_id=issue.id, issue_id=issue.id, before=before,
                         after={"department_id": issue.department_id, "category_id": cat.id},
                         reason=payload.reason)
    priority_service.assess(db, issue, trigger="classification_change")
    commit_and_dispatch(db, background)
    return views.issue_detail(db, issue)


@router.post("/issues/{issue_id}/reject")
def reject_issue(issue_id: int, payload: ReasonIn, background: BackgroundTasks, db: Session = Depends(get_db),
                 scope: Scope = Depends(get_scope), actor: User = Depends(require_role(*MANAGERS))):
    issue = get_issue_or_404(db, scope, issue_id)
    issue_service.transition(db, issue, "rejected", actor, reason=payload.reason)
    commit_and_dispatch(db, background)
    return views.issue_rows(db, [issue])[0]


@router.post("/issues/{issue_id}/reopen")
def reopen_issue(issue_id: int, payload: ReasonIn, background: BackgroundTasks, db: Session = Depends(get_db),
                 scope: Scope = Depends(get_scope), actor: User = Depends(require_role(*MANAGERS))):
    issue = get_issue_or_404(db, scope, issue_id)
    issue_service.transition(db, issue, "reopened", actor, reason=payload.reason)
    db.query(Complaint).filter(Complaint.issue_id == issue.id).update({"has_dissent": False},
                                                                      synchronize_session=False)
    issue.needs_review, issue.needs_review_reason = False, None
    commit_and_dispatch(db, background)
    return views.issue_rows(db, [issue])[0]


# ---------------------------------------------------------- duplicate suggestions
@router.get("/issues/{issue_id}/duplicate-suggestions")
def duplicate_suggestions(issue_id: int, db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
                          _: User = Depends(require_role(*MANAGERS))):
    issue = get_issue_or_404(db, scope, issue_id)
    out = []
    for s, provisional_id, ticket_no in (db.query(DuplicateSuggestion, Complaint.issue_id, Issue.ticket_no)
              .join(Complaint, Complaint.id == DuplicateSuggestion.complaint_id)
              .join(Issue, Issue.id == DuplicateSuggestion.candidate_issue_id)
              .filter((Complaint.issue_id == issue.id) | (DuplicateSuggestion.candidate_issue_id == issue.id))
              .order_by(DuplicateSuggestion.id).all()):
        out.append({"id": s.id, "status": s.status, "score": s.score, "breakdown": s.breakdown,
                    "complaint_id": s.complaint_id, "provisional_issue_id": provisional_id,
                    "candidate_issue_id": s.candidate_issue_id, "candidate_ticket_no": ticket_no})
    return out


def _suggestion(db: Session, scope: Scope, suggestion_id: int) -> DuplicateSuggestion:
    s = db.query(DuplicateSuggestion).filter(DuplicateSuggestion.id == suggestion_id).first()
    cand = db.query(Issue).filter(Issue.id == s.candidate_issue_id).first() if s else None
    if s is None or cand is None or not scope.can_access(cand.department_id):
        raise HTTPException(404, "Suggestion not found")
    if s.status != "pending":
        raise DomainError("already_reviewed", f"Suggestion already {s.status}", 409)
    return s


@router.post("/duplicate-suggestions/{suggestion_id}/accept")
def accept_suggestion(suggestion_id: int, background: BackgroundTasks, db: Session = Depends(get_db),
                      scope: Scope = Depends(get_scope), actor: User = Depends(require_role(*MANAGERS))):
    s = _suggestion(db, scope, suggestion_id)
    complaint = db.query(Complaint).filter(Complaint.id == s.complaint_id).first()
    target = db.query(Issue).filter(Issue.id == s.candidate_issue_id).first()
    issue_service.relink(db, complaint, target, actor, "duplicate suggestion accepted", link_type="admin")
    now = utcnow()
    for other in db.query(DuplicateSuggestion).filter(DuplicateSuggestion.complaint_id == s.complaint_id,
                                                      DuplicateSuggestion.status == "pending"):
        other.status = "accepted" if other.id == s.id else "rejected"
        other.reviewed_by, other.reviewed_at = actor.id, now
    audit_service.record(db, actor=actor, action="duplicate_accepted", entity_type="duplicate_suggestion",
                         entity_id=s.id, issue_id=target.id, complaint_id=complaint.id)
    commit_and_dispatch(db, background)
    return {"status": "accepted", "issue_id": target.id}


@router.post("/duplicate-suggestions/{suggestion_id}/reject")
def reject_suggestion(suggestion_id: int, db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
                      actor: User = Depends(require_role(*MANAGERS))):
    s = _suggestion(db, scope, suggestion_id)
    s.status, s.reviewed_by, s.reviewed_at = "rejected", actor.id, utcnow()
    complaint = db.query(Complaint).filter(Complaint.id == s.complaint_id).first()
    still_pending = (db.query(DuplicateSuggestion.id).filter(DuplicateSuggestion.complaint_id == s.complaint_id,
                                                            DuplicateSuggestion.status == "pending",
                                                            DuplicateSuggestion.id != s.id).first())
    provisional = db.query(Issue).filter(Issue.id == complaint.issue_id).first()
    if provisional and not still_pending and provisional.needs_review_reason == "possible_duplicate":
        provisional.needs_review, provisional.needs_review_reason = False, None
    audit_service.record(db, actor=actor, action="duplicate_rejected", entity_type="duplicate_suggestion",
                         entity_id=s.id, issue_id=complaint.issue_id, complaint_id=complaint.id)
    db.commit()
    return {"status": "rejected"}


# --------------------------------------------------------------------- priority
@router.get("/issues/{issue_id}/priority")
def get_priority(issue_id: int, db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
                 _: User = Depends(require_role(*READERS))):
    return views.issue_detail(db, get_issue_or_404(db, scope, issue_id))["priority"]


@router.post("/issues/{issue_id}/priority/override")
def override_priority(issue_id: int, payload: OverrideIn, background: BackgroundTasks,
                      db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
                      actor: User = Depends(require_role(*MANAGERS))):
    issue = get_issue_or_404(db, scope, issue_id)
    priority_service.set_override(db, issue, actor, payload.score, payload.reason, payload.expires_at)
    commit_and_dispatch(db, background)
    return views.issue_detail(db, issue)["priority"]


@router.delete("/issues/{issue_id}/priority/override")
def clear_override(issue_id: int, db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
                   actor: User = Depends(require_role(*MANAGERS))):
    issue = get_issue_or_404(db, scope, issue_id)
    priority_service.clear_override(db, issue, actor)
    db.commit()
    return views.issue_detail(db, issue)["priority"]
