from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, true

from app.core.database import Base

LOCATION_KINDS = ("campus", "building", "wing", "floor", "corridor", "room")


class Location(Base):
    """Self-referential location tree: campus > building > wing > floor > corridor > room."""

    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    kind = Column(String, nullable=False)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)  # denormalised, e.g. "Main Block > Wing 1 > Floor 2"
    is_active = Column(Boolean, nullable=False, server_default=true(), default=True)
