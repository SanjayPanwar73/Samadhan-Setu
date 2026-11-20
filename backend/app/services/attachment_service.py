from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import DomainError
from app.core.storage import get_storage, sniff
from app.models.user import User
from app.models.work import Attachment
from app.services import audit_service

MAX_FILES_PER_OWNER = 10


async def save_upload(db: Session, upload: UploadFile, *, owner_type: str, owner_id: int, kind: str,
                      user: User, issue_id: int | None = None) -> Attachment:
    if kind not in ("evidence", "before", "after"):
        raise DomainError("invalid_kind", "kind must be evidence, before or after", 422)
    if db.query(Attachment).filter(Attachment.owner_type == owner_type,
                                   Attachment.owner_id == owner_id).count() >= MAX_FILES_PER_OWNER:
        raise DomainError("too_many_files", "Attachment limit reached", 409)
    content = await upload.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise DomainError("file_too_large", "File exceeds the size limit", 413)
    if not content:
        raise DomainError("empty_file", "File is empty", 422)
    mime = sniff(content, upload.content_type or "")
    key, digest = get_storage().save(content, mime)
    att = Attachment(owner_type=owner_type, owner_id=owner_id, kind=kind, storage_key=key,
                     original_name=(upload.filename or "file")[:120], mime=mime, size_bytes=len(content),
                     sha256=digest, uploaded_by=user.id)
    db.add(att)
    db.flush()
    audit_service.record(db, actor=user, action="attachment_uploaded", entity_type="attachment",
                         entity_id=att.id, issue_id=issue_id,
                         after={"owner_type": owner_type, "owner_id": owner_id, "size": len(content)})
    return att
