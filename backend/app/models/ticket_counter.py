from sqlalchemy import Column, ForeignKey, Integer

from app.core.database import Base


class TicketCounter(Base):
    """Per-department sequence for ticket numbers (WAT-001, WAT-002, ...)."""

    __tablename__ = "ticket_counters"

    department_id = Column(Integer, ForeignKey("departments.id"), primary_key=True)
    next_value = Column(Integer, nullable=False, default=1)
