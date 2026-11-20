"""pytest scaffold. A temporary file-based SQLite DB is used (file-based so later
concurrency tests are meaningful). AI models are never loaded: the TestClient is
created without running the app lifespan, and AI modules import their heavy
dependencies lazily."""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="samadhan-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-0123456789"
os.environ["SEED_DEMO_ACCOUNTS"] = "false"
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "uploads")

import hashlib
import re
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.ai.providers import Providers, set_providers

from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.department import Department
from app.models.department_membership import DepartmentMembership
from app.models.user import User, UserRole
from app import models as _models  # noqa: F401


_PASSWORD_HASH = hash_password("password123")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def fake_embed(text: str) -> np.ndarray:
    """Deterministic bag-of-words embedding: similar wording -> high cosine, no model download."""
    vec = np.zeros(128, dtype="float32")
    for tok in _tokens(text):
        vec[int(hashlib.md5(tok.encode()).hexdigest(), 16) % 128] += 1.0
    n = np.linalg.norm(vec)
    return vec / n if n else vec


def fake_classify(text: str, labels: list[str]) -> tuple[str, float]:
    words = set(_tokens(text))
    scored = [(len(words & set(_tokens(label))), label) for label in labels]
    best = max(scored)
    return best[1], (0.9 if best[0] > 0 else 0.1)


def fake_sentiment(text: str) -> tuple[str, float]:
    negative = any(w in text.lower() for w in ("broken", "not working", "sparking", "dirty"))
    return ("NEGATIVE", 0.8) if negative else ("POSITIVE", 0.6)


@pytest.fixture(autouse=True)
def fake_ai():
    set_providers(Providers(classify=fake_classify, embed=fake_embed, sentiment=fake_sentiment,
                            embedding_model_name="fake-bow"))
    yield
    set_providers(None)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    return TestClient(app)  # no `with`: skips lifespan (no model loading, no scheduler)


@pytest.fixture()
def depts(db):
    out = {}
    for code, name in [("WAT", "Water"), ("ELE", "Electricity"), ("ACC", "Accounts")]:
        d = Department(name=name, code=code, category=name.lower())
        db.add(d)
        db.flush()
        out[code] = d
    db.add(Department(name="Triage", code="TRI", category="triage", is_system=True))
    db.commit()
    return out


@pytest.fixture()
def make_user(db):
    counter = {"n": 0}

    def _make(role, dept_ids=(), **extra):
        counter["n"] += 1
        user = User(
            name=f"{role.value} {counter['n']}",
            email=f"{role.value}{counter['n']}@example.com",
            hashed_password=_PASSWORD_HASH,
            role=role,
            **extra,
        )
        db.add(user)
        db.flush()
        for dept_id in dept_ids:
            db.add(DepartmentMembership(user_id=user.id, department_id=dept_id))
        if len(dept_ids) == 1:
            user.department_id = dept_ids[0]
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture()
def auth():
    def _auth(user):
        token = create_access_token({"sub": str(user.id), "role": user.role.value})
        return {"Authorization": f"Bearer {token}"}

    return _auth


@pytest.fixture()
def world(db, depts, make_user):
    """A small campus: corridor with two water coolers and a switchboard, staff and admins per department."""
    from app.models.asset import Asset
    from app.models.category import Category
    from app.models.department import Department
    from app.models.location import Location

    cln = Department(name="Cleaning & Maintenance", code="CLN", category="cleaning")
    db.add(cln)
    db.flush()

    campus = Location(kind="campus", name="Main Campus", path="Main Campus")
    db.add(campus)
    db.flush()
    block = Location(parent_id=campus.id, kind="building", name="Main Block", path="Main Campus > Main Block")
    db.add(block)
    db.flush()
    c3 = Location(parent_id=block.id, kind="corridor", name="Corridor 3", path="Main Campus > Main Block > Corridor 3")
    c4 = Location(parent_id=block.id, kind="corridor", name="Corridor 4", path="Main Campus > Main Block > Corridor 4")
    db.add_all([c3, c4])
    db.flush()

    def cat(dept, name, sev, verify, hours=48, evidence=False):
        c = Category(department_id=dept.id, name=name, base_severity=sev, default_criticality=0.5,
                     impact_level=0.3, expected_resolution_hours=hours, requires_verification=verify,
                     requires_evidence=evidence)
        db.add(c)
        db.flush()
        return c

    cooler_cat = cat(depts["WAT"], "Water cooler not working", 0.4, True)
    hazard_cat = cat(depts["ELE"], "Electrical hazard sparking", 0.9, True, hours=4)
    bin_cat = cat(cln, "Dustbin garbage cleaning", 0.2, False, hours=24)

    def asset(dept, loc, typ, tag, crit=3):
        a = Asset(department_id=dept.id, location_id=loc.id, asset_type=typ, tag=tag, name=tag, criticality=crit)
        db.add(a)
        db.flush()
        return a

    cooler1 = asset(depts["WAT"], c3, "water_cooler", "WC-1")
    cooler2 = asset(depts["WAT"], c3, "water_cooler", "WC-2")
    board = asset(depts["ELE"], c3, "switchboard", "SB-1", 4)
    db.commit()

    users = SimpleNamespace(
        super=make_user(UserRole.super_admin),
        wat_admin=make_user(UserRole.dept_admin, [depts["WAT"].id]),
        wat_staff=make_user(UserRole.staff, [depts["WAT"].id]),
        wat_staff2=make_user(UserRole.staff, [depts["WAT"].id]),
        ele_admin=make_user(UserRole.dept_admin, [depts["ELE"].id]),
        ele_staff=make_user(UserRole.staff, [depts["ELE"].id]),
        cln_admin=make_user(UserRole.dept_admin, [cln.id]),
        cln_staff=make_user(UserRole.staff, [cln.id]),
        hod=make_user(UserRole.hod, [depts["WAT"].id, depts["ELE"].id]),
    )
    return SimpleNamespace(depts={**depts, "CLN": cln}, c3=c3, c4=c4, cooler_cat=cooler_cat, hazard_cat=hazard_cat,
                           bin_cat=bin_cat, cooler1=cooler1, cooler2=cooler2, board=board, **vars(users))


@pytest.fixture()
def students(make_user):
    counter = {"n": 0}

    def _make(n=1):
        out = []
        for _ in range(n):
            counter["n"] += 1
            out.append(make_user(UserRole.student, enrollment_no=f"ENR{counter['n']:05d}"))
        return out if n > 1 else out[0]

    return _make


@pytest.fixture()
def submit(client, auth):
    def _submit(student, world, *, asset=None, category=None, department=None, title="Water cooler is broken",
                description="The water cooler near the corridor is broken and not working", anonymous=False,
                location=None, expect=201, **extra):
        body = {"title": title, "description": description, "location_id": (location or world.c3).id,
                "is_anonymous": anonymous, **extra}
        if asset is not None:
            body["asset_id"] = asset.id
        if category is not None:
            body["category_id"] = category.id
            body["department_id"] = category.department_id
        elif department is not None:
            body["department_id"] = department.id
        r = client.post("/complaints", json=body, headers=auth(student))
        assert r.status_code == expect, r.text
        return r

    return _submit
