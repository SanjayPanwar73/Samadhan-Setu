from sqlalchemy import Column, Integer, String

from app.core.database import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    # Category keywords this department handles, e.g. "electricity,power,outage"
    # Used by the auto-assign step after AI classification.
    category = Column(String, nullable=False)
