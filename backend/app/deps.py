from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.roles import LEGACY_GLOBAL_ROLES, has_role, role_value
from app.models.department_membership import DepartmentMembership
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if isinstance(user_id, bool) or not isinstance(user_id, (str, int)):
        raise credentials_exception
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise credentials_exception
    if user_id <= 0:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.is_active is False:
        raise credentials_exception
    return user


def require_role(*roles: str):
    """Usage: Depends(require_role("admin", "management")).

    V1 and V2 role names are interchangeable (user=student, admin=super_admin,
    management=hod), so existing V1 routes keep working for migrated accounts.
    """

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_role(current_user, *roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return role_checker


@dataclass(frozen=True)
class Scope:
    """Department scope of the caller, always re-read from the database (never from the JWT)."""

    user_id: int
    is_global: bool
    department_ids: frozenset

    def can_access(self, department_id: int | None) -> bool:
        if self.is_global:
            return True
        return department_id is not None and department_id in self.department_ids


def load_scope(db: Session, user: User) -> Scope:
    # super_admin is global. Legacy V1 admin/management were global too and stay
    # so until the backfill gives them explicit roles and memberships.
    if has_role(user, "super_admin") or role_value(user.role) in LEGACY_GLOBAL_ROLES:
        return Scope(user.id, True, frozenset())

    ids = {
        row.department_id
        for row in db.query(DepartmentMembership.department_id).filter(
            DepartmentMembership.user_id == user.id
        )
    }
    # Pre-backfill fallback for staff created by V1 with only users.department_id.
    if not ids and user.department_id is not None and has_role(user, "staff", "dept_admin"):
        ids.add(user.department_id)
    return Scope(user.id, False, frozenset(ids))


def get_scope(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Scope:
    return load_scope(db, current_user)
