"""Part 1 acceptance: org structure, department scope, Test D."""

from app.models.audit_event import AuditEvent
from app.models.user import UserRole


# ---------------------------------------------------------------- registration
def test_enrollment_no_unique_and_normalised(client):
    base = {"name": "S", "password": "password123"}
    r1 = client.post("/auth/register", json={**base, "email": "s1@example.com", "enrollment_no": " en001 "})
    assert r1.status_code == 201
    r2 = client.post("/auth/register", json={**base, "email": "s2@example.com", "enrollment_no": "EN001"})
    assert r2.status_code == 400


def test_email_domain_allow_list(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "ALLOWED_EMAIL_DOMAINS", ["college.edu"])
    body = {"name": "S", "password": "password123", "enrollment_no": "EN900"}
    assert client.post("/auth/register", json={**body, "email": "x@gmail.com"}).status_code == 400
    assert client.post("/auth/register", json={**body, "email": "x@college.edu"}).status_code == 201


def test_inactive_user_cannot_login_or_use_token(client, db, make_user, auth):
    user = make_user(UserRole.student, enrollment_no="E1")
    headers = auth(user)
    user.is_active = False
    db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401
    r = client.post("/auth/login", json={"email": user.email, "password": "password123"})
    assert r.status_code == 401


# ----------------------------------------------------------------------- scope
def test_me_returns_scope_from_db(client, db, depts, make_user, auth):
    hod = make_user(UserRole.hod, [depts["WAT"].id, depts["ELE"].id])
    me = client.get("/auth/me", headers=auth(hod)).json()
    assert me["is_global"] is False
    assert me["department_ids"] == sorted([depts["WAT"].id, depts["ELE"].id])


def test_super_admin_is_global(client, make_user, auth):
    me = client.get("/auth/me", headers=auth(make_user(UserRole.super_admin))).json()
    assert me["is_global"] is True


# ------------------------------------------------------------ role permissions
def test_only_super_admin_manages_org(client, make_user, depts, auth):
    for role in (UserRole.student, UserRole.staff, UserRole.dept_admin, UserRole.hod):
        ids = [depts["WAT"].id] if role in (UserRole.staff, UserRole.dept_admin, UserRole.hod) else []
        user = make_user(role, ids, **({"enrollment_no": "EX"} if role == UserRole.student else {}))
        assert client.get("/admin/org/users", headers=auth(user)).status_code == 403
        assert client.post("/admin/org/departments", json={"name": "Lab", "code": "LAB"},
                           headers=auth(user)).status_code == 403


def test_reference_data_hides_triage(client, depts, make_user, auth):
    student = make_user(UserRole.student, enrollment_no="E5")
    names = [d["name"] for d in client.get("/reference/departments", headers=auth(student)).json()]
    assert "Triage" not in names and {"Water", "Electricity"} <= set(names)


def test_reference_requires_auth(client):
    assert client.get("/reference/departments").status_code == 401


# ------------------------------------------------------- membership / role rules
def test_membership_shape_rules(client, depts, make_user, auth):
    sa = make_user(UserRole.super_admin)
    h = auth(sa)
    base = {"name": "N", "password": "password123"}
    two = [depts["WAT"].id, depts["ELE"].id]
    assert client.post("/admin/org/users", headers=h, json={**base, "email": "a@x.com", "role": "staff",
                                                            "department_ids": two}).status_code == 422
    assert client.post("/admin/org/users", headers=h, json={**base, "email": "b@x.com", "role": "staff",
                                                            "department_ids": []}).status_code == 422
    assert client.post("/admin/org/users", headers=h, json={**base, "email": "c@x.com", "role": "hod",
                                                            "department_ids": two}).status_code == 201
    assert client.post("/admin/org/users", headers=h, json={**base, "email": "d@x.com", "role": "hod",
                                                            "department_ids": []}).status_code == 422
    assert client.post("/admin/org/users", headers=h, json={**base, "email": "e@x.com", "role": "student",
                                                            "enrollment_no": "S9",
                                                            "department_ids": two[:1]}).status_code == 422
    assert client.post("/admin/org/users", headers=h, json={**base, "email": "f@x.com",
                                                            "role": "student"}).status_code == 422  # no enrollment


def test_staff_creation_syncs_legacy_department_id(client, db, depts, make_user, auth):
    h = auth(make_user(UserRole.super_admin))
    r = client.post("/admin/org/users", headers=h, json={
        "name": "W", "email": "w@x.com", "password": "password123", "role": "staff",
        "department_ids": [depts["WAT"].id]})
    assert r.status_code == 201 and r.json()["department_ids"] == [depts["WAT"].id]
    from app.models.user import User
    assert db.query(User).filter(User.email == "w@x.com").one().department_id == depts["WAT"].id


def test_cannot_change_own_role_or_memberships(client, make_user, auth):
    sa = make_user(UserRole.super_admin)
    h = auth(sa)
    assert client.patch(f"/admin/org/users/{sa.id}", headers=h,
                        json={"role": "student", "reason": "x"}).status_code == 409
    assert client.put(f"/admin/org/users/{sa.id}/memberships", headers=h,
                      json={"department_ids": []}).status_code == 409


