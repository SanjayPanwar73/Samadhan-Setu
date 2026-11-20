"""Complaint intake pipeline (design section 7.3).

classify -> embed -> safety rules   (outside the DB lock, slow)
BEGIN; lock; group; link/create issue; counts; priority; SLA; audit; outbox; COMMIT
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai import grouping as g
from app.ai.providers import get_providers, safe_classify, safe_embed, safe_sentiment
from app.core.config import settings
from app.core.database import acquire_grouping_lock
from app.core.errors import DomainError
from app.core.timeutil import utcnow
from app.models.asset import Asset
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.complaint_embedding import ComplaintEmbedding
from app.models.department import Department
from app.models.duplicate_suggestion import DuplicateSuggestion
from app.models.issue import Issue
from app.models.issue_link import IssueLink
from app.models.location import Location
from app.models.user import User
from app.services import audit_service, grouping_service, issue_service, notification_service, priority_service
from app.services.privacy import new_anon_code, redact_pii

logger = logging.getLogger(__name__)


@dataclass
class IntakeInput:
    title: str
    description: str
    location_id: int
    department_id: int | None = None      # None = "Not sure"
    category_id: int | None = None        # None = "Not sure"
    asset_id: int | None = None           # None = "I don't know" / no asset
    people_affected: int | None = None
    is_anonymous: bool = False
    location_text: str | None = None
    client_request_id: str | None = None


@dataclass
class IntakeResult:
    complaint: Complaint
    issue: Issue
    outcome: str            # linked | new_issue | possible_duplicate | existing
    pii_redacted: bool = False
    existing: bool = False


@dataclass
class _Prepared:
    data: IntakeInput
    title: str
    description: str
    department_id: int
    category_id: int
    category_name: str
    location_id: int
    location_parent_id: int | None
    asset_id: int | None
    student_category_id: int | None
    ai_category_id: int | None
    ai_confidence: float | None
    disagreement: bool
    needs_review_reason: str | None
    embedding: object
    sentiment: tuple
    pii_redacted: bool
    content_hash: str


def ensure_triage(db: Session) -> tuple[Department, Category]:
    dept = db.query(Department).filter(Department.is_system.is_(True)).first()
    if dept is None:
        dept = Department(name="Triage", code="TRI", is_system=True)
        db.add(dept)
        db.flush()
    cat = db.query(Category).filter(Category.department_id == dept.id, Category.name == "Unclassified").first()
    if cat is None:
        cat = Category(department_id=dept.id, name="Unclassified")
        db.add(cat)
        db.flush()
    db.commit()
    return dept, cat


def _labelled_categories(db: Session, department_id: int | None = None):
    q = (db.query(Category.id, Category.department_id, Category.name, Department.name.label("department"))
         .join(Department, Department.id == Category.department_id)
         .filter(Category.is_active.is_(True), Department.is_active.is_(True), Department.is_system.is_(False)))
    if department_id:
        q = q.filter(Department.id == department_id)
    return {f"{row.department}: {row.name}": row for row in q}


def _prepare(db: Session, student: User, data: IntakeInput) -> _Prepared:
    # --- structural validation ------------------------------------------------
    loc = db.query(Location.id, Location.parent_id).filter(Location.id == data.location_id, Location.is_active.is_(True)).first()
    if loc is None:
        raise DomainError("invalid_location", "Unknown or inactive location", 422)
    asset = None
    if data.asset_id is not None:
        asset = db.query(Asset).filter(Asset.id == data.asset_id, Asset.is_active.is_(True)).first()
        if asset is None or asset.location_id != loc.id:
            raise DomainError("invalid_asset", "Asset does not exist at the selected location", 422)

    chosen_cat = None
    if data.category_id is not None:
        chosen_cat = (db.query(Category.id, Category.name, Category.department_id)
                      .filter(Category.id == data.category_id, Category.is_active.is_(True)).first())
        if chosen_cat is None:
            raise DomainError("invalid_category", "Unknown category", 422)
        if data.department_id is not None and chosen_cat.department_id != data.department_id:
            raise DomainError("invalid_category", "Category does not belong to the department", 422)
    if data.department_id is not None:
        dept = db.query(Department).filter(Department.id == data.department_id, Department.is_active.is_(True),
                                           Department.is_system.is_(False)).first()
        if dept is None:
            raise DomainError("invalid_department", "Unknown department", 422)
    if asset is not None:
        asset_dept = chosen_cat.department_id if chosen_cat else data.department_id
        if asset_dept is not None and asset.department_id != asset_dept:
            raise DomainError("invalid_asset", "Asset belongs to a different department", 422)

    # --- text hygiene -----------------------------------------------------------
    title, t_red = (data.title.strip(), False)
    description, d_red = (data.description.strip(), False)
    if data.is_anonymous:
        extra = [student.enrollment_no, student.email, student.name]
        title, t_red = redact_pii(title, extra)
        description, d_red = redact_pii(description, extra)
    text = f"{title}. {description}"

    # --- AI (outside the lock) ----------------------------------------------------
    scoped = chosen_cat is None and data.department_id is not None
    labels = _labelled_categories(db, data.department_id if scoped else None)
    if scoped and not labels:
        raise DomainError("invalid_department", "Department has no categories", 422)

    # All reads above are validation only. Return the pooled connection while
    # the models run so simultaneous submissions cannot starve other routes.
    db.rollback()
    label, conf = (next(iter(labels)), 1.0) if scoped and len(labels) == 1 else safe_classify(text, list(labels))
    embedding = safe_embed(text)
    sent_label, sent_score = safe_sentiment(text)
    needs_review: str | None = None
    ai_cat_id, ai_conf, disagreement = None, None, False
    dept_id, cat = None, None

    if chosen_cat is not None:
        dept_id, cat = chosen_cat.department_id, chosen_cat
        if label:
            ai_cat_id, ai_conf = labels[label].id, conf
            if ai_cat_id != chosen_cat.id and conf >= settings.CLASSIFY_DISAGREE_CONF:
                disagreement, needs_review = True, "classification_disagreement"
    elif data.department_id is not None:
        label = label or next(iter(labels))
        cat, dept_id = labels[label], data.department_id
        ai_cat_id, ai_conf = cat.id, conf
        if conf < settings.CLASSIFY_MIN_CONF:
            needs_review = "low_confidence_classification"
    else:
        if label and conf >= settings.CLASSIFY_MIN_CONF:
            cat = labels[label]
            dept_id, ai_cat_id, ai_conf = cat.department_id, cat.id, conf
        else:
            tri_dept, tri_cat = ensure_triage(db)
            dept_id, cat = tri_dept.id, tri_cat
            ai_cat_id = labels[label].id if label else None
            ai_conf = conf if label else None
            needs_review = "unclassified_triage"

    if embedding is None:
        needs_review = needs_review or "embedding_unavailable"

    return _Prepared(
        data=data, title=title, description=description, department_id=dept_id, category_id=cat.id,
        category_name=cat.name, location_id=loc.id, location_parent_id=loc.parent_id,
        asset_id=data.asset_id, student_category_id=chosen_cat.id if chosen_cat else None,
        ai_category_id=ai_cat_id, ai_confidence=ai_conf, disagreement=disagreement,
        needs_review_reason=needs_review, embedding=embedding, sentiment=(sent_label, sent_score),
        pii_redacted=t_red or d_red,
        content_hash=hashlib.sha256(text.lower().encode()).hexdigest(),
    )


def _existing(db: Session, student: User, client_request_id: str | None) -> Complaint | None:
    if not client_request_id:
        return None
    return (db.query(Complaint).filter(Complaint.created_by == student.id,
                                       Complaint.client_request_id == client_request_id).first())


def _result_for_existing(db: Session, complaint: Complaint) -> IntakeResult:
    issue = db.query(Issue).filter(Issue.id == complaint.issue_id).first()
    return IntakeResult(complaint, issue, "existing", existing=True)


def _persist(db: Session, student: User, p: _Prepared) -> IntakeResult:
    acquire_grouping_lock(db, p.department_id, p.location_parent_id)

    existing = _existing(db, student, p.data.client_request_id)
    if existing is not None:
        return _result_for_existing(db, existing)

    spec = grouping_service.ComplaintSpec(
        created_by=student.id, department_id=p.department_id, category_id=p.category_id,
        location_id=p.location_id, asset_id=p.asset_id, embedding=p.embedding,
        location_parent_id=p.location_parent_id)
    match = grouping_service.find_match(db, spec)

    if match.outcome == "link":
        prior = (db.query(Complaint).join(IssueLink, IssueLink.complaint_id == Complaint.id)
                 .filter(IssueLink.issue_id == match.issue.id, IssueLink.unlinked_at.is_(None),
                         Complaint.created_by == student.id).first())
        if prior is not None:
            raise DomainError("already_reported", "You have already reported this issue", 409,
                              {"complaint_id": prior.id})

    now = utcnow()
    complaint = Complaint(
        title=p.title, description=p.description, created_by=student.id, created_at=now, updated_at=now,
        people_affected=p.data.people_affected, category=p.category_name,
        department_id=p.department_id, category_id=p.category_id, location_id=p.location_id,
        asset_id=p.asset_id, location_text=p.data.location_text, is_anonymous=p.data.is_anonymous,
        anon_code=new_anon_code() if p.data.is_anonymous else None,
        student_category_id=p.student_category_id, ai_category_id=p.ai_category_id,
        ai_confidence=p.ai_confidence, classification_disagreement=p.disagreement,
        client_request_id=p.data.client_request_id, content_hash=p.content_hash,
        sentiment_label=p.sentiment[0], sentiment_score=p.sentiment[1])
    db.add(complaint)
    db.flush()
    if p.embedding is not None:
        db.add(ComplaintEmbedding(complaint_id=complaint.id, model=get_providers().embedding_model_name or settings.EMBEDDING_MODEL,
                                  dim=int(p.embedding.shape[0]), vector=p.embedding.astype("float32").tobytes()))

    dissent_on = None
    if match.outcome == "link":
        issue, outcome = match.issue, "linked"
        if match.needs_review_reason and not issue.needs_review:
            issue.needs_review, issue.needs_review_reason = True, match.needs_review_reason
    else:
        dept = db.query(Department).filter(Department.id == p.department_id).first()
        issue = Issue(ticket_no=issue_service.next_ticket_no(db, dept), department_id=p.department_id,
                      category_id=p.category_id, location_id=p.location_id, asset_id=p.asset_id,
                      title=p.title, status="open", first_reported_at=now, last_reported_at=now,
                      last_progress_at=now, recurrence_of_issue_id=match.recurrence_of.id if match.recurrence_of else None)
        reason = p.needs_review_reason or match.needs_review_reason
        if reason:
            issue.needs_review, issue.needs_review_reason = True, reason
        db.add(issue)
        db.flush()
        outcome = "possible_duplicate" if match.suggestions else "new_issue"
        for cand, score, breakdown in match.suggestions:
            db.add(DuplicateSuggestion(complaint_id=complaint.id, candidate_issue_id=cand.id, score=score,
                                       breakdown=breakdown))
        if match.recurrence_of is not None and grouping_service.in_recurrence_grace(match.recurrence_of):
            dissent_on = match.recurrence_of
            dissent_on.needs_review, dissent_on.needs_review_reason = True, "recurrence_dissent"
            audit_service.record(db, actor=None, action="recurrence_dissent", entity_type="issue",
                                 entity_id=dissent_on.id, issue_id=dissent_on.id, complaint_id=complaint.id,
                                 after={"new_issue_id": issue.id})

    issue_service.link_complaint(db, complaint, issue, link_type="auto", score=match.score,
                                 breakdown=match.breakdown, algorithm_version=g.ALGORITHM_VERSION)
    issue_service.recompute_counts(db, issue)
    issue_service.refresh_summary(db, issue)
    if p.disagreement and not issue.needs_review:
        issue.needs_review, issue.needs_review_reason = True, "classification_disagreement"
    priority_service.assess(db, issue, trigger="complaint_linked" if outcome == "linked" else "issue_created")
    if dissent_on is not None:   # counted only now that the new report is linked
        db.flush()
        _maybe_reopen_after_dissent(db, dissent_on)

    audit_service.record(db, actor=student if not p.data.is_anonymous else None,
                         action="complaint_submitted", entity_type="complaint", entity_id=complaint.id,
                         issue_id=issue.id, complaint_id=complaint.id,
                         after={"outcome": outcome, "ticket_no": issue.ticket_no, "score": match.score})
    notification_service.emit(db, "complaint_submitted", issue_id=issue.id, complaint_id=complaint.id,
                              payload={"linked": outcome == "linked"})
    if outcome == "linked":
        notification_service.emit(db, "report_linked", issue_id=issue.id, complaint_id=complaint.id)
    else:
        notification_service.emit(db, "issue_created", issue_id=issue.id, complaint_id=complaint.id)
    for _ in match.suggestions:
        notification_service.emit(db, "duplicate_suggested", issue_id=issue.id, complaint_id=complaint.id)
    db.commit()
    return IntakeResult(complaint, issue, outcome, pii_redacted=p.pii_redacted)


def _maybe_reopen_after_dissent(db: Session, issue: Issue) -> None:
    from app.services import feedback_service

    feedback_service.maybe_auto_reopen(db, issue)


def submit_complaint(db: Session, student: User, data: IntakeInput) -> IntakeResult:
    existing = _existing(db, student, data.client_request_id)
    if existing is not None:
        return _result_for_existing(db, existing)

    since = utcnow() - timedelta(hours=24)
    today = db.query(Complaint.id).filter(Complaint.created_by == student.id, Complaint.created_at >= since).count()
    if today >= settings.MAX_COMPLAINTS_PER_DAY:
        raise DomainError("daily_limit", "Daily complaint limit reached", 429)

    prepared = _prepare(db, student, data)
    for attempt in (1, 2):
        try:
            return _persist(db, student, prepared)
        except IntegrityError as exc:
            db.rollback()  # lost a race (e.g. unique active issue per asset); retry sees the winner
            logger.exception("Complaint submission integrity conflict")
            if attempt == 2:
                raise DomainError("conflict", "Could not complete the submission, please retry", 409)
        except DomainError:
            db.rollback()
            raise
    raise DomainError("conflict", "Could not complete the submission, please retry", 409)  # pragma: no cover
