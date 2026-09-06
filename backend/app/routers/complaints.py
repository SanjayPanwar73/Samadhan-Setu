from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.complaint import Complaint
from app.models.feedback import Feedback
from app.models.department import Department
from app.models.user import User
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintOut,
    ComplaintStatusUpdate,
    FeedbackCreate,
    ComplaintOverride,
)
from app.services.complaint_service import create_complaint, update_status
from app.ai.rag import generate_suggestion, retrieve_similar_resolutions

router = APIRouter(prefix="/complaints", tags=["complaints"])

VALID_TRANSITIONS = {
    "pending": {"in_progress", "rejected"},
    "in_progress": {"resolved", "rejected"},
    "resolved": set(),
    "reopened": {"in_progress"},
    "rejected": set(),
}


def _ensure_staff_scope(complaint: Complaint, current_user: User) -> None:
    """Staff may act only on complaints assigned to them; admins are global."""
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if role == "staff" and complaint.assigned_to != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff may only act on complaints assigned to them",
        )


@router.post("", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
def submit_complaint(
    payload: ComplaintCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_complaint(db, payload, current_user.id)


@router.get("/me", response_model=list[ComplaintOut])
def my_complaints(
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Complaint)
        .filter(Complaint.created_by == current_user.id)
        .order_by(Complaint.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/assigned", response_model=list[ComplaintOut])
def assigned_complaints(
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("staff", "admin")),
):
    return (
        db.query(Complaint)
        .filter(Complaint.assigned_to == current_user.id)
        .order_by(Complaint.priority_score.desc(), Complaint.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{complaint_id}", response_model=ComplaintOut)
def get_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    is_owner = complaint.created_by == current_user.id
    is_staff_or_above = current_user.role.value in ("staff", "admin", "management")
    if not (is_owner or is_staff_or_above):
        raise HTTPException(status_code=403, detail="Not authorized to view this complaint")

    return complaint


@router.patch("/{complaint_id}/status", response_model=ComplaintOut)
def patch_status(
    complaint_id: int,
    payload: ComplaintStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("staff", "admin")),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    _ensure_staff_scope(complaint, current_user)

    current = complaint.status.value if hasattr(complaint.status, "value") else complaint.status
    new_status = payload.status.value if hasattr(payload.status, "value") else payload.status

    if new_status not in VALID_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition: {current} -> {new_status}",
        )

    resolution_text = payload.resolution_text or payload.remarks
    return update_status(db, complaint, payload.status, current_user.id, resolution_text)


@router.get("/{complaint_id}/suggested-resolution")
def suggested_resolution(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("staff", "admin")),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    _ensure_staff_scope(complaint, current_user)

    retrieved = retrieve_similar_resolutions(
        f"{complaint.title}. {complaint.description}"
    )
    retrieved = [
        result for result in retrieved if result["complaint_id"] != complaint.id
    ]
    suggested_action = generate_suggestion(
        f"{complaint.title}. {complaint.description}", retrieved
    ) if retrieved else None
    return {
        "complaint_id": complaint.id,
        "retrieved_cases": retrieved,
        "suggested_action": suggested_action,
        "generated": suggested_action is not None,
    }


@router.patch("/{complaint_id}/override", response_model=ComplaintOut)
def override_complaint(
    complaint_id: int,
    payload: ComplaintOverride,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if payload.department_id is None and payload.priority_score is None:
        raise HTTPException(status_code=400, detail="Provide a department or priority score")
    if payload.priority_score is not None and not 0 <= payload.priority_score <= 100:
        raise HTTPException(status_code=400, detail="Priority score must be between 0 and 100")
    if payload.department_id is not None:
        department = db.query(Department).filter(Department.id == payload.department_id).first()
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        complaint.department_id = department.id
    if payload.priority_score is not None:
        complaint.priority_score = payload.priority_score
    db.commit()
    db.refresh(complaint)
    return complaint


@router.post("/{complaint_id}/feedback", status_code=status.HTTP_201_CREATED)
def add_feedback(
    complaint_id: int,
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if complaint.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the complaint owner can leave feedback")
    if not (1 <= payload.rating <= 5):
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    feedback = Feedback(
        complaint_id=complaint_id,
        user_id=current_user.id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(feedback)
    was_resolved = complaint.status.value == "resolved" if hasattr(complaint.status, "value") else complaint.status == "resolved"
    if was_resolved and payload.rating <= 2:
        complaint.status = "reopened"
        complaint.escalation_level = (complaint.escalation_level or 0) + 1
        complaint.repeat_count = (complaint.repeat_count or 1) + 1
        from app.ai.priority import compute_priority
        from app.models.complaint_history import ComplaintHistory
        from datetime import datetime, timezone

        age_days = max(
            0.0,
            (datetime.now(timezone.utc) - complaint.created_at.replace(tzinfo=timezone.utc)).total_seconds()
            / 86400,
        )
        priority = compute_priority(
            severity=complaint.sentiment_score or 0.0,
            people_affected=complaint.people_affected or 1,
            age_days=age_days,
            repeat_count=complaint.repeat_count,
        )
        complaint.priority_score = priority["final_score"]
        complaint.priority_breakdown = priority
        db.add(
            ComplaintHistory(
                complaint_id=complaint.id,
                action="auto_reopened",
                detail=f"Reopened due to low feedback rating: {payload.rating}/5",
                actor_id=current_user.id,
            )
        )
    db.commit()
    db.refresh(feedback)
    return {"id": feedback.id, "message": "Feedback recorded"}
