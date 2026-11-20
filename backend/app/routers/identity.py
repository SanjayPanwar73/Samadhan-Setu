"""Revealing an anonymous submitter is a rare, fully logged super-admin action."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.complaint import Complaint
from app.models.events import IdentityAccessLog
from app.models.user import User
from app.schemas.v2 import RevealIn
from app.services import audit_service

router = APIRouter(prefix="/admin", tags=["identity"])


@router.post("/complaints/{complaint_id}/reveal-identity")
def reveal_identity(complaint_id: int, payload: RevealIn, db: Session = Depends(get_db),
                    actor: User = Depends(require_role("super_admin"))):
    c = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if c is None:
        raise HTTPException(404, "Complaint not found")
    student = db.query(User).filter(User.id == c.created_by).first()
    db.add(IdentityAccessLog(actor_id=actor.id, complaint_id=c.id, reason=payload.reason))
    audit_service.record(db, actor=actor, action="identity_revealed", entity_type="complaint",
                         entity_id=c.id, issue_id=c.issue_id, complaint_id=c.id, reason=payload.reason)
    db.commit()
    return {"complaint_id": c.id, "was_anonymous": bool(c.is_anonymous), "name": student.name,
            "email": student.email, "enrollment_no": student.enrollment_no}
