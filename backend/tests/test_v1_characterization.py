"""Auth behaviour that must keep working after V1 removal."""

from app.models.user import UserRole

BODY = {"name": "A", "email": "A@Example.com", "password": "password123", "enrollment_no": "en100"}


def test_register_login_me_roundtrip(client):
    r = client.post("/auth/register", json=BODY)
    assert r.status_code == 201
    assert r.json()["role"] == "student"
    login = client.post("/auth/login", json={"email": "a@example.com", "password": "password123"})
    assert login.status_code == 200
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}).json()
    assert me["email"] == "a@example.com" and me["enrollment_no"] == "EN100" and me["needs_enrollment_no"] is False


def test_register_requires_enrollment_number(client):
    body = {k: v for k, v in BODY.items() if k != "enrollment_no"}
    assert client.post("/auth/register", json=body).status_code == 422


def test_register_cannot_choose_role(client):
    r = client.post("/auth/register", json={**BODY, "role": "super_admin"})
    assert r.status_code == 422


def test_duplicate_email_rejected(client):
    assert client.post("/auth/register", json=BODY).status_code == 201
    assert client.post("/auth/register", json={**BODY, "enrollment_no": "EN200"}).status_code == 400


def test_wrong_password_401(client):
    client.post("/auth/register", json=BODY)
    r = client.post("/auth/login", json={"email": "a@example.com", "password": "nope-nope-1"})
    assert r.status_code == 401


def test_v1_routes_are_gone(client, make_user, auth):
    admin = make_user(UserRole.super_admin)
    for path in ("/admin/departments", "/management/summary", "/complaints/assigned"):
        assert client.get(path, headers=auth(admin)).status_code in (404, 405, 422)


def test_migrated_student_is_prompted_for_enrollment_once(client, db, make_user, auth):
    s = make_user(UserRole.student)             # as left by the backfill: no enrollment number
    assert client.get("/auth/me", headers=auth(s)).json()["needs_enrollment_no"] is True
    r = client.patch("/auth/me/enrollment", json={"enrollment_no": " en555 "}, headers=auth(s))
    assert r.status_code == 200 and r.json()["enrollment_no"] == "EN555" and r.json()["needs_enrollment_no"] is False
    assert client.patch("/auth/me/enrollment", json={"enrollment_no": "EN556"}, headers=auth(s)).status_code == 409
    other = make_user(UserRole.student)
    assert client.patch("/auth/me/enrollment", json={"enrollment_no": "EN555"}, headers=auth(other)).status_code == 400
    staff = make_user(UserRole.staff)
    assert client.patch("/auth/me/enrollment", json={"enrollment_no": "EN777"}, headers=auth(staff)).status_code == 403