def test_role_change_requires_reason_and_is_audited(client, db, depts, make_user, auth):
    sa = make_user(UserRole.super_admin)
    staff = make_user(UserRole.staff, [depts["WAT"].id])
    h = auth(sa)
    assert client.patch(f"/admin/org/users/{staff.id}", headers=h,
                        json={"role": "dept_admin"}).status_code == 422
    r = client.patch(f"/admin/org/users/{staff.id}", headers=h,
                     json={"role": "dept_admin", "reason": "promoted"})
    assert r.status_code == 200 and r.json()["role"] == "dept_admin"
    ev = db.query(AuditEvent).filter(AuditEvent.action == "user_updated").one()
    assert ev.actor_id == sa.id and ev.reason == "promoted"
    assert ev.before == {"role": "staff"} and ev.after == {"role": "dept_admin"}


def test_memberships_change_is_audited(client, db, depts, make_user, auth):
    sa = make_user(UserRole.super_admin)
    hod = make_user(UserRole.hod, [depts["WAT"].id])
    r = client.put(f"/admin/org/users/{hod.id}/memberships", headers=auth(sa),
                   json={"department_ids": [depts["WAT"].id, depts["ACC"].id], "reason": "added ACC"})
    assert r.status_code == 200
    ev = db.query(AuditEvent).filter(AuditEvent.action == "memberships_changed").one()
    assert ev.after == {"department_ids": sorted([depts["WAT"].id, depts["ACC"].id])}


# --------------------------------------------------------------- dept asset scope
def _location(client, h):
    c = client.post("/admin/org/locations", headers=h, json={"kind": "campus", "name": "Main"})
    assert c.status_code == 201
    b = client.post("/admin/org/locations", headers=h,
                    json={"kind": "building", "name": "Block A", "parent_id": c.json()["id"]})
    assert b.json()["path"] == "Main > Block A"
    return b.json()["id"]


def test_dept_admin_manages_only_own_department_assets(client, depts, make_user, auth):
    sa = make_user(UserRole.super_admin)
    loc = _location(client, auth(sa))
    wat_admin = make_user(UserRole.dept_admin, [depts["WAT"].id])
    payload = {"location_id": loc, "asset_type": "water_cooler", "tag": "WC-1", "name": "Cooler", "criticality": 3}
    assert client.post("/admin/org/assets", headers=auth(wat_admin),
                       json={**payload, "department_id": depts["WAT"].id}).status_code == 201
    # other department -> 404, existence is not revealed
    assert client.post("/admin/org/assets", headers=auth(wat_admin),
                       json={**payload, "tag": "EL-1", "department_id": depts["ELE"].id}).status_code == 404
    # duplicate tag -> 409
    assert client.post("/admin/org/assets", headers=auth(sa),
                       json={**payload, "department_id": depts["WAT"].id}).status_code == 409


def test_dept_admin_cannot_edit_other_department_asset(client, depts, make_user, auth):
    sa = make_user(UserRole.super_admin)
    loc = _location(client, auth(sa))
    a = client.post("/admin/org/assets", headers=auth(sa), json={
        "department_id": depts["ELE"].id, "location_id": loc, "asset_type": "switchboard",
        "tag": "SB-1", "name": "Board", "criticality": 4}).json()
    wat_admin = make_user(UserRole.dept_admin, [depts["WAT"].id])
    assert client.patch(f"/admin/org/assets/{a['id']}", headers=auth(wat_admin),
                        json={"is_active": False}).status_code == 404


def test_triage_cannot_be_deactivated(client, db, depts, make_user, auth):
    from app.models.department import Department
    triage = db.query(Department).filter(Department.is_system.is_(True)).one()
    r = client.patch(f"/admin/org/departments/{triage.id}", headers=auth(make_user(UserRole.super_admin)),
                     json={"is_active": False})
    assert r.status_code == 409


def test_role_change_and_departments_in_one_validated_step(client, db, depts, make_user, auth):
    sa = make_user(UserRole.super_admin)
    staff = make_user(UserRole.staff, [depts["WAT"].id])
    h = auth(sa)
    # staff -> student needs the department removed in the same call
    assert client.patch(f"/admin/org/users/{staff.id}", headers=h,
                        json={"role": "student", "reason": "left the team"}).status_code == 422
    r = client.patch(f"/admin/org/users/{staff.id}", headers=h,
                     json={"role": "hod", "department_ids": [depts["WAT"].id, depts["ELE"].id],
                           "reason": "promoted to head"})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "hod" and sorted(r.json()["department_ids"]) == sorted([depts["WAT"].id, depts["ELE"].id])
    r = client.patch(f"/admin/org/users/{staff.id}", headers=h,
                     json={"role": "super_admin", "department_ids": [], "reason": "org change"})
    assert r.status_code == 200 and r.json()["department_ids"] == []
