import enum

from sqlalchemy import Column, Integer, String, Text, Float, Enum, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ComplaintStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    resolved = "resolved"
    rejected = "rejected"


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)

    # --- Filled in by AI after creation (nullable at insert time) ---
    category = Column(String, nullable=True)
    priority_score = Column(Float, nullable=True)
    sentiment_label = Column(String, nullable=True)
    sentiment_score = Column(Float, nullable=True)

    status = Column(Enum(ComplaintStatus), default=ComplaintStatus.pending, nullable=False)

    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)

    people_affected = Column(Integer, default=1)
    repeat_count = Column(Integer, default=1)

    sla_deadline = Column(DateTime(timezone=True), nullable=True)
    escalation_level = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    creator = relationship("User", back_populates="complaints_created", foreign_keys=[created_by])
    history = relationship("ComplaintHistory", back_populates="complaint")
    feedback = relationship("Feedback", back_populates="complaint")
