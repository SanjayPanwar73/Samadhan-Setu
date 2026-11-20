"""Assignments, task updates, resolution reports, attachments."""

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, false, func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

ACTIVE_ASSIGNMENT_STATUSES = ("assigned", "acknowledged", "in_progress", "awaiting_verification")


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        Index("ix_assignments_staff_status", "staff_id", "status"),
        Index("ix_assignments_issue", "issue_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False)
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_lead = Column(Boolean, nullable=False, server_default=false(), default=False)
    task_description = Column(Text, nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True)
    priority_at_assignment = Column(String, nullable=True)
    status = Column(String, nullable=False, default="assigned")
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    reassign_requested = Column(Boolean, nullable=False, server_default=false(), default=False)
    reassign_reason = Column(Text, nullable=True)
    issue = relationship("Issue", viewonly=True)


class TaskUpdate(Base):
    __tablename__ = "task_updates"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False, index=True)
    kind = Column(String, nullable=False)  # progress | blocker | reassignment_request | note
    body = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ResolutionReport(Base):
    __tablename__ = "resolution_reports"
    __table_args__ = (Index("ix_resolution_reports_issue_cycle", "issue_id", "cycle"),)

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)
    cycle = Column(Integer, nullable=False, default=1)
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    what_was_wrong = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    action_taken = Column(Text, nullable=True)
    parts_replaced = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    followup_needed = Column(Boolean, nullable=False, server_default=false(), default=False)
    followup_notes = Column(Text, nullable=True)
    public_summary = Column(Text, nullable=True)  # student-safe text
    status = Column(String, nullable=False, default="submitted")  # submitted | approved | rejected
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verifier_comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachments_owner", "owner_type", "owner_id"),)

    id = Column(Integer, primary_key=True, index=True)
    owner_type = Column(String, nullable=False)  # complaint | assignment | resolution
    owner_id = Column(Integer, nullable=False)
    kind = Column(String, nullable=False, default="evidence")  # evidence | before | after
    storage_key = Column(String, nullable=False)
    original_name = Column(String, nullable=False)
    mime = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
