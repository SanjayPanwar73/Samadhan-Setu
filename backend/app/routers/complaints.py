from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.complaint import Complaint
from app.models.feedback import Feedback
from app.models.user import User
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintOut,
    ComplaintStatusUpdate,
    FeedbackCreate,
)
from app.services.complaint_service import create_complaint, update_status

router = APIRouter(prefix="/complaints", tags=["complaints"])

VALID_TRANSITIONS = {
    "pending": {"in_progress", "rejected"},
    "in_progress": {"resolved", "rejected"},
    "resolved": set(),
    "rejected": set(),
}


@router.post("", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
def submit_complaint(
    payload: ComplaintCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_complaint(db, payload, current_user.id)


@router.get("/me", response_model=list[ComplaintOut])
def my_complaints(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return (
        db.query(Complaint)
        .filter(Complaint.created_by == current_user.id)
        .order_by(Complaint.created_at.desc())
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

    current = complaint.status.value if hasattr(complaint.status, "value") else complaint.status
    new_status = payload.status.value if hasattr(payload.status, "value") else payload.status

    if new_status not in VALID_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition: {current} -> {new_status}",
        )

    return update_status(db, complaint, payload.status, current_user.id)


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
    db.commit()
    db.refresh(feedback)
    return {"id": feedback.id, "message": "Feedback recorded"}
