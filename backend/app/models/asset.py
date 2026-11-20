from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, true

from app.core.database import Base


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (Index("ix_assets_location_type", "location_id", "asset_type"),)

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    asset_type = Column(String, nullable=False)  # e.g. water_cooler
    tag = Column(String, unique=True, nullable=False)  # e.g. WC-W1-C3-01
    name = Column(String, nullable=False)
    criticality = Column(Integer, nullable=False, default=3)  # 1-5
    is_active = Column(Boolean, nullable=False, server_default=true(), default=True)
