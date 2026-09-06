from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.ai.classifier import classify_complaint
from app.ai.similarity import find_similar, get_index
from app.ai.sentiment import analyze_sentiment
from app.ai.priority import compute_priority
from app.core.config import settings
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.user import User, UserRole
from app.models.complaint_history import ComplaintHistory
from app.schemas.complaint import ComplaintCreate


def _severity_from_sentiment(sentiment: dict) -> float:
    # NEGATIVE sentiment -> high severity, scaled by model confidence.
    # POSITIVE sentiment -> low severity.
    if sentiment["label"] == "NEGATIVE":
        return sentiment["score"]
    return 1.0 - sentiment["score"]


def _count_similar(complaint_id: int, similar_results: list[tuple[int, float]], threshold: float = 1.0) -> int:
    # repeat_count = 1 (itself) + how many similar complaints are within threshold distance
    close_matches = [cid for cid, dist in similar_results if cid != complaint_id and dist < threshold]
    return 1 + len(close_matches)


def _assign_department(db: Session, category: str) -> int | None:
    dept = db.query(Department).filter(Department.category.ilike(f"%{category}%")).first()
    return dept.id if dept else None


def create_complaint(db: Session, payload: ComplaintCreate, user_id: int) -> Complaint:
    """
    Pipeline: save (unclassified) -> classify -> similarity check ->
    sentiment -> priority score -> department auto-assign -> update row -> respond
    """
    text = f"{payload.title}. {payload.description}"

    # 1. Save unclassified first so we have an ID for the similarity index / history log.
    complaint = Complaint(
        title=payload.title,
        description=payload.description,
        created_by=user_id,
        people_affected=payload.people_affected,
        sla_deadline=datetime.now(timezone.utc) + timedelta(hours=settings.DEFAULT_SLA_HOURS),
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    # 2. Classify category
    category = classify_complaint(text)

    # 3. Similarity check (also adds this complaint to the index for future checks)
    similar_results = find_similar(text, top_k=5)
    get_index().add(complaint.id, text)
    repeat_count = _count_similar(complaint.id, similar_results)
    similar_ids = [
        cid for cid, distance in similar_results
        if cid != complaint.id and distance < 1.0
    ]
    if similar_ids:
        matched = (
            db.query(Complaint)
            .filter(Complaint.id.in_(similar_ids))
            .order_by(Complaint.id)
            .first()
        )
        complaint.issue_root_id = (
            matched.issue_root_id if matched and matched.issue_root_id else matched.id
        ) if matched else complaint.id
    else:
        complaint.issue_root_id = complaint.id

    # 4. Sentiment
    sentiment = analyze_sentiment(text)

    # 5. Priority score
    age_days = 0.0  # brand new complaint
    severity = _severity_from_sentiment(sentiment)
    priority_score = compute_priority(
        severity=severity,
        people_affected=payload.people_affected,
        age_days=age_days,
        repeat_count=repeat_count,
    )

    # 6. Department auto-assign
    department_id = _assign_department(db, category)
    if department_id is not None:
        assigned_staff = (
            db.query(User)
            .filter(User.role == UserRole.staff)
            .order_by(User.id)
            .first()
        )
        if assigned_staff:
            complaint.assigned_to = assigned_staff.id

    # 7. Update the row with everything the AI produced
    complaint.category = category
    complaint.sentiment_label = sentiment["label"]
    complaint.sentiment_score = sentiment["score"]
    complaint.priority_score = priority_score
    complaint.repeat_count = repeat_count
    complaint.department_id = department_id
    db.commit()
    db.refresh(complaint)

    db.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            action="created_and_classified",
            detail=f"category={category}, priority={priority_score}, dept={department_id}",
            actor_id=user_id,
        )
    )
    db.commit()

    return complaint


def update_status(db: Session, complaint: Complaint, new_status: str, actor_id: int) -> Complaint:
    old_status = complaint.status
    complaint.status = new_status
    db.commit()
    db.refresh(complaint)

    db.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            action="status_changed",
            detail=f"{old_status} -> {new_status}",
            actor_id=actor_id,
        )
    )
    db.commit()
    return complaint
