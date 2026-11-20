"""V2 organisation admin: departments, categories, locations, assets, users, memberships, audit.

Mounted at /admin/org so it does not collide with the V1 /admin/departments routes,
which are removed in Part 3. Deactivate instead of delete everywhere.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.roles import has_role, role_value
from app.core.security import hash_password
from app.deps import Scope, get_scope, require_role
from app.models.asset import Asset
from app.models.audit_event import AuditEvent
from app.models.category import Category
from app.models.department import Department
from app.models.department_membership import DepartmentMembership
from app.models.location import Location
from app.models.user import User
from app.policies import require_department_access
from app.schemas.org import (
    AdminUserCreate, AdminUserOut, AdminUserPatch, AssetIn, AssetOut, AssetPatch,
    AuditEventOut, CategoryIn, CategoryOut, CategoryPatch, DepartmentIn, DepartmentOut,
    DepartmentPatch, LocationIn, LocationOut, LocationPatch, MembershipsPut,
)
from app.services import audit_service, org_service

router = APIRouter(prefix="/admin/org", tags=["admin-org"])

super_admin_only = Depends(require_role("super_admin"))


def _snapshot(obj, fields):
    return {f: getattr(obj, f) for f in fields}


def _commit(db: Session, message: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, message)


# ----------------------------------------------------------------- departments
@router.get("/departments", response_model=list[DepartmentOut], dependencies=[super_admin_only])
def list_departments(db: Session = Depends(get_db)):
    return db.query(Department).order_by(Department.name).all()


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(
    payload: DepartmentIn, db: Session = Depends(get_db), actor: User = Depends(require_role("super_admin"))
):
    code = payload.code.upper()
    dept = Department(
        name=payload.name,
        code=code,
        requires_verification_default=payload.requires_verification_default,
    )
    db.add(dept)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Department name or code already exists")
    audit_service.record(db, actor=actor, action="department_created", entity_type="department",
                         entity_id=dept.id, after={"name": dept.name, "code": dept.code})
    _commit(db, "Department name or code already exists")
    db.refresh(dept)
    return dept


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: int, payload: DepartmentPatch, db: Session = Depends(get_db),
    actor: User = Depends(require_role("super_admin")),
):
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(404, "Department not found")
    fields = ["name", "is_active", "requires_verification_default"]
    before = _snapshot(dept, fields)
    changes = payload.model_dump(exclude_unset=True)
    if dept.is_system and changes.get("is_active") is False:
        raise HTTPException(409, "The Triage department cannot be deactivated")
    for key, value in changes.items():
        setattr(dept, key, value)
    audit_service.record(db, actor=actor, action="department_updated", entity_type="department",
                         entity_id=dept.id, before=before, after=_snapshot(dept, fields))
    _commit(db, "Department name already exists")
    db.refresh(dept)
    return dept


# ------------------------------------------------------------------ categories
@router.get("/categories", response_model=list[CategoryOut], dependencies=[super_admin_only])
def list_categories(department_id: int | None = Query(default=None, ge=1), db: Session = Depends(get_db)):
    q = db.query(Category)
    if department_id:
        q = q.filter(Category.department_id == department_id)
    return q.order_by(Category.department_id, Category.name).all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryIn, db: Session = Depends(get_db), actor: User = Depends(require_role("super_admin"))
):
    if not db.query(Department).filter(Department.id == payload.department_id).first():
        raise HTTPException(422, "Unknown department")
    cat = Category(**payload.model_dump())
    db.add(cat)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Category already exists in this department")
    audit_service.record(db, actor=actor, action="category_created", entity_type="category",
                         entity_id=cat.id, after=payload.model_dump())
    _commit(db, "Category already exists in this department")
    db.refresh(cat)
    return cat


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int, payload: CategoryPatch, db: Session = Depends(get_db),
    actor: User = Depends(require_role("super_admin")),
):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(404, "Category not found")
    changes = payload.model_dump(exclude_unset=True)
    before = {k: getattr(cat, k) for k in changes}
    for key, value in changes.items():
        setattr(cat, key, value)
    audit_service.record(db, actor=actor, action="category_updated", entity_type="category",
                         entity_id=cat.id, before=before, after=changes)
    _commit(db, "Category already exists in this department")
    db.refresh(cat)
    return cat


# ------------------------------------------------------------------- locations
@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(
    payload: LocationIn, db: Session = Depends(get_db), actor: User = Depends(require_role("super_admin"))
):
    org_service.validate_location_kind(payload.kind)
    loc = Location(
        parent_id=payload.parent_id,
        kind=payload.kind,
        name=payload.name,
        path=org_service.build_location_path(db, payload.parent_id, payload.name),
    )
    db.add(loc)
    db.flush()
    audit_service.record(db, actor=actor, action="location_created", entity_type="location",
                         entity_id=loc.id, after={"path": loc.path, "kind": loc.kind})
    db.commit()
    db.refresh(loc)
    return loc


@router.patch("/locations/{location_id}", response_model=LocationOut)
def update_location(
    location_id: int, payload: LocationPatch, db: Session = Depends(get_db),
    actor: User = Depends(require_role("super_admin")),
):
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(404, "Location not found")
    before = {"is_active": loc.is_active}
    loc.is_active = payload.is_active
    audit_service.record(db, actor=actor, action="location_updated", entity_type="location",
                         entity_id=loc.id, before=before, after={"is_active": loc.is_active})
    db.commit()
    db.refresh(loc)
    return loc


# ---------------------------------------------------------------------- assets
# super_admin manages all assets; dept_admin manages assets of their own department.
asset_manager = Depends(require_role("super_admin", "dept_admin"))


@router.get("/assets", response_model=list[AssetOut])
def list_assets(
    department_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    scope: Scope = Depends(get_scope),
    _: User = asset_manager,
):
    q = db.query(Asset)
    if not scope.is_global:
        q = q.filter(Asset.department_id.in_(scope.department_ids))
    if department_id:
        q = q.filter(Asset.department_id == department_id)
    return q.order_by(Asset.tag).offset(offset).limit(limit).all()


@router.post("/assets", response_model=AssetOut, status_code=201)
def create_asset(
    payload: AssetIn, db: Session = Depends(get_db), scope: Scope = Depends(get_scope),
    actor: User = asset_manager,
):
    require_department_access(scope, payload.department_id, "Department")
    if not db.query(Location).filter(Location.id == payload.location_id).first():
        raise HTTPException(422, "Unknown location")
    if not db.query(Department).filter(Department.id == payload.department_id).first():
        raise HTTPException(422, "Unknown department")
    asset = Asset(**payload.model_dump())
    db.add(asset)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Asset tag already exists")
    audit_service.record(db, actor=actor, action="asset_created", entity_type="asset",
                         entity_id=asset.id, after=payload.model_dump())
    _commit(db, "Asset tag already exists")
    db.refresh(asset)
    return asset


@router.patch("/assets/{asset_id}", response_model=AssetOut)
def update_asset(
    asset_id: int, payload: AssetPatch, db: Session = Depends(get_db),
    scope: Scope = Depends(get_scope), actor: User = asset_manager,
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    require_department_access(scope, asset.department_id, "Asset")
    changes = payload.model_dump(exclude_unset=True)
    if "location_id" in changes and not db.query(Location).filter(Location.id == changes["location_id"]).first():
        raise HTTPException(422, "Unknown location")
    before = {k: getattr(asset, k) for k in changes}
    for key, value in changes.items():
        setattr(asset, key, value)
    audit_service.record(db, actor=actor, action="asset_updated", entity_type="asset",
                         entity_id=asset.id, before=before, after=changes)
    db.commit()
    db.refresh(asset)
    return asset


# ----------------------------------------------------------------------- users
def _user_out(db: Session, user: User) -> AdminUserOut:
    ids = sorted(r.department_id for r in db.query(DepartmentMembership.department_id)
                 .filter(DepartmentMembership.user_id == user.id))
    return AdminUserOut(id=user.id, name=user.name, email=user.email, role=user.role,
                        enrollment_no=user.enrollment_no, is_active=user.is_active,
                        department_ids=ids)


@router.get("/users", response_model=list[AdminUserOut], dependencies=[super_admin_only])
def list_users(
    role: str | None = Query(default=None, max_length=20),
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    return [_user_out(db, u) for u in q.order_by(User.id).offset(offset).limit(limit).all()]


@router.post("/users", response_model=AdminUserOut, status_code=201)
def create_user(
    payload: AdminUserCreate, db: Session = Depends(get_db), actor: User = Depends(require_role("super_admin"))
):
    if role_value(payload.role) in ("student", "user") and not payload.enrollment_no:
        raise HTTPException(422, "Students need an enrollment number")
    org_service.validate_membership_shape(payload.role, payload.department_ids)
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(409, "Email already registered")
    if payload.enrollment_no and db.query(User).filter(User.enrollment_no == payload.enrollment_no).first():
        raise HTTPException(409, "Enrollment number already registered")
    user = User(name=payload.name, email=payload.email, hashed_password=hash_password(payload.password),
                role=payload.role, enrollment_no=payload.enrollment_no)
    db.add(user)
    db.flush()
    org_service.set_memberships(db, target=user, department_ids=payload.department_ids, actor=actor)
    audit_service.record(db, actor=actor, action="user_created", entity_type="user", entity_id=user.id,
                         after={"email": user.email, "role": role_value(user.role)})
    _commit(db, "Email or enrollment number already registered")
    db.refresh(user)
    return _user_out(db, user)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int, payload: AdminUserPatch, db: Session = Depends(get_db),
    actor: User = Depends(require_role("super_admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    changes = payload.model_dump(exclude_unset=True, exclude={"reason", "department_ids"})
    if user.id == actor.id and ("role" in changes or payload.department_ids is not None
                                or changes.get("is_active") is False):
        raise HTTPException(409, "You cannot change your own role, departments or deactivate yourself")
    if "role" in changes and changes["role"] != user.role:
        if not payload.reason:
            raise HTTPException(422, "A reason is required to change a role")
        # The departments after the change must fit the new role.
        current = [r.department_id for r in db.query(DepartmentMembership.department_id)
                   .filter(DepartmentMembership.user_id == user.id)]
        org_service.validate_membership_shape(
            changes["role"], payload.department_ids if payload.department_ids is not None else current)
    elif payload.department_ids is not None:
        org_service.validate_membership_shape(user.role, payload.department_ids)
    before = {k: (role_value(getattr(user, k)) if k == "role" else getattr(user, k)) for k in changes}
    for key, value in changes.items():
        setattr(user, key, value)
    after = {k: (role_value(v) if k == "role" else v) for k, v in changes.items()}
    if changes:
        audit_service.record(db, actor=actor, action="user_updated", entity_type="user", entity_id=user.id,
                             before=before, after=after, reason=payload.reason)
    if payload.department_ids is not None:
        org_service.set_memberships(db, target=user, department_ids=payload.department_ids,
                                    actor=actor, reason=payload.reason)
    db.commit()
    db.refresh(user)
    return _user_out(db, user)


@router.put("/users/{user_id}/memberships", response_model=AdminUserOut)
def put_memberships(
    user_id: int, payload: MembershipsPut, db: Session = Depends(get_db),
    actor: User = Depends(require_role("super_admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == actor.id:
        raise HTTPException(409, "You cannot change your own memberships")
    org_service.set_memberships(db, target=user, department_ids=payload.department_ids,
                                actor=actor, reason=payload.reason)
    db.commit()
    return _user_out(db, user)


# ----------------------------------------------------------------------- audit
@router.get("/audit", response_model=list[AuditEventOut])
def audit_log(
    entity_type: str | None = Query(default=None, max_length=40),
    entity_id: int | None = Query(default=None, ge=1),
    actor_id: int | None = Query(default=None, ge=1),
    issue_id: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_role("super_admin")),
):
    q = db.query(AuditEvent)
    if entity_type:
        q = q.filter(AuditEvent.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditEvent.entity_id == entity_id)
    if actor_id:
        q = q.filter(AuditEvent.actor_id == actor_id)
    if issue_id:
        q = q.filter(AuditEvent.issue_id == issue_id)
    return q.order_by(AuditEvent.id.desc()).offset(offset).limit(limit).all()
