"""Issue lifecycle: state machine, link management, counts, summaries."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.roles import role_value
from app.core.timeutil import utcnow
from app.models.complaint import Complaint, ComplaintStatus
from app.models.issue import ACTIVE_STATUSES, Issue
from app.models.issue_link import IssueLink
from app.models.ticket_counter import TicketCounter
from app.models.user import User
from app.models.work import ACTIVE_ASSIGNMENT_STATUSES, Assignment
from app.services import audit_service, notification_service

TRANSITIONS: dict[str, set[str]] = {
    "open": {"assigned", "rejected", "merged"},
    "assigned": {"in_progress", "rejected", "merged"},
    "in_progress": {"awaiting_verification", "resolved", "merged"},
    "awaiting_verification": {"resolved", "in_progress", "merged"},
    "resolved": {"closed", "reopened"},
    "closed": {"reopened"},
    "reopened": {"assigned", "in_progress", "merged"},
    "rejected": set(),
    "merged": set(),
}


def can_transition(frm: str, to: str) -> bool:
    return to in TRANSITIONS.get(frm, set())


def next_ticket_no(db: Session, department) -> str:
    counter = (db.query(TicketCounter).filter(TicketCounter.department_id == department.id)
               .with_for_update().first())
    if counter is None:
        counter = TicketCounter(department_id=department.id, next_value=1)
        db.add(counter)
        db.flush()
    number = counter.next_value
    counter.next_value = number + 1
    return f"{department.code or 'GEN'}-{number:03d}"


def propagate_status(db: Session, issue: Issue) -> None:
    """Sync the student-facing status of every currently linked complaint."""
    db.query(Complaint).filter(Complaint.issue_id == issue.id).update(
        {"status": ComplaintStatus(issue.status)}, synchronize_session=False)


def recompute_counts(db: Session, issue: Issue) -> None:
    """Counts always come from ``issue_links`` (never blind increments), so they cannot drift."""
    count, reporters, first, last = (db.query(func.count(Complaint.id), func.count(func.distinct(Complaint.created_by)),
                                               func.min(Complaint.created_at), func.max(Complaint.created_at))
                                     .join(IssueLink, IssueLink.complaint_id == Complaint.id)
                                     .filter(IssueLink.issue_id == issue.id, IssueLink.unlinked_at.is_(None)).one())
    issue.report_count, issue.distinct_reporter_count = count, reporters
    if count:
        issue.first_reported_at, issue.last_reported_at = first, last
    issue.version = (issue.version or 1) + 1


def link_complaint(db: Session, complaint: Complaint, issue: Issue, *, link_type: str,
                   score: float | None = None, breakdown: dict | None = None,
                   algorithm_version: str | None = None, actor: User | None = None) -> IssueLink:
    link = IssueLink(complaint_id=complaint.id, issue_id=issue.id, link_type=link_type,
                     match_score=score, match_breakdown=breakdown, algorithm_version=algorithm_version,
                     linked_by=actor.id if actor else None, linked_at=utcnow())
    db.add(link)
    complaint.issue_id = issue.id
    complaint.status = ComplaintStatus(issue.status)
    db.flush()
    return link


def active_assignments(db: Session, issue_id: int) -> list[Assignment]:
    return db.query(Assignment).filter(Assignment.issue_id == issue_id,
                                       Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES)).all()


def cancel_assignments(db: Session, issue: Issue, actor: User | None, why: str) -> int:
    n = 0
    for a in active_assignments(db, issue.id):
        a.status = "cancelled"
        n += 1
        audit_service.record(db, actor=actor, action="assignment_cancelled", entity_type="assignment",
                             entity_id=a.id, issue_id=issue.id, reason=why)
    return n


def asset_conflict(db: Session, issue: Issue) -> Issue | None:
    """Another active issue already owns this asset (only one active issue per asset)."""
    if issue.asset_id is None:
        return None
    return (db.query(Issue).filter(Issue.asset_id == issue.asset_id, Issue.id != issue.id,
                                   Issue.status.in_(ACTIVE_STATUSES)).first())


def transition(db: Session, issue: Issue, to: str, actor: User | None, *, reason: str | None = None,
               touch_progress: bool = True) -> None:
    """The only place an issue's status changes. Invalid jumps raise a 409 DomainError."""
    frm = issue.status
    if not can_transition(frm, to):
        raise DomainError("invalid_transition", f"Cannot move an issue from '{frm}' to '{to}'", 409,
                          {"from": frm, "to": to})
    if to == "reopened" and asset_conflict(db, issue) is not None:
        raise DomainError("asset_has_active_issue",
                          "Another active issue already exists for this asset; relink instead of reopening", 409)
    now = utcnow()
    issue.status = to
    issue.version = (issue.version or 1) + 1
    if touch_progress:
        issue.last_progress_at = now
    if to == "resolved":
        issue.resolved_at = now
    elif to == "closed":
        issue.closed_at = now
    elif to == "reopened":
        issue.reopen_count = (issue.reopen_count or 0) + 1
        issue.resolved_at = None
        issue.closed_at = None
    if to in ("rejected", "merged"):
        cancel_assignments(db, issue, actor, f"issue {to}")
    propagate_status(db, issue)
    audit_service.record(db, actor=actor, action="status_changed", entity_type="issue", entity_id=issue.id,
                         issue_id=issue.id, before={"status": frm}, after={"status": to}, reason=reason)
    if to == "reopened":
        notification_service.emit(db, "issue_reopened", issue_id=issue.id)
    elif to != "resolved":  # resolution_approved is emitted by the resolution service
        notification_service.emit(db, "issue_status_changed", issue_id=issue.id, payload={"status": to})
    if to in ACTIVE_STATUSES:
        from app.services import priority_service

        priority_service.assess(db, issue, trigger="status_change")


