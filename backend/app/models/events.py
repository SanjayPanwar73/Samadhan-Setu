"""Transactional outbox, notifications, identity access log."""

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
    false, func,
)

from app.core.database import Base


class DomainEvent(Base):
    __tablename__ = "domain_events"
    __table_args__ = (Index("ix_domain_events_pending", "processed_at", "attempts"),)

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False)
    issue_id = Column(Integer, nullable=True, index=True)
    complaint_id = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("recipient_id", "dedupe_key", name="uq_notification_dedupe"),
        Index("ix_notifications_recipient_read", "recipient_id", "is_read", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)
    issue_id = Column(Integer, nullable=True)
    complaint_id = Column(Integer, nullable=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)  # allow-listed safe fields only
    dedupe_key = Column(String, nullable=False)
    group_key = Column(String, nullable=True, index=True)
    count = Column(Integer, nullable=False, default=1)
    is_read = Column(Boolean, nullable=False, server_default=false(), default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IdentityAccessLog(Base):
    __tablename__ = "identity_access_log"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
