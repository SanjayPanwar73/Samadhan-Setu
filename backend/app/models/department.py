from sqlalchemy import Boolean, Column, DateTime, Integer, String, false, func, true

from app.core.database import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    # Deprecated V1 keyword. Kept (nullable) only so the backfill can map old departments.
    category = Column(String, nullable=True)

    # --- V2 ---
    code = Column(String, unique=True, index=True, nullable=True)  # WAT, ELE, CLN, ACC
    is_active = Column(Boolean, nullable=False, server_default=true(), default=True)
    is_system = Column(Boolean, nullable=False, server_default=false(), default=False)  # Triage
    requires_verification_default = Column(
        Boolean, nullable=False, server_default=false(), default=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
