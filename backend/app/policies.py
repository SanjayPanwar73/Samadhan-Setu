"""Object-level authorization rules.

Cross-department access answers 404 (not 403) so that the existence of another
department's data is never revealed.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.roles import has_role
from app.deps import Scope, load_scope
from app.models.user import User


def require_department_access(scope: Scope, department_id: int | None, what: str = "Resource") -> None:
    if not scope.can_access(department_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")


def staff_department_ids(db: Session, staff: User) -> frozenset:
    return load_scope(db, staff).department_ids


def assert_assignable_staff(db: Session, staff_id: int, department_id: int | None) -> User:
    """The assignment target must be an active ``staff`` user with a membership in the
    issue's department (Test D). Raises 403 with no side effects otherwise."""
    staff = db.query(User).filter(User.id == staff_id).first()
    if staff is None or not has_role(staff, "staff") or staff.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selected user is not an active staff member")
    if department_id is None or department_id not in staff_department_ids(db, staff):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Staff member does not belong to this complaint's department",
        )
    return staff
