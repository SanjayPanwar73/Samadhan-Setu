from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.complaint import Complaint
from app.models.complaint_history import ComplaintHistory
from app.models.department import Department
from app.models.user import User, UserRole
from app.schemas.complaint import ComplaintAssignment, ComplaintOut
from app.services.escalation_service import run_escalation_check

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])


class DepartmentCreate(BaseModel):
    name: str
    category: str


class DepartmentUpdate(BaseModel):
    name: str | None = None
    category: str | None = None


@router.get("/staff")
def list_staff(db: Session = Depends(get_db)):
    staff = (
        db.query(User)
        .filter(User.role == UserRole.staff)
        .order_by(User.name)
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
def list_complaints(db: Session = Depends(get_db)):
    return (
        db.query(Complaint)
        .order_by(Complaint.priority_score.desc(), Complaint.created_at.desc())
        .all()
    )


@router.get("/escalations", response_model=list[ComplaintOut])
def list_escalated(db: Session = Depends(get_db)):
    return (
        db.query(Complaint)
        .filter(Complaint.escalation_level > 0)
        .order_by(Complaint.escalation_level.desc())
        .all()
    )


@router.post("/escalations/run-now")
def trigger_escalation_check(db: Session = Depends(get_db)):
    """Manually trigger the escalation sweep — useful for testing without waiting for the scheduler."""
    count = run_escalation_check(db)
    return {"escalated_count": count}


@router.get("/departments")
def list_departments(db: Session = Depends(get_db)):
    return db.query(Department).order_by(Department.name).all()


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
