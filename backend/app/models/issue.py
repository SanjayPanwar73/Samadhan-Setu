from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, false, func, text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

ACTIVE_STATUSES = ("open", "assigned", "in_progress", "awaiting_verification", "reopened")
ALL_STATUSES = ACTIVE_STATUSES + ("resolved", "closed", "rejected", "merged")

_ACTIVE_SQL = "asset_id IS NOT NULL AND status IN ({})".format(
    ", ".join(f"'{s}'" for s in ACTIVE_STATUSES)
)


class Issue(Base):
    """The cumulative ticket: one shared physical problem, many individual complaints."""

    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    ticket_no = Column(String, unique=True, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="open")
    needs_review = Column(Boolean, nullable=False, server_default=false(), default=False)
    needs_review_reason = Column(String, nullable=True)

    report_count = Column(Integer, nullable=False, default=0)
    distinct_reporter_count = Column(Integer, nullable=False, default=0)

    priority_score = Column(Float, nullable=True)
    priority_band = Column(String, nullable=True)
    current_assessment_id = Column(Integer, nullable=True)

    sla_anchor_at = Column(DateTime(timezone=True), nullable=True)  # set when the SLA restarts
    sla_response_due_at = Column(DateTime(timezone=True), nullable=True)
    sla_resolution_due_at = Column(DateTime(timezone=True), nullable=True)
    escalation_level = Column(Integer, nullable=False, default=0)
    last_escalated_at = Column(DateTime(timezone=True), nullable=True)

    first_reported_at = Column(DateTime(timezone=True), nullable=True)
    last_reported_at = Column(DateTime(timezone=True), nullable=True)
    last_progress_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    reopen_count = Column(Integer, nullable=False, default=0)

    recurrence_of_issue_id = Column(Integer, ForeignKey("issues.id"), nullable=True)
    merged_into_id = Column(Integer, ForeignKey("issues.id"), nullable=True)

    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    category = relationship("Category", viewonly=True)
    location = relationship("Location", viewonly=True)
    asset = relationship("Asset", viewonly=True)

    __table_args__ = (
        Index("ix_issues_dept_status_priority", "department_id", "status", "priority_score"),
        Index("ix_issues_asset", "asset_id"),
        Index("ix_issues_location", "location_id"),
        # Database-level guard: at most one active issue per asset.
        Index(
            "uq_issue_active_asset",
            "asset_id",
            unique=True,
            sqlite_where=text(_ACTIVE_SQL),
            postgresql_where=text(_ACTIVE_SQL),
        ),
    )
