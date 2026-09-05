from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ComplaintHistory(Base):
    __tablename__ = "complaint_history"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    action = Column(String, nullable=False)  # e.g. "status_changed", "escalated", "assigned"
    detail = Column(String, nullable=True)   # e.g. "pending -> in_progress"
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null for system actions
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    complaint = relationship("Complaint", back_populates="history")
