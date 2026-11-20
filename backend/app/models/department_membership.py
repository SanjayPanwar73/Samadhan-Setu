from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class DepartmentMembership(Base):
    __tablename__ = "department_memberships"
    __table_args__ = (UniqueConstraint("user_id", "department_id", name="uq_membership_user_dept"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="memberships", foreign_keys=[user_id])
    department = relationship("Department")
