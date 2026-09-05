import enum

from sqlalchemy import Column, Integer, String, Enum, DateTime, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserRole(str, enum.Enum):
    user = "user"
    staff = "staff"
    admin = "admin"
    management = "management"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.user, nullable=False)
    department_id = Column(Integer, nullable=True)  # set for staff/admin tied to a dept
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    complaints_created = relationship(
        "Complaint", back_populates="creator", foreign_keys="Complaint.created_by"
    )
