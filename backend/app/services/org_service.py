"""Organisation rules: role / department-membership consistency and ticket codes."""

import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.roles import (
    MULTI_DEPARTMENT_ROLES,
    NO_DEPARTMENT_ROLES,
    SINGLE_DEPARTMENT_ROLES,
    canonical_role,
)
from app.models.department import Department
from app.models.department_membership import DepartmentMembership
from app.models.location import LOCATION_KINDS, Location
from app.models.user import User
from app.services import audit_service


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip() or "general"


def validate_membership_shape(role, department_ids: list[int]) -> list[int]:
    """Enforce: staff/dept_admin exactly one, hod at least one, student/super_admin none."""
    ids = list(dict.fromkeys(department_ids))  # de-duplicate, keep order
    r = canonical_role(role)
    if r in SINGLE_DEPARTMENT_ROLES and len(ids) != 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"A {r} must belong to exactly one department")
    if r in MULTI_DEPARTMENT_ROLES and len(ids) < 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "An HOD must belong to at least one department")
    if r in NO_DEPARTMENT_ROLES and ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"A {r} cannot have department memberships")
    return ids


def set_memberships(
    db: Session, *, target: User, department_ids: list[int], actor: User, reason: str | None = None
) -> list[int]:
    ids = validate_membership_shape(target.role, department_ids)
    if ids:
        found = {
            d.id for d in db.query(Department).filter(Department.id.in_(ids), Department.is_active.is_(True)).all()
        }
        missing = [i for i in ids if i not in found]
        if missing:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown or inactive department(s): {missing}")

    existing = db.query(DepartmentMembership).filter(DepartmentMembership.user_id == target.id).all()
    before = sorted(m.department_id for m in existing)
    for m in existing:
        if m.department_id not in ids:
            db.delete(m)
    for dept_id in ids:
        if dept_id not in before:
            db.add(DepartmentMembership(user_id=target.id, department_id=dept_id, created_by=actor.id))

    # Keep the legacy single-department pointer in sync so V1 code keeps working.
    target.department_id = ids[0] if len(ids) == 1 else None

    audit_service.record(
        db,
        actor=actor,
        action="memberships_changed",
        entity_type="user",
        entity_id=target.id,
        before={"department_ids": before},
        after={"department_ids": sorted(ids)},
        reason=reason,
    )
    return ids


def build_location_path(db: Session, parent_id: int | None, name: str) -> str:
    if parent_id is None:
        return name
    parent = db.query(Location).filter(Location.id == parent_id).first()
    if parent is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Parent location not found")
    return f"{parent.path} > {name}"


def validate_location_kind(kind: str) -> str:
    if kind not in LOCATION_KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"kind must be one of {list(LOCATION_KINDS)}")
    return kind
