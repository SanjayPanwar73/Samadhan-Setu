"""Append-only audit writer. The only code allowed to insert into ``audit_events``.

``record`` adds the row to the caller's session without committing, so the audit
entry lands in the same transaction as the change it describes.
"""

from sqlalchemy.orm import Session

from app.core.roles import role_value
from app.models.audit_event import AuditEvent
from app.models.user import User


def record(
    db: Session,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
    issue_id: int | None = None,
    complaint_id: int | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor.id if actor else None,
        actor_role=role_value(actor.role) if actor else "system",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        issue_id=issue_id,
        complaint_id=complaint_id,
        before=before,
        after=after,
        reason=reason,
        request_id=request_id,
    )
    db.add(event)
    return event
