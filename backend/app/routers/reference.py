"""Read-only reference data for the intake form (any authenticated user)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.models.asset import Asset
from app.models.category import Category
from app.models.department import Department
from app.models.location import Location
from app.schemas.org import AssetOut, CategoryOut, DepartmentOut, LocationOut

router = APIRouter(prefix="/reference", tags=["reference"], dependencies=[Depends(get_current_user)])


@router.get("/departments", response_model=list[DepartmentOut])
def departments(db: Session = Depends(get_db)):
    # System departments (Triage) are never offered to students.
    return (
        db.query(Department)
        .filter(Department.is_active.is_(True), Department.is_system.is_(False), Department.code.isnot(None))
        .order_by(Department.name)
        .all()
    )


@router.get("/categories", response_model=list[CategoryOut])
def categories(department_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db)):
    query = (
        db.query(Category)
        .join(Department, Department.id == Category.department_id)
        .filter(Category.is_active.is_(True), Department.is_active.is_(True), Department.is_system.is_(False))
    )
    if department_id is not None:
        query = query.filter(Category.department_id == department_id)
    return query.order_by(Category.name).all()


@router.get("/locations", response_model=list[LocationOut])
def locations(parent_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db)):
    """Children of ``parent_id``; roots when omitted. Used by the cascading location picker."""
    query = db.query(Location).filter(Location.is_active.is_(True))
    query = query.filter(Location.parent_id.is_(None) if parent_id is None else Location.parent_id == parent_id)
    return query.order_by(Location.name).all()


@router.get("/assets", response_model=list[AssetOut])
def assets(
    location_id: int = Query(ge=1),
    type: str | None = Query(default=None, max_length=60),
    db: Session = Depends(get_db),
):
    query = db.query(Asset).filter(Asset.location_id == location_id, Asset.is_active.is_(True))
    if type:
        query = query.filter(Asset.asset_type == type)
    return query.order_by(Asset.tag).all()
