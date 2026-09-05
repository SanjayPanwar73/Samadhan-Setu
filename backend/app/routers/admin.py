from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.complaint import Complaint
from app.models.department import Department
from app.schemas.complaint import ComplaintOut
from app.services.escalation_service import run_escalation_check

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])


@router.get("/escalations", response_model=list[ComplaintOut])
def list_escalated(db: Session = Depends(get_db)):
    return (
        db.query(Complaint)
        .filter(Complaint.escalation_level > 0)
        .order_by(Complaint.escalation_level.desc())
        .all()
    )


@router.post("/escalations/run-now")
def trigger_escalation_check(db: Session = Depends(get_db)):
    """Manually trigger the escalation sweep — useful for testing without waiting for the scheduler."""
    count = run_escalation_check(db)
    return {"escalated_count": count}


@router.get("/departments")
def list_departments(db: Session = Depends(get_db)):
    return db.query(Department).all()
