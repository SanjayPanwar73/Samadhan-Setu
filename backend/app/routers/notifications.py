from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.timeutil import utcnow
from app.deps import get_current_user
from app.models.events import Notification
from app.models.user import User
from app.schemas.v2 import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(unread_only: bool = False, offset: int = Query(0, ge=0, le=100_000),
                       limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    q = db.query(Notification).filter(Notification.recipient_id == user.id)
    if unread_only:
        q = q.filter(Notification.is_read.is_(False))
    return q.order_by(Notification.updated_at.desc(), Notification.id.desc()).offset(offset).limit(limit).all()


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.recipient_id == user.id, Notification.is_read.is_(False)).count()
    return {"unread": n}


@router.post("/read-all")
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = (db.query(Notification).filter(Notification.recipient_id == user.id, Notification.is_read.is_(False))
         .update({"is_read": True, "read_at": utcnow()}, synchronize_session=False))
    db.commit()
    return {"marked": n}


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.id == notification_id,
                                      Notification.recipient_id == user.id).first()
    if n is None:
        raise HTTPException(404, "Notification not found")
    if not n.is_read:
        n.is_read, n.read_at = True, utcnow()
        db.commit()
    return {"id": n.id, "is_read": True}
