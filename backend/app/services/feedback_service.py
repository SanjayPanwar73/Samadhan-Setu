"""Per-student feedback, dissent handling and closing (design section 16)."""

import math
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import DomainError
from app.core.timeutil import as_utc, utcnow
from app.models.complaint import Complaint
from app.models.feedback import Feedback
from app.models.issue import Issue
from app.models.work import ResolutionReport
from app.services import audit_service, issue_service, notification_service


def latest_report(db: Session, issue_id: int) -> ResolutionReport | None:
    return (db.query(ResolutionReport).filter(ResolutionReport.issue_id == issue_id,
                                              ResolutionReport.status == "approved")
            .order_by(ResolutionReport.id.desc()).first())


def dissent_student_ids(db: Session, issue: Issue) -> set[int]:
    """Distinct students who disagree with the current resolution: explicit feedback for this
    cycle plus students whose new report recurred inside the grace window."""
    ids: set[int] = set()
    report = latest_report(db, issue.id)
    if report:
        for f in db.query(Feedback).filter(Feedback.resolution_report_id == report.id,
                                           Feedback.still_unresolved.is_(True)):
            ids.add(f.user_id)
    if issue.resolved_at:
        end = as_utc(issue.resolved_at) + timedelta(hours=settings.RECURRENCE_GRACE_HOURS)
        recurred = (db.query(Complaint.created_by).join(Issue, Issue.id == Complaint.issue_id)
                    .filter(Issue.recurrence_of_issue_id == issue.id,
                            Complaint.created_at >= issue.resolved_at, Complaint.created_at <= end).all())
        ids.update(r[0] for r in recurred)
    return ids


def maybe_auto_reopen(db: Session, issue: Issue) -> bool:
    if issue.status != "resolved":
        return False
    needed = max(settings.DISSENT_MIN_COUNT, math.ceil(settings.DISSENT_RATIO * (issue.distinct_reporter_count or 1)))
    if len(dissent_student_ids(db, issue)) < needed:
        return False
    if issue_service.asset_conflict(db, issue) is not None:
        # A newer active issue owns this asset: leave the decision to the department admin.
        issue.needs_review, issue.needs_review_reason = True, "dissent"
        return False
    issue_service.transition(db, issue, "reopened", None, reason="dissent threshold reached")
    db.query(Complaint).filter(Complaint.issue_id == issue.id).update({"has_dissent": False},
                                                                        synchronize_session=False)
    issue.needs_review, issue.needs_review_reason = False, None
    return True


def submit(db: Session, complaint: Complaint, student, *, rating: int, comment: str | None,
           resolved_for_me: bool, still_unresolved: bool) -> Feedback:
    issue = db.query(Issue).filter(Issue.id == complaint.issue_id).first()
    if issue is None or issue.status != "resolved":
        raise DomainError("feedback_closed", "Feedback is only open while an issue is resolved", 409)
    report = latest_report(db, issue.id)
    if report is None:
        raise DomainError("no_resolution", "There is no approved resolution to give feedback on", 409)
    if db.query(Feedback).filter(Feedback.complaint_id == complaint.id,
                                 Feedback.resolution_report_id == report.id).first():
        raise DomainError("duplicate_feedback", "You already responded for this resolution", 409)

    dissent = still_unresolved or (rating <= 2 and not resolved_for_me)
    fb = Feedback(complaint_id=complaint.id, user_id=student.id, rating=rating, comment=comment,
                  issue_id=issue.id, resolution_report_id=report.id, resolved_for_me=resolved_for_me,
                  still_unresolved=dissent)
    db.add(fb)
    db.flush()
    audit_service.record(db, actor=student if not complaint.is_anonymous else None, action="feedback_submitted",
                         entity_type="feedback", entity_id=fb.id, issue_id=issue.id, complaint_id=complaint.id,
                         after={"rating": rating, "resolved_for_me": resolved_for_me, "dissent": dissent})
    if dissent:
        complaint.has_dissent = True
        issue.needs_review, issue.needs_review_reason = True, "dissent"
        notification_service.emit(db, "feedback_dissent", issue_id=issue.id,
                                  payload={"body": "A student reports the issue is still unresolved."})
        maybe_auto_reopen(db, issue)   # a single dissenting student never reopens it on their own
    return fb


def close_expired(db: Session) -> int:
    """Close resolved issues after the feedback window, or once every complainant responded,
    unless a dissent review is still open."""
    cutoff = utcnow() - timedelta(days=settings.FEEDBACK_WINDOW_DAYS)
    n = 0
    for issue in db.query(Issue).filter(Issue.status == "resolved").all():
        if issue.needs_review and issue.needs_review_reason in ("dissent", "recurrence_dissent"):
            continue
        report = latest_report(db, issue.id)
        responded = 0
        if report:
            responded = db.query(Feedback).filter(Feedback.resolution_report_id == report.id).count()
        expired = issue.resolved_at is not None and as_utc(issue.resolved_at) <= cutoff
        if expired or (report and responded >= (issue.report_count or 0) > 0):
            issue_service.transition(db, issue, "closed", None, reason="feedback window ended", touch_progress=False)
            n += 1
    db.commit()
    return n
