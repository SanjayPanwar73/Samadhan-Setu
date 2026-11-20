from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class AuditEvent(Base):
    """Append-only audit record. ``audit_service`` is the only writer; nothing updates or deletes."""

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null = system
    actor_role = Column(String, nullable=True)
    action = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=True)
    # Plain integers for now; foreign keys to issues/complaints are added with the issues tables.
    issue_id = Column(Integer, nullable=True, index=True)
    complaint_id = Column(Integer, nullable=True)
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)
    reason = Column(Text, nullable=True)
    request_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
