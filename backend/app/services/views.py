"""Builders that turn ORM rows into the role-specific views."""

from collections import defaultdict

from sqlalchemy import and_, func, select
from sqlalchemy.orm import joinedload, Session

from app.models.asset import Asset
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.duplicate_suggestion import DuplicateSuggestion
from app.models.feedback import Feedback
from app.models.issue import ACTIVE_STATUSES, Issue
from app.models.issue_link import IssueLink
from app.models.location import Location
from app.models.user import User
from app.models.work import ACTIVE_ASSIGNMENT_STATUSES, Assignment, ResolutionReport
from app.core.timeutil import as_utc, utcnow
from app.schemas.v2 import ComplaintAdminView, ComplaintOwnerView, ComplaintStaffView
from app.services import priority_service
from app.services.privacy import STUDENT_STATUS_LABEL, shared_issue_message


def _status(c: Complaint) -> str:
    return c.status.value if hasattr(c.status, "value") else str(c.status)


def owner_query(db: Session):
    latest = (select(func.max(ResolutionReport.id))
              .where(ResolutionReport.issue_id == Issue.id, ResolutionReport.status == "approved")
              .correlate(Issue).scalar_subquery())
    return (db.query(Complaint, Issue.ticket_no, Issue.status.label("issue_status"), Issue.report_count,
                     Department.name.label("department"), Category.name.label("category"), Location.path,
                     Asset.name.label("asset"), ResolutionReport.id.label("report_id"),
                     ResolutionReport.public_summary, Feedback.id.label("feedback_id"))
            .select_from(Complaint)
            .outerjoin(Issue, Issue.id == Complaint.issue_id)
            .outerjoin(Department, Department.id == Complaint.department_id)
            .outerjoin(Category, Category.id == Complaint.category_id)
            .outerjoin(Location, Location.id == Complaint.location_id)
            .outerjoin(Asset, Asset.id == Complaint.asset_id)
            .outerjoin(ResolutionReport, and_(Issue.status.in_(("resolved", "closed", "reopened")), ResolutionReport.id == latest))
            .outerjoin(Feedback, and_(Feedback.complaint_id == Complaint.id,
                                      Feedback.resolution_report_id == ResolutionReport.id)))


def owner_view(row) -> ComplaintOwnerView:
    c = row.Complaint
    fb_state = "none"
    if row.report_id is not None:
        fb_state = "submitted" if row.feedback_id is not None else ("pending" if row.issue_status == "resolved" else "none")
    status = _status(c)
    return ComplaintOwnerView(
        id=c.id, ticket_no=row.ticket_no, title=c.title, description=c.description,
        department_name=row.department, category_name=row.category,
        location_path=row.path, asset_name=row.asset,
        is_anonymous=bool(c.is_anonymous), anon_code=c.anon_code, status=status,
        status_label=STUDENT_STATUS_LABEL.get(status, status), created_at=c.created_at,
        shared_message=shared_issue_message(row.report_count or 1),
        resolution_summary=row.public_summary if row.issue_status in ("resolved", "closed") else None,
        feedback_state=fb_state, has_dissent=bool(c.has_dissent))


def admin_view(c: Complaint) -> ComplaintAdminView:
    link = c.current_link
    name = c.creator.name if not c.is_anonymous and c.creator else None
    return ComplaintAdminView(
        id=c.id, title=c.title, description=c.description, created_at=c.created_at,
        is_anonymous=bool(c.is_anonymous), anon_code=c.anon_code, submitter_name=name,
        link_type=link.link_type if link else None, match_score=link.match_score if link else None,
        classification_disagreement=bool(c.classification_disagreement), ai_confidence=c.ai_confidence,
        has_dissent=bool(c.has_dissent))


def staff_view(c: Complaint) -> ComplaintStaffView:
    return ComplaintStaffView(id=c.id, title=c.title, description=c.description,
                              location_path=c.location.path if c.location else None,
                              asset_name=c.asset.name if c.asset else None, created_at=c.created_at)


def linked_complaints(db: Session, issue_id: int, limit: int = 200, *, staff=False) -> list[Complaint]:
    related = ((joinedload(Complaint.location), joinedload(Complaint.asset)) if staff else
               (joinedload(Complaint.current_link), joinedload(Complaint.creator).load_only(User.name)))
    return (db.query(Complaint).join(IssueLink, IssueLink.complaint_id == Complaint.id)
            .options(*related)
            .filter(IssueLink.issue_id == issue_id, IssueLink.unlinked_at.is_(None))
            .order_by(Complaint.created_at).limit(limit).all())


def issue_rows(db: Session, issues: list[Issue]) -> list[dict]:
    if not issues:
        return []
    ids = [i.id for i in issues]
    staff = defaultdict(list)
    assignments = (db.query(Assignment.issue_id, User.id, User.name).join(User, User.id == Assignment.staff_id)
                   .filter(Assignment.issue_id.in_(ids), Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES))
                   .distinct().order_by(Assignment.issue_id, User.id))
    for issue_id, _, name in assignments:
        staff[issue_id].append(name)
    pending = {r.issue_id for r in db.query(Complaint.issue_id)
               .join(DuplicateSuggestion, Complaint.id == DuplicateSuggestion.complaint_id)
               .filter(Complaint.issue_id.in_(ids), DuplicateSuggestion.status == "pending").distinct()}
    return [_issue_row(i, staff[i.id], i.id in pending) for i in issues]


def _issue_row(i: Issue, staff: list[str], pending_dup: bool) -> dict:
    due = as_utc(i.sla_resolution_due_at)
    return {
        "id": i.id, "ticket_no": i.ticket_no, "title": i.title, "status": i.status,
        "department_id": i.department_id, "category": i.category.name if i.category else None,
        "location_path": i.location.path if i.location else None, "asset_tag": i.asset.tag if i.asset else None,
        "report_count": i.report_count, "distinct_reporter_count": i.distinct_reporter_count,
        "priority_score": i.priority_score, "priority_band": i.priority_band,
        "assignees": staff, "sla_resolution_due_at": i.sla_resolution_due_at,
        "overdue": bool(due and utcnow() > due and i.status in ACTIVE_STATUSES),
        "escalation_level": i.escalation_level, "first_reported_at": i.first_reported_at,
        "flags": {"possible_duplicate": pending_dup, "recurrence": i.recurrence_of_issue_id is not None,
                  "dissent": i.needs_review_reason in ("dissent", "recurrence_dissent"),
                  "needs_review": bool(i.needs_review), "review_reason": i.needs_review_reason},
    }


def issue_detail(db: Session, i: Issue) -> dict:
    row = issue_rows(db, [i])[0]
    cur = priority_service.current_assessment(db, i.id)
    override = priority_service.active_override(db, i.id)
    row.update({
        "summary": i.summary, "reopen_count": i.reopen_count, "recurrence_of_issue_id": i.recurrence_of_issue_id,
        "merged_into_id": i.merged_into_id, "version": i.version,
        "sla_response_due_at": i.sla_response_due_at, "last_progress_at": i.last_progress_at,
        "resolved_at": i.resolved_at, "needs_review_reason": i.needs_review_reason,
        "priority": {
            "assessment": None if cur is None else {"score": cur.score, "band": cur.band, "factors": cur.factors,
                                                    "reason_codes": cur.reason_codes,
                                                    "algorithm_version": cur.algorithm_version,
                                                    "config_version": cur.config_version},
            "override": None if override is None else {"score": override.score, "band": override.band,
                                                       "reason": override.reason, "expires_at": override.expires_at},
        },
    })
    return row
