"""Seeds the V2 college structure: departments, categories, locations, assets, demo users.

Idempotent and additive; it never touches existing complaints. Run from backend/:
    python -m scripts.seed_org
The V1 demo seed (scripts/seed.py) was removed together with the V1 API.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.asset import Asset
from app.models.category import Category
from app.models.department import Department
from app.models.department_membership import DepartmentMembership
from app.models.location import Location
from app.models.ticket_counter import TicketCounter
from app.models.user import User, UserRole
from app.services import org_service
import app.models  # noqa: F401

# code, name, requires_verification_default, is_system
DEPARTMENTS = [
    ("WAT", "Water", True, False),
    ("ELE", "Electricity", True, False),
    ("CLN", "Cleaning & Maintenance", True, False),
    ("ACC", "Accounts", False, False),
    ("TRI", "Triage", False, True),
]

# dept code -> (name, severity, criticality, impact, expected_hours, verify, evidence)
CATEGORIES = {
    "WAT": [
        ("Water cooler / RO not working", 0.4, 0.5, 0.3, 48, True, True),
        ("No water supply", 0.6, 0.7, 0.5, 12, True, False),
        ("Leakage / pipe burst", 0.6, 0.5, 0.4, 24, True, True),
        ("Water quality", 0.7, 0.6, 0.4, 24, True, False),
    ],
    "ELE": [
        ("Power outage", 0.6, 0.7, 0.6, 8, True, False),
        ("Electrical hazard / sparking", 0.9, 0.8, 0.5, 4, True, True),
        ("Light / fan not working", 0.2, 0.3, 0.3, 48, True, True),
        ("Projector / lab equipment power", 0.4, 0.6, 0.7, 24, True, False),
    ],
    "CLN": [
        ("Washroom cleanliness", 0.4, 0.5, 0.3, 24, True, True),
        ("Dustbin / garbage", 0.2, 0.3, 0.2, 24, False, False),
        ("Broken furniture", 0.2, 0.3, 0.4, 72, True, True),
        ("Classroom maintenance", 0.3, 0.4, 0.6, 48, True, True),
    ],
    "ACC": [
        ("Fee receipt / payment issue", 0.3, 0.4, 0.6, 72, False, False),
        ("Scholarship query", 0.3, 0.4, 0.6, 120, False, False),
        ("Refund request", 0.3, 0.3, 0.4, 120, False, False),
    ],
    "TRI": [("Unclassified", 0.3, 0.3, 0.3, 48, False, False)],
}

# (kind, name, children)
LOCATIONS = ("campus", "Main Campus", [
    ("building", "Main Block", [
        ("wing", "Wing 1", [
            ("floor", "Floor 1", [("corridor", "Corridor 1", []), ("corridor", "Corridor 2", [])]),
            ("floor", "Floor 2", [("corridor", "Corridor 3", [])]),
        ]),
        ("wing", "Wing 2", [("floor", "Floor 1", [("corridor", "Corridor 1", [])])]),
    ]),
    ("building", "Admin Block", [("floor", "Ground Floor", [("room", "Accounts Office", [])])]),
])

# (dept, location path suffix, asset_type, tag, name, criticality)
ASSETS = [
    ("WAT", "Wing 1 > Floor 2 > Corridor 3", "water_cooler", "WC-W1-C3-01", "Water Cooler 1", 3),
    ("WAT", "Wing 1 > Floor 2 > Corridor 3", "water_cooler", "WC-W1-C3-02", "Water Cooler 2", 3),
    ("WAT", "Wing 1 > Floor 1 > Corridor 1", "ro_plant", "RO-W1-C1-01", "RO Plant", 4),
    ("ELE", "Wing 1 > Floor 2 > Corridor 3", "switchboard", "SB-W1-C3-01", "Switchboard", 4),
]

DEMO_PASSWORD = "password123"
# email, name, role, department codes, enrollment_no
DEMO_USERS = [
    ("student@example.com", "Demo Student", UserRole.student, [], "ENR0001"),
    ("water.staff@example.com", "Water Staff", UserRole.staff, ["WAT"], None),
    ("electric.staff@example.com", "Electricity Staff", UserRole.staff, ["ELE"], None),
    ("water.admin@example.com", "Water Dept Admin", UserRole.dept_admin, ["WAT"], None),
    ("electric.admin@example.com", "Electricity Dept Admin", UserRole.dept_admin, ["ELE"], None),
    ("hod@example.com", "Demo HOD", UserRole.hod, ["WAT", "ELE"], None),
    ("super@example.com", "Super Admin", UserRole.super_admin, [], None),
]


def _seed_locations(db, spec, parent=None):
    kind, name, children = spec
    loc = db.query(Location).filter(Location.parent_id == (parent.id if parent else None), Location.name == name).first()
    if not loc:
        loc = Location(parent_id=parent.id if parent else None, kind=kind, name=name,
                       path=org_service.build_location_path(db, parent.id if parent else None, name))
        db.add(loc)
        db.flush()
    for child in children:
        _seed_locations(db, child, loc)
    return loc


def seed_structure(db, sample_places: bool = True):
    """Departments, ticket counters, categories and (optionally) a sample campus with assets.
    Idempotent. Returns {code: Department}. The backfill passes sample_places=False."""
    depts = {}
    for code, name, verify, system in DEPARTMENTS:
        dept = db.query(Department).filter((Department.code == code) | (Department.name == name)).first()
        if not dept:
            dept = Department(name=name, code=code, requires_verification_default=verify, is_system=system)
            db.add(dept)
            db.flush()
        elif dept.code is None:
            dept.code = code
        depts[code] = dept
        if not db.query(TicketCounter).filter(TicketCounter.department_id == dept.id).first():
            db.add(TicketCounter(department_id=dept.id, next_value=1))

    for code, rows in CATEGORIES.items():
        for name, sev, crit, impact, hours, verify, evidence in rows:
            exists = db.query(Category).filter(
                Category.department_id == depts[code].id, Category.name == name).first()
            if not exists:
                db.add(Category(department_id=depts[code].id, name=name, base_severity=sev,
                                default_criticality=crit, impact_level=impact,
                                expected_resolution_hours=hours, requires_verification=verify,
                                requires_evidence=evidence))

    if not sample_places:
        db.flush()
        return depts
    root = _seed_locations(db, LOCATIONS)
    db.flush()
    for code, suffix, atype, tag, name, crit in ASSETS:
        loc = db.query(Location).filter(Location.path == f"{root.path} > Main Block > {suffix}").first()
        if loc and not db.query(Asset).filter(Asset.tag == tag).first():
            db.add(Asset(department_id=depts[code].id, location_id=loc.id, asset_type=atype,
                         tag=tag, name=name, criticality=crit))
    db.flush()
    return depts


def seed_demo_users(db, depts):
    for email, name, role, codes, enrollment in DEMO_USERS:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(name=name, email=email, hashed_password=hash_password(DEMO_PASSWORD),
                        role=role, enrollment_no=enrollment)
            db.add(user)
            db.flush()
        existing = {m.department_id for m in db.query(DepartmentMembership).filter(
            DepartmentMembership.user_id == user.id)}
        for code in codes:
            if depts[code].id not in existing:
                db.add(DepartmentMembership(user_id=user.id, department_id=depts[code].id))
        if len(codes) == 1:
            user.department_id = depts[codes[0]].id


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        depts = seed_structure(db)
        db.commit()
        if settings.SEED_DEMO_ACCOUNTS and settings.ENVIRONMENT != "production":
            seed_demo_users(db, depts)
            db.commit()
        print("V2 org structure seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
