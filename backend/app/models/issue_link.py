from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, func, text

from app.core.database import Base


class IssueLink(Base):
    """Link history. The row with ``unlinked_at IS NULL`` is the complaint's current link."""

    __tablename__ = "issue_links"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False, index=True)
    link_type = Column(String, nullable=False)  # auto | admin | system_migration | relink
    match_score = Column(Float, nullable=True)
    match_breakdown = Column(JSON, nullable=True)
    algorithm_version = Column(String, nullable=True)
    linked_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # null = system
    linked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    unlinked_at = Column(DateTime(timezone=True), nullable=True)
    unlink_reason = Column(Text, nullable=True)

    __table_args__ = (
        Index(
            "uq_issue_link_current",
            "complaint_id",
            unique=True,
            sqlite_where=text("unlinked_at IS NULL"),
            postgresql_where=text("unlinked_at IS NULL"),
        ),
    )