def build_summary(db: Session, issue: Issue, limit: int = 3) -> str:
    """Deterministic, identity-free summary (design 8.9)."""
    from app.models.asset import Asset
    from app.models.category import Category
    from app.models.location import Location
    from app.services.privacy import redact_pii

    cat = db.query(Category).filter(Category.id == issue.category_id).first()
    loc = db.query(Location).filter(Location.id == issue.location_id).first()
    asset = db.query(Asset).filter(Asset.id == issue.asset_id).first() if issue.asset_id else None
    head = f"{cat.name if cat else 'Issue'} at {loc.path if loc else 'unknown location'}"
    if asset:
        head += f" (asset {asset.tag})"
    head += f". {issue.report_count} report(s) from {issue.distinct_reporter_count} student(s)"
    if issue.first_reported_at:
        head += f", first reported {issue.first_reported_at:%Y-%m-%d}"
    head += "."
    samples = (db.query(Complaint.description).join(IssueLink, IssueLink.complaint_id == Complaint.id)
               .filter(IssueLink.issue_id == issue.id, IssueLink.unlinked_at.is_(None))
               .order_by(Complaint.created_at).limit(limit).all())
    parts = [redact_pii(d[0])[0][:200] for d in samples]
    return head + ("\nSamples: " + " | ".join(parts) if parts else "")


def refresh_summary(db: Session, issue: Issue) -> None:
    issue.summary = build_summary(db, issue)


def relink(db: Session, complaint: Complaint, target: Issue, actor: User, reason: str,
           link_type: str = "relink") -> Issue:
    """Move a complaint to another issue of the same department; both issues are recomputed."""
    if target.department_id != complaint.department_id:
        raise DomainError("cross_department", "Target issue belongs to another department", 409)
    if target.status not in ACTIVE_STATUSES:
        raise DomainError("target_not_active", "Target issue is not active", 409)
    if complaint.issue_id == target.id:
        raise DomainError("already_linked", "Complaint is already linked to that issue", 409)

    source = db.query(Issue).filter(Issue.id == complaint.issue_id).first()
    now = utcnow()
    current = (db.query(IssueLink).filter(IssueLink.complaint_id == complaint.id,
                                          IssueLink.unlinked_at.is_(None)).first())
    if current:
        current.unlinked_at = now
        current.unlink_reason = reason
        db.flush()
    link_complaint(db, complaint, target, link_type=link_type, actor=actor)
    recompute_counts(db, target)
    refresh_summary(db, target)
    audit_service.record(db, actor=actor, action="complaint_relinked", entity_type="complaint",
                         entity_id=complaint.id, issue_id=target.id, complaint_id=complaint.id,
                         before={"issue_id": source.id if source else None}, after={"issue_id": target.id},
                         reason=reason)
    from app.services import priority_service

    priority_service.assess(db, target, trigger="relink")
    if source is not None:
        recompute_counts(db, source)
        if source.report_count == 0:
            source.merged_into_id = target.id
            if can_transition(source.status, "merged"):
                transition(db, source, "merged", actor, reason="emptied by relink", touch_progress=False)
        else:
            refresh_summary(db, source)
            priority_service.assess(db, source, trigger="relink")
    return target


def actor_label(actor: User | None) -> str:
    return role_value(actor.role) if actor else "system"
