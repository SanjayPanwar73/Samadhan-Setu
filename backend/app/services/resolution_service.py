"""Resolution reports and verification (design section 12)."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.timeutil import utcnow
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.issue import Issue
from app.models.resolution_history import ResolutionHistory
from app.models.user import User
from app.models.work import ACTIVE_ASSIGNMENT_STATUSES, Assignment, Attachment, ResolutionReport
from app.services import audit_service, issue_service, notification_service

DEFAULT_REQUIRED = ("what_was_wrong", "action_taken", "public_summary")
REPORT_FIELDS = ("what_was_wrong", "root_cause", "action_taken", "parts_replaced", "notes",
                 "followup_needed", "followup_notes", "public_summary")


def required_fields(category: Category | None) -> tuple[str, ...]:
    schema = (category.resolution_schema or {}) if category else {}
    return tuple(schema.get("required", DEFAULT_REQUIRED))


def submit(db: Session, a: Assignment, staff: User, fields: dict, completed_at: datetime | None) -> ResolutionReport:
    issue = db.query(Issue).filter(Issue.id == a.issue_id).first()
    category = db.query(Category).filter(Category.id == issue.category_id).first()
    if not a.is_lead:
        raise DomainError("not_lead", "Only the lead assignee can submit the resolution", 403)
    if a.status != "in_progress" or issue.status != "in_progress":
        raise DomainError("invalid_transition", "Start the task before submitting a resolution", 409)

    missing = [f for f in required_fields(category) if not str(fields.get(f) or "").strip()]
    if missing:
        raise DomainError("missing_fields", f"Missing required fields: {', '.join(missing)}", 422,
                          {"fields": missing})
    if category and category.requires_evidence:
        n = db.query(Attachment).filter(Attachment.owner_type == "assignment", Attachment.owner_id == a.id).count()
        if n == 0:
            raise DomainError("evidence_required", "This category requires photo/PDF evidence", 422)

    report = ResolutionReport(issue_id=issue.id, assignment_id=a.id, cycle=(issue.reopen_count or 0) + 1,
                              submitted_by=staff.id, completed_at=completed_at or utcnow(),
                              **{k: fields.get(k) for k in REPORT_FIELDS})
    report.followup_needed = bool(fields.get("followup_needed"))
    db.add(report)
    db.flush()
    audit_service.record(db, actor=staff, action="resolution_submitted", entity_type="resolution_report",
                         entity_id=report.id, issue_id=issue.id,
                         after={k: fields.get(k) for k in ("action_taken", "public_summary")})

    if category and category.requires_verification:
        a.status = "awaiting_verification"
        issue_service.transition(db, issue, "awaiting_verification", staff)
        notification_service.emit(db, "resolution_submitted", issue_id=issue.id,
                                  payload={"body": (report.action_taken or "")[:300]})
    else:
        report.status = "approved"
        _finish(db, issue, report, staff, verifier=None)
    return report


def _finish(db: Session, issue: Issue, report: ResolutionReport, actor: User, verifier: User | None) -> None:
    """Shared tail of auto-approval and admin approval."""
    for a in issue_service.active_assignments(db, issue.id):
        a.status, a.completed_at = "completed", utcnow()
    issue_service.transition(db, issue, "resolved", actor)
    first = (db.query(Complaint).filter(Complaint.issue_id == issue.id).order_by(Complaint.id).first())
    if first is not None and report.action_taken:  # feeds the advisory RAG index
        db.add(ResolutionHistory(complaint_id=first.id, resolution_text=report.action_taken,
                                 resolved_by=report.submitted_by))
    notification_service.emit(db, "resolution_approved", issue_id=issue.id,
                              payload={"public_summary": report.public_summary or ""})
    audit_service.record(db, actor=verifier, action="resolution_approved", entity_type="resolution_report",
                         entity_id=report.id, issue_id=issue.id)


def _pending(db: Session, report_id: int) -> tuple[ResolutionReport, Issue]:
    report = db.query(ResolutionReport).filter(ResolutionReport.id == report_id).first()
    if report is None:
        raise DomainError("not_found", "Resolution not found", 404)
    issue = db.query(Issue).filter(Issue.id == report.issue_id).first()
    if report.status != "submitted" or issue.status != "awaiting_verification":
        raise DomainError("invalid_transition", "This resolution is not awaiting verification", 409)
    return report, issue


def approve(db: Session, report_id: int, actor: User, comment: str | None) -> ResolutionReport:
    report, issue = _pending(db, report_id)
    report.status, report.verified_by, report.verified_at = "approved", actor.id, utcnow()
    report.verifier_comment = comment
    _finish(db, issue, report, actor, verifier=actor)
    return report


def reject(db: Session, report_id: int, actor: User, comment: str) -> ResolutionReport:
    if not (comment or "").strip():
        raise DomainError("comment_required", "A comment is required to reject a resolution", 422)
    report, issue = _pending(db, report_id)
    report.status, report.verified_by, report.verified_at = "rejected", actor.id, utcnow()
    report.verifier_comment = comment.strip()
    for a in db.query(Assignment).filter(Assignment.issue_id == issue.id,
                                         Assignment.status == "awaiting_verification"):
        a.status = "in_progress"
    issue_service.transition(db, issue, "in_progress", actor, reason=comment)
    audit_service.record(db, actor=actor, action="resolution_rejected", entity_type="resolution_report",
                         entity_id=report.id, issue_id=issue.id, reason=comment)
    lead = db.query(Assignment).filter(Assignment.id == report.assignment_id).first()
    if lead:
        notification_service.emit(db, "task_assigned", issue_id=issue.id,
                                  payload={"staff_id": lead.staff_id, "assignment_id": lead.id,
                                           "reject_cycle": report.id})
    return report
