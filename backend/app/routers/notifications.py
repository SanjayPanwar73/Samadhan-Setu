from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.models.complaint import Complaint, ComplaintStatus
from app.models.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Complaint)
    if current_user.role.value == "user":
        query = query.filter(Complaint.created_by == current_user.id)
    elif current_user.role.value == "staff":
        query = query.filter(Complaint.assigned_to == current_user.id)
    elif current_user.role.value == "management":
        query = query.filter(Complaint.status.in_([ComplaintStatus.pending, ComplaintStatus.in_progress]))

    complaints = (
        query.order_by(Complaint.updated_at.desc(), Complaint.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    notifications = []
    for complaint in complaints:
        if current_user.role.value == "user":
            title = f"Complaint #{complaint.id} updated"
            message = f'"{complaint.title}" is currently {complaint.status.value.replace("_", " ")}.'
        elif current_user.role.value == "staff":
            title = f"Complaint #{complaint.id} assigned"
            message = f'You are assigned to "{complaint.title}".'
        else:
            title = f"Complaint #{complaint.id} requires attention"
            message = f'"{complaint.title}" has priority {complaint.priority_score or 0:.2f}.'
        notifications.append(
            {
                "id": f"complaint-{complaint.id}",
                "title": title,
                "message": message,
                "complaint_id": complaint.id,
                "created_at": complaint.updated_at or complaint.created_at,
            }
        )
    return notifications
