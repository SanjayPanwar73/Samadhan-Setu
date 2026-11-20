import enum

from sqlalchemy import Boolean, Column, Integer, String, Text, Float, Enum, DateTime, ForeignKey, Index, JSON, UniqueConstraint, false, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ComplaintStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    resolved = "resolved"
    rejected = "rejected"
    reopened = "reopened"
    # V2 issue-driven statuses (synced from the issue)
    open = "open"
    assigned = "assigned"
    awaiting_verification = "awaiting_verification"
    closed = "closed"
    merged = "merged"


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)

    # --- Classification and sentiment recorded at intake ---
    category = Column(String, nullable=True)
    sentiment_label = Column(String, nullable=True)
    sentiment_score = Column(Float, nullable=True)

    status = Column(Enum(ComplaintStatus, values_callable=lambda enum: [item.value for item in enum]), default=ComplaintStatus.pending, nullable=False)

    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    people_affected = Column(Integer, default=1)


    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- V2 ---
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=True, index=True)  # current link
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    location_text = Column(String, nullable=True)
    is_anonymous = Column(Boolean, nullable=False, server_default=false(), default=False)
    anon_code = Column(String, nullable=True)
    student_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    ai_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    ai_confidence = Column(Float, nullable=True)
    classification_disagreement = Column(Boolean, nullable=False, server_default=false(), default=False)
    has_dissent = Column(Boolean, nullable=False, server_default=false(), default=False)
    client_request_id = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("created_by", "client_request_id", name="uq_complaint_client_request"),
        Index("ix_complaints_created_by_created_at", "created_by", "created_at"),
    )

    creator = relationship("User", back_populates="complaints_created", foreign_keys=[created_by])
    location = relationship("Location", viewonly=True)
    asset = relationship("Asset", viewonly=True)
    current_link = relationship("IssueLink", uselist=False, viewonly=True,
                                primaryjoin="and_(Complaint.id == IssueLink.complaint_id, IssueLink.unlinked_at == None)")
    history = relationship("ComplaintHistory", back_populates="complaint")
    feedback = relationship("Feedback", back_populates="complaint")
