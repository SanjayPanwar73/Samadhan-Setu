"""Authenticated attachment download. Files are never served from a public static path."""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.roles import has_role
from app.core.storage import get_storage
from app.deps import Scope, get_current_user, get_scope
from app.models.complaint import Complaint
from app.models.issue import Issue
from app.models.user import User
from app.models.work import Assignment, Attachment

router = APIRouter(tags=["attachments"])


def _issue_of(db: Session, att: Attachment) -> Issue | None:
    if att.owner_type == "complaint":
        c = db.query(Complaint).filter(Complaint.id == att.owner_id).first()
        return db.query(Issue).filter(Issue.id == c.issue_id).first() if c and c.issue_id else None
    if att.owner_type == "assignment":
        a = db.query(Assignment).filter(Assignment.id == att.owner_id).first()
        return db.query(Issue).filter(Issue.id == a.issue_id).first() if a else None
    return None


@router.get("/attachments/{attachment_id}")
def download(attachment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user),
             scope: Scope = Depends(get_scope)):
    att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    allowed = False
    if att is not None:
        issue = _issue_of(db, att)
        if att.uploaded_by == user.id:
            allowed = True
        elif has_role(user, "staff") and issue is not None:
            allowed = db.query(Assignment.id).filter(Assignment.issue_id == issue.id,
                                                     Assignment.staff_id == user.id).first() is not None
        elif has_role(user, "dept_admin", "super_admin") and issue is not None:
            allowed = scope.can_access(issue.department_id)
    if not allowed:
        raise HTTPException(404, "Attachment not found")
    path = get_storage().path(att.storage_key)
    if not os.path.exists(path):
        raise HTTPException(404, "Attachment not found")
    return FileResponse(path, media_type=att.mime, filename=att.original_name,
                        headers={"X-Content-Type-Options": "nosniff"})
