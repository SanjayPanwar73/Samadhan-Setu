from sqlalchemy import (
    JSON, Boolean, Column, Float, ForeignKey, Integer, String, UniqueConstraint, false, true,
)

from app.core.database import Base


class Category(Base):
    """A complaint category inside a department. Drives classifier labels and priority inputs."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("department_id", "name", name="uq_category_dept_name"),)

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    base_severity = Column(Float, nullable=False, default=0.3)       # 0-1
    default_criticality = Column(Float, nullable=False, default=0.3)  # 0-1
    impact_level = Column(Float, nullable=False, default=0.3)        # 0-1
    expected_resolution_hours = Column(Integer, nullable=False, default=48)
    requires_verification = Column(Boolean, nullable=False, server_default=false(), default=False)
    requires_evidence = Column(Boolean, nullable=False, server_default=false(), default=False)
    resolution_schema = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=true(), default=True)
