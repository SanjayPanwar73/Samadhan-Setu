from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ResolutionHistory(Base):
    __tablename__ = "resolution_history"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    resolution_text = Column(Text, nullable=False)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    resolved_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    complaint = relationship("Complaint")
    resolver = relationship("User")
