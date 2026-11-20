from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func

from app.core.database import Base


class DuplicateSuggestion(Base):
    """Medium-confidence match awaiting a department admin decision."""

    __tablename__ = "duplicate_suggestions"
    __table_args__ = (UniqueConstraint("complaint_id", "candidate_issue_id", name="uq_dup_suggestion"),)

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    candidate_issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False, index=True)
    score = Column(Float, nullable=False)
    breakdown = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending | accepted | rejected
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
