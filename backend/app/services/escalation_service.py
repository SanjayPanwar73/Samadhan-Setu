from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.complaint import Complaint, ComplaintStatus
from app.models.complaint_history import ComplaintHistory


def run_escalation_check(db: Session) -> int:
    """
    Finds pending/in-progress complaints past their SLA deadline, bumps their
    escalation_level, and logs it to complaint_history.

    Returns the number of complaints escalated (useful for logging/testing).
    """
    now = datetime.now(timezone.utc)
    overdue = (
        db.query(Complaint)
        .filter(
            Complaint.status.in_([ComplaintStatus.pending, ComplaintStatus.in_progress]),
            Complaint.sla_deadline < now,
        )
        .all()
    )

    for complaint in overdue:
        complaint.escalation_level += 1
        db.add(
            ComplaintHistory(
                complaint_id=complaint.id,
                action="escalated",
                detail=f"escalation_level -> {complaint.escalation_level}",
                actor_id=None,  # system action
            )
        )

    db.commit()
    return len(overdue)
