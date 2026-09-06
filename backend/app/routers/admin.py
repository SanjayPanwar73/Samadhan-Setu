from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password
from app.deps import require_role
from app.models.complaint import Complaint, ComplaintStatus
from app.models.complaint_history import ComplaintHistory
from app.models.department import Department
from app.models.user import User, UserRole
from app.schemas.auth import ManagedUserCreate, UserOut
from app.schemas.complaint import ComplaintAssignment, ComplaintOut
from app.services.escalation_service import run_escalation_check
from sqlalchemy import func

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=500)

    @field_validator("name", "category")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("name", "category")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value


def _create_managed_user(
    payload: ManagedUserCreate,
    role: UserRole,
    db: Session,
) -> User:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    if payload.department_id is not None:
        department = db.query(Department).filter(Department.id == payload.department_id).first()
        if department is None:
            raise HTTPException(status_code=400, detail="Department not found")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=role,
        department_id=payload.department_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/staff", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_staff(payload: ManagedUserCreate, db: Session = Depends(get_db)):
    return _create_managed_user(payload, UserRole.staff, db)


@router.post("/management", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_management(payload: ManagedUserCreate, db: Session = Depends(get_db)):
    # The role is selected by this protected endpoint, never by the client.
    return _create_managed_user(payload, UserRole.management, db)


@router.get("/management", response_model=list[UserOut])
def list_management(
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return (
        db.query(User)
        .filter(User.role == UserRole.management)
        .order_by(User.name)
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/staff")
def list_staff(
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    staff = (
        db.query(User)
        .filter(User.role == UserRole.staff)
        .order_by(User.name)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": member.id,
            "name": member.name,
            "email": member.email,
            "department_id": member.department_id,
        }
        for member in staff
    ]


@router.get("/staff-workload")
def staff_workload(
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    open_statuses = [ComplaintStatus.pending, ComplaintStatus.in_progress, ComplaintStatus.reopened]
    staff = (
        db.query(User)
        .filter(User.role == UserRole.staff)
        .order_by(User.name)
        .offset(offset)
        .limit(limit)
        .all()
    )
    counts = dict(
        db.query(Complaint.assigned_to, func.count(Complaint.id))
        .filter(Complaint.status.in_(open_statuses))
        .group_by(Complaint.assigned_to)
        .all()
    )
    departments = {department.id: department.name for department in db.query(Department).all()}
    return [
        {
            "staff_id": member.id,
            "name": member.name,
            "department": departments.get(member.department_id),
            "open_complaint_count": counts.get(member.id, 0),
        }
        for member in staff
    ]


@router.patch("/complaints/{complaint_id}/assign", response_model=ComplaintOut)
def assign_complaint(
    complaint_id: int,
    payload: ComplaintAssignment,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    staff_id = payload.staff_id
    staff = None
    if staff_id is not None:
        staff = (
            db.query(User)
            .filter(User.id == staff_id, User.role == UserRole.staff)
            .first()
        )
        if not staff:
            raise HTTPException(status_code=400, detail="Selected user is not a staff member")

    old_staff_id = complaint.assigned_to
    complaint.assigned_to = staff.id if staff else None
    db.add(
        ComplaintHistory(
            complaint_id=complaint.id,
            action="assigned",
            detail=f"{old_staff_id or 'unassigned'} -> {staff.id if staff else 'unassigned'}",
            actor_id=current_user.id,
        )
    )
    db.commit()
    db.refresh(complaint)
    return complaint


@router.get("/complaints", response_model=list[ComplaintOut])
def list_complaints(
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return (
        db.query(Complaint)
        .order_by(Complaint.priority_score.desc(), Complaint.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/escalations", response_model=list[ComplaintOut])
def list_escalated(
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return (
        db.query(Complaint)
        .filter(Complaint.escalation_level > 0)
        .order_by(Complaint.escalation_level.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post("/escalations/run-now")
def trigger_escalation_check(db: Session = Depends(get_db)):
    """Manually trigger the escalation sweep — useful for testing without waiting for the scheduler."""
    count = run_escalation_check(db)
    return {"escalated_count": count}


@router.get("/departments")
def list_departments(
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return (
        db.query(Department)
        .order_by(Department.name)
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post("/departments", status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    category = payload.category.strip()
    if not name or not category:
        raise HTTPException(status_code=400, detail="Name and category are required")
    if db.query(Department).filter(Department.name == name).first():
        raise HTTPException(status_code=400, detail="Department already exists")
    department = Department(name=name, category=category)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


@router.put("/departments/{department_id}")
def update_department(
    department_id: int, payload: DepartmentUpdate, db: Session = Depends(get_db)
):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    if payload.name is not None:
        department.name = payload.name.strip()
    if payload.category is not None:
        department.category = payload.category.strip()
    if not department.name or not department.category:
        raise HTTPException(status_code=400, detail="Name and category are required")
    db.commit()
    db.refresh(department)
    return department


@router.delete("/departments/{department_id}")
def delete_department(department_id: int, db: Session = Depends(get_db)):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    db.query(Complaint).filter(Complaint.department_id == department_id).update(
        {Complaint.department_id: None}, synchronize_session=False
    )
    db.delete(department)
    db.commit()
    return {"message": "Department deleted"}
