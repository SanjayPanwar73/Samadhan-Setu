from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, false, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- V2: one response per complaint per resolution cycle ---
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=True, index=True)
    resolution_report_id = Column(Integer, ForeignKey("resolution_reports.id"), nullable=True)
    resolved_for_me = Column(Boolean, nullable=True)
    still_unresolved = Column(Boolean, nullable=False, server_default=false(), default=False)

    __table_args__ = (
        UniqueConstraint("complaint_id", "resolution_report_id", name="uq_feedback_complaint_report"),
    )

    complaint = relationship("Complaint", back_populates="feedback")
