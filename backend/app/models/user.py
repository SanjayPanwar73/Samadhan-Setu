import enum

from sqlalchemy import Boolean, Column, Integer, String, Enum, DateTime, func, true
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserRole(str, enum.Enum):
    user = "user"
    staff = "staff"
    admin = "admin"
    management = "management"
    # V2 roles (the V1 values above stay until the backfill converts them)
    student = "student"
    dept_admin = "dept_admin"
    hod = "hod"
    super_admin = "super_admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.user, nullable=False)
    # Legacy single-department pointer. V2 scope lives in department_memberships;
    # this column is kept in sync for staff / dept_admin so V1 code keeps working.
    department_id = Column(Integer, nullable=True)
    enrollment_no = Column(String, unique=True, index=True, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=true(), default=True)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    complaints_created = relationship(
        "Complaint", back_populates="creator", foreign_keys="Complaint.created_by"
    )
    memberships = relationship(
        "DepartmentMembership",
        back_populates="user",
        foreign_keys="DepartmentMembership.user_id",
        cascade="all, delete-orphan",
    )
