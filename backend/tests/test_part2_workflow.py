"""Part 2 acceptance tests D(v2), E, F, G, H, I, J and supporting checks."""

import json

import pytest

from app.models.audit_event import AuditEvent
from app.models.complaint import Complaint
from app.models.events import DomainEvent, IdentityAccessLog, Notification
from app.models.issue import Issue
from app.models.priority import EscalationEvent
from app.models.work import Assignment
from app.services import issue_service, notification_service, sla_service

REPORT = {"what_was_wrong": "Compressor failed", "action_taken": "Replaced compressor",
          "public_summary": "The cooler was repaired."}


def _only_issue(db):
    return db.query(Issue).one()


def _assign(client, auth, admin, issue_id, staff):
    r = client.post(f"/issues/{issue_id}/assignments", json={"staff_ids": [staff.id]}, headers=auth(admin))
    assert r.status_code == 201, r.text
    return r.json()[0]["id"]


def _work(client, auth, staff, task_id, report=REPORT):
    assert client.post(f"/tasks/{task_id}/acknowledge", headers=auth(staff)).status_code == 200
    assert client.post(f"/tasks/{task_id}/start", headers=auth(staff)).status_code == 200
    r = client.post(f"/tasks/{task_id}/resolve", json=report, headers=auth(staff))
    assert r.status_code == 201, r.text
    return r.json()


def _resolve_issue(client, auth, db, issue, admin, staff, verify=True):
    task = _assign(client, auth, admin, issue.id, staff)
    out = _work(client, auth, staff, task)
    if verify:
        r = client.post(f"/resolutions/{out['resolution_id']}/approve", json={}, headers=auth(admin))
        assert r.status_code == 200, r.text
    db.expire_all()
    return task, out


# ------------------------------------------------------------------ Test D (V2)
def test_D_cross_department_assignment_and_access_blocked(client, db, world, students, submit, auth):
    submit(students(), world, asset=world.cooler1, category=world.cooler_cat)
    issue = _only_issue(db)
    r = client.post(f"/issues/{issue.id}/assignments", json={"staff_ids": [world.ele_staff.id]},
                    headers=auth(world.wat_admin))
    assert r.status_code == 403
    assert db.query(Assignment).count() == 0
    assert client.get(f"/issues/{issue.id}", headers=auth(world.ele_admin)).status_code == 404  # not 403
    assert client.get(f"/issues/{issue.id}", headers=auth(world.wat_admin)).status_code == 200


def test_roles_cannot_use_other_roles_endpoints(client, db, world, students, submit, auth):
    s = students()
    submit(s, world, asset=world.cooler1, category=world.cooler_cat)
    issue = _only_issue(db)
    assert client.get("/issues", headers=auth(world.wat_staff)).status_code == 403
    assert client.get("/issues", headers=auth(s)).status_code == 403
    assert client.post(f"/issues/{issue.id}/assignments", json={"staff_ids": [world.wat_staff.id]},
                       headers=auth(s)).status_code == 403
    assert client.get("/tasks", headers=auth(world.wat_admin)).status_code == 403
    # HOD is read-only and never sees individual complaints
    assert client.get(f"/issues/{issue.id}", headers=auth(world.hod)).status_code == 200
    assert client.get(f"/issues/{issue.id}/complaints", headers=auth(world.hod)).status_code == 403
    assert client.post(f"/issues/{issue.id}/assignments", json={"staff_ids": [world.wat_staff.id]},
                       headers=auth(world.hod)).status_code == 403


# ------------------------------------------------------------------------ Test E
def test_E_full_lifecycle_with_audit_and_illegal_jumps(client, db, world, students, submit, auth):
    submit(students(), world, asset=world.cooler1, category=world.cooler_cat)
    issue = _only_issue(db)
    task = _assign(client, auth, world.wat_admin, issue.id, world.wat_staff)
    db.expire_all()
    assert db.get(Issue, issue.id).status == "assigned"

    # illegal order of operations -> 409
    assert client.post(f"/tasks/{task}/start", headers=auth(world.wat_staff)).status_code == 409
    assert client.post(f"/tasks/{task}/resolve", json=REPORT, headers=auth(world.wat_staff)).status_code == 409

    assert client.post(f"/tasks/{task}/acknowledge", headers=auth(world.wat_staff)).status_code == 200
    assert client.post(f"/tasks/{task}/start", headers=auth(world.wat_staff)).status_code == 200
    # another staff member cannot touch this task, and does not learn it exists
    assert client.get(f"/tasks/{task}", headers=auth(world.wat_staff2)).status_code == 404
    assert client.get(f"/tasks/{task}", headers=auth(world.ele_staff)).status_code == 404

    # missing required fields are rejected
    bad = client.post(f"/tasks/{task}/resolve", json={"notes": "done"}, headers=auth(world.wat_staff))
    assert bad.status_code == 422 and bad.json()["code"] == "missing_fields"

    out = client.post(f"/tasks/{task}/resolve", json=REPORT, headers=auth(world.wat_staff)).json()
    assert out["issue_status"] == "awaiting_verification" and out["report_status"] == "submitted"

    # staff cannot approve their own work
    assert client.post(f"/resolutions/{out['resolution_id']}/approve", json={},
                       headers=auth(world.wat_staff)).status_code == 403
    assert client.post(f"/resolutions/{out['resolution_id']}/approve", json={},
                       headers=auth(world.ele_admin)).status_code == 404
    assert client.post(f"/resolutions/{out['resolution_id']}/approve", json={},
                       headers=auth(world.wat_admin)).status_code == 200
    # approving twice, or rejecting a resolved issue, is an invalid transition
    assert client.post(f"/resolutions/{out['resolution_id']}/approve", json={},
                       headers=auth(world.wat_admin)).status_code == 409
    assert client.post(f"/issues/{issue.id}/reject", json={"reason": "invalid report"},
                       headers=auth(world.wat_admin)).status_code == 409

    db.expire_all()
    assert db.get(Issue, issue.id).status == "resolved"
    a = db.get(Assignment, task)
    assert a.status == "completed"
    assert a.assigned_at <= a.acknowledged_at <= a.started_at <= a.completed_at

    changes = [(e.before["status"], e.after["status"]) for e in
               db.query(AuditEvent).filter(AuditEvent.issue_id == issue.id, AuditEvent.action == "status_changed")
               .order_by(AuditEvent.id)]
    assert changes == [("open", "assigned"), ("assigned", "in_progress"),
                       ("in_progress", "awaiting_verification"), ("awaiting_verification", "resolved")]
    actions = {e.action for e in db.query(AuditEvent).filter(AuditEvent.issue_id == issue.id)}
    assert {"assignment_created", "task_acknowledged", "task_started", "resolution_submitted",
            "resolution_approved"} <= actions


def test_rejected_resolution_returns_to_in_progress(client, db, world, students, submit, auth):
    submit(students(), world, asset=world.cooler1, category=world.cooler_cat)
    issue = _only_issue(db)
    task = _assign(client, auth, world.wat_admin, issue.id, world.wat_staff)
    out = _work(client, auth, world.wat_staff, task)
    r = client.post(f"/resolutions/{out['resolution_id']}/reject", json={"comment": "No photo of the fix"},
                    headers=auth(world.wat_admin))
    assert r.status_code == 200
    db.expire_all()
    assert db.get(Issue, issue.id).status == "in_progress"
    assert db.get(Assignment, task).status == "in_progress"
    # a rejection must carry a comment
    out2 = client.post(f"/tasks/{task}/resolve", json=REPORT, headers=auth(world.wat_staff)).json()
    assert client.post(f"/resolutions/{out2['resolution_id']}/reject", json={"comment": ""},
                       headers=auth(world.wat_admin)).status_code == 422


def test_only_lead_can_submit_and_updates_are_recorded(client, db, world, students, submit, auth):
    submit(students(), world, asset=world.cooler1, category=world.cooler_cat)
    issue = _only_issue(db)
    r = client.post(f"/issues/{issue.id}/assignments", headers=auth(world.wat_admin),
                    json={"staff_ids": [world.wat_staff.id, world.wat_staff2.id]})
    lead, second = r.json()[0], r.json()[1]
    assert lead["is_lead"] and not second["is_lead"]
    for task, staff in ((lead["id"], world.wat_staff), (second["id"], world.wat_staff2)):
        client.post(f"/tasks/{task}/acknowledge", headers=auth(staff))
        client.post(f"/tasks/{task}/start", headers=auth(staff))
    assert client.post(f"/tasks/{second['id']}/resolve", json=REPORT,
                       headers=auth(world.wat_staff2)).status_code == 403
    assert client.post(f"/tasks/{second['id']}/updates", json={"kind": "blocker", "body": "Need a spare part"},
                       headers=auth(world.wat_staff2)).status_code == 201
    assert client.post(f"/tasks/{lead['id']}/resolve", json=REPORT,
                       headers=auth(world.wat_staff)).status_code == 201
    detail = client.get(f"/tasks/{second['id']}", headers=auth(world.wat_staff2)).json()
    assert detail["updates"][0]["kind"] == "blocker"


def test_reassignment_request_and_admin_reassign(client, db, world, students, submit, auth):
    submit(students(), world, asset=world.cooler1, category=world.cooler_cat)
    issue = _only_issue(db)
    task = _assign(client, auth, world.wat_admin, issue.id, world.wat_staff)
    r = client.post(f"/tasks/{task}/request-reassignment", json={"reason": "I am on leave tomorrow"},
                    headers=auth(world.wat_staff))
    assert r.status_code == 200 and r.json()["reassign_requested"] is True
    # an electricity staff member is not a valid target; a water colleague is
    assert client.patch(f"/assignments/{task}", json={"staff_id": world.ele_staff.id},
                        headers=auth(world.wat_admin)).status_code == 403
    r = client.patch(f"/assignments/{task}", json={"staff_id": world.wat_staff2.id}, headers=auth(world.wat_admin))
    assert r.status_code == 200 and r.json()["staff_id"] == world.wat_staff2.id and r.json()["is_lead"]
    db.expire_all()
    assert db.get(Assignment, task).status == "reassigned"
    assert client.get("/tasks", headers=auth(world.wat_staff)).json()[0]["status"] == "reassigned"


def test_duplicate_assignment_is_a_noop(client, db, world, students, submit, auth):
    submit(students(), world, asset=world.cooler1, category=world.cooler_cat)
    issue = _only_issue(db)
    a = _assign(client, auth, world.wat_admin, issue.id, world.wat_staff)
    b = _assign(client, auth, world.wat_admin, issue.id, world.wat_staff)
    assert a == b and db.query(Assignment).count() == 1


def test_evidence_required_categories_need_an_attachment(client, db, world, students, submit, auth):
    world.cooler_cat.requires_evidence = True
    db.commit()
    submit(students(), world, asset=world.cooler1, category=world.cooler_cat)
    issue = _only_issue(db)
    task = _assign(client, auth, world.wat_admin, issue.id, world.wat_staff)
    client.post(f"/tasks/{task}/acknowledge", headers=auth(world.wat_staff))
    client.post(f"/tasks/{task}/start", headers=auth(world.wat_staff))
    r = client.post(f"/tasks/{task}/resolve", json=REPORT, headers=auth(world.wat_staff))
    assert r.status_code == 422 and r.json()["code"] == "evidence_required"
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    up = client.post(f"/tasks/{task}/attachments", headers=auth(world.wat_staff),
                     files={"file": ("fix.png", png, "image/png")})
    assert up.status_code == 201
    assert client.post(f"/tasks/{task}/resolve", json=REPORT, headers=auth(world.wat_staff)).status_code == 201


def test_attachment_content_is_validated(client, db, world, students, submit, auth, tmp_path, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    s = students()
    cid = submit(s, world, asset=world.cooler1, category=world.cooler_cat).json()["complaint_id"]
    # declared as PNG but the bytes are not -> rejected
    fake = client.post(f"/complaints/{cid}/attachments", headers=auth(s),
                       files={"file": ("a.png", b"<script>alert(1)</script>", "image/png")})
    assert fake.status_code == 415
    exe = client.post(f"/complaints/{cid}/attachments", headers=auth(s),
                      files={"file": ("a.exe", b"MZ....", "application/octet-stream")})
    assert exe.status_code == 415
    ok = client.post(f"/complaints/{cid}/attachments", headers=auth(s),
                     files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert ok.status_code == 201
    att = ok.json()["id"]
    assert client.get(f"/attachments/{att}", headers=auth(s)).status_code == 200
    other = students()
    assert client.get(f"/attachments/{att}", headers=auth(other)).status_code == 404
    assert client.get(f"/attachments/{att}", headers=auth(world.ele_admin)).status_code == 404
    assert client.get(f"/attachments/{att}", headers=auth(world.wat_admin)).status_code == 200


# ------------------------------------------------------------------------ Test F
def test_F_resolving_shared_issue_notifies_each_complainant_privately(client, db, world, students, submit, auth):
    people = students(12)
    for s in people:
        submit(s, world, asset=world.cooler1, category=world.cooler_cat)
    issue = _only_issue(db)
    _resolve_issue(client, auth, db, issue, world.wat_admin, world.wat_staff)
    notification_service.dispatch_pending()

    mine = {c.created_by: c.id for c in db.query(Complaint).all()}
    for s in people:
        rows = db.query(Notification).filter(Notification.recipient_id == s.id,
                                             Notification.type == "resolution_approved").all()
        assert len(rows) == 1
        n = rows[0]
        assert n.complaint_id == mine[s.id]
        assert "The cooler was repaired." in n.body
        blob = json.dumps({"p": n.payload, "t": n.title, "b": n.body}).lower()
        for other in people:
            if other.id != s.id:
                assert other.email.lower() not in blob and other.enrollment_no.lower() not in blob
        assert set(n.payload) <= notification_service.ALLOWED_PAYLOAD_KEYS


def test_dispatch_is_idempotent(db, client, world, students, submit):
    submit(students(), world, asset=world.cooler1, category=world.cooler_cat)
    notification_service.dispatch_pending()
    before = db.query(Notification).count()
    # replay every event: dedupe keys prevent duplicates
    for e in db.query(DomainEvent).all():
        e.processed_at, e.attempts = None, 0
    db.commit()
    notification_service.dispatch_pending()
    db.expire_all()
    assert db.query(Notification).count() == before


# ------------------------------------------------------------------------ Test G
def test_G_independent_feedback_per_complainant(client, db, world, students, submit, auth):
    people = students(3)
    for s in people:
        submit(s, world, asset=world.cooler1, category=world.cooler_cat)
    issue = _only_issue(db)
    _resolve_issue(client, auth, db, issue, world.wat_admin, world.wat_staff)
    cids = {c.created_by: c.id for c in db.query(Complaint).all()}

    for s, rating in zip(people, (5, 3, 4)):
        r = client.post(f"/complaints/{cids[s.id]}/feedback", headers=auth(s),
                        json={"rating": rating, "resolved_for_me": True})
        assert r.status_code == 201, r.text
    dup = client.post(f"/complaints/{cids[people[0].id]}/feedback", headers=auth(people[0]),
                      json={"rating": 1, "resolved_for_me": False})
    assert dup.status_code == 409 and dup.json()["code"] == "duplicate_feedback"
    # a student cannot answer for someone else's complaint
    assert client.post(f"/complaints/{cids[people[1].id]}/feedback", headers=auth(people[0]),
                       json={"rating": 5, "resolved_for_me": True}).status_code == 404

    stats = client.get("/reports/satisfaction", headers=auth(world.wat_admin)).json()
    assert stats["responses"] == 3 and stats["avg_rating"] == 4.0 and stats["satisfaction_rate"] == 1.0
    assert client.get("/reports/satisfaction", headers=auth(people[0])).status_code == 403
    # students see their own feedback state only
    mine = client.get(f"/complaints/{cids[people[0].id]}", headers=auth(people[0])).json()
    assert mine["feedback_state"] == "submitted"


def test_feedback_only_while_resolved(client, db, world, students, submit, auth):
    s = students()
    cid = submit(s, world, asset=world.cooler1, category=world.cooler_cat).json()["complaint_id"]
    r = client.post(f"/complaints/{cid}/feedback", headers=auth(s), json={"rating": 5, "resolved_for_me": True})
    assert r.status_code == 409 and r.json()["code"] == "feedback_closed"


# ------------------------------------------------------------------------ Test H
def test_H_anonymous_complaint_never_exposes_identity(client, db, world, students, submit, auth):
    s = students()
    text = f"The cooler is broken. Contact me {s.email} or enrollment {s.enrollment_no} please"
    r = submit(s, world, asset=world.cooler1, category=world.cooler_cat, anonymous=True, description=text)
    assert r.json()["pii_redacted"] is True
    cid = r.json()["complaint_id"]
    stored = db.get(Complaint, cid)
    assert s.email not in stored.description and s.enrollment_no not in stored.description
    assert stored.created_by == s.id and stored.anon_code.startswith("ANON-")  # internal record is kept

    issue = _only_issue(db)
    task = _assign(client, auth, world.wat_admin, issue.id, world.wat_staff)
    secrets_ = [s.email.lower(), s.enrollment_no.lower(), s.name.lower()]

    def clean(resp):
        blob = resp.text.lower()
        assert resp.status_code == 200, resp.text
        for secret in secrets_:
            assert secret not in blob, secret

    clean(client.get(f"/tasks/{task}", headers=auth(world.wat_staff)))
    clean(client.get(f"/complaints/{cid}", headers=auth(world.wat_staff)))
    clean(client.get(f"/issues/{issue.id}/complaints", headers=auth(world.wat_admin)))
    clean(client.get(f"/complaints/{cid}", headers=auth(world.wat_admin)))
    clean(client.get(f"/issues/{issue.id}", headers=auth(world.hod)))
    clean(client.get(f"/issues/{issue.id}/history", headers=auth(world.wat_admin)))
    clean(client.get("/issues", headers=auth(world.hod)))
    admin_row = client.get(f"/issues/{issue.id}/complaints", headers=auth(world.wat_admin)).json()[0]
    assert admin_row["submitter_name"] is None and admin_row["anon_code"] == stored.anon_code

    notification_service.dispatch_pending()
    for n in db.query(Notification).filter(Notification.recipient_id != s.id):
        blob = json.dumps({"t": n.title, "b": n.body, "p": n.payload}).lower()
        for secret in secrets_:
            assert secret not in blob

    # revealing the identity: super admin only, with a real reason, and it is logged
    url = f"/admin/complaints/{cid}/reveal-identity"
    assert client.post(url, json={"reason": "legitimate safety review"}, headers=auth(world.wat_admin)).status_code == 403
    assert client.post(url, json={"reason": "short"}, headers=auth(world.super)).status_code == 422
    ok = client.post(url, json={"reason": "legitimate safety review"}, headers=auth(world.super))
    assert ok.status_code == 200 and ok.json()["email"] == s.email
    assert db.query(IdentityAccessLog).filter(IdentityAccessLog.complaint_id == cid).count() == 1
    assert db.query(AuditEvent).filter(AuditEvent.action == "identity_revealed").count() == 1


def test_H_identified_complaint_shows_name_to_dept_admin_only(client, db, world, students, submit, auth):
    s = students()
    cid = submit(s, world, asset=world.cooler1, category=world.cooler_cat).json()["complaint_id"]
    issue = _only_issue(db)
    task = _assign(client, auth, world.wat_admin, issue.id, world.wat_staff)
    admin_row = client.get(f"/issues/{issue.id}/complaints", headers=auth(world.wat_admin)).json()[0]
    assert admin_row["submitter_name"] == s.name
    assert s.email not in json.dumps(admin_row) and s.enrollment_no not in json.dumps(admin_row)
    staff_blob = client.get(f"/tasks/{task}", headers=auth(world.wat_staff)).text
    assert s.name not in staff_blob


def test_H_privacy_lint_view_models_have_no_identity_fields():
    from app.schemas.v2 import ComplaintAdminView, ComplaintStaffView, NotificationOut
    forbidden = {"email", "enrollment_no", "created_by", "user_id", "hashed_password", "password"}
    assert not forbidden & set(ComplaintAdminView.model_fields)
    assert not forbidden & set(NotificationOut.model_fields)
    assert not (forbidden | {"submitter_name", "anon_code", "is_anonymous"}) & set(ComplaintStaffView.model_fields)
    assert not forbidden & notification_service.ALLOWED_PAYLOAD_KEYS


def test_notification_payload_filter_drops_unknown_keys():
    assert notification_service.safe_payload({"ticket_no": "WAT-001", "email": "x@y.z", "name": "A"}) \
        == {"ticket_no": "WAT-001"}


def test_students_cannot_read_other_students_complaints(client, db, world, students, submit, auth):
    a, b = students(2)
    ca = submit(a, world, asset=world.cooler1, category=world.cooler_cat).json()["complaint_id"]
    submit(b, world, asset=world.cooler1, category=world.cooler_cat)
    assert client.get(f"/complaints/{ca}", headers=auth(b)).status_code == 404
    assert client.get(f"/complaints/{ca}/timeline", headers=auth(b)).status_code == 404
    mine = client.get("/complaints/me", headers=auth(b)).json()
    assert len(mine) == 1 and mine[0]["id"] != ca
    # fewer than K_ANON_MIN reporters: no exact count is disclosed
    assert "2" not in mine[0]["shared_message"]
    tl = client.get(f"/complaints/{mine[0]['id']}/timeline", headers=auth(b)).json()
    assert len(tl) == 1 and tl[0]["label"] == "Complaint received"


# ------------------------------------------------------------------------ Test I
def test_I_safety_hazard_is_critical_but_volume_alone_is_not(client, db, world, students, submit, auth):
    submit(students(), world, asset=world.board, category=world.hazard_cat,
           title="Sparking switchboard", description="Sparking switchboard near the water cooler, risk of shock")
    hazard = db.query(Issue).filter(Issue.asset_id == world.board.id).one()
    detail = client.get(f"/issues/{hazard.id}", headers=auth(world.ele_admin)).json()
    p = detail["priority"]["assessment"]
    assert p["score"] >= 80 and p["band"] == "critical"
    assert "SAFETY_RULE:ELECTRICAL_HAZARD" in p["reason_codes"]
    assert p["factors"]["safety"]["value"] == 1.0 and p["algorithm_version"].startswith("priority-v2")

    for s in students(30):
        submit(s, world, category=world.bin_cat, title="Dustbin dirty",
               description="Dustbin garbage cleaning is needed in the corridor")
    bins = db.query(Issue).filter(Issue.category_id == world.bin_cat.id).one()
    assert bins.report_count == 30
    vol = client.get(f"/issues/{bins.id}", headers=auth(world.cln_admin)).json()["priority"]["assessment"]
    assert vol["score"] < 80 and vol["band"] != "critical"
    assert vol["factors"]["affected_users"]["value"] > 0.8   # volume counted, but capped by the gate


def test_priority_override_rules(client, db, world, students, submit, auth):
    submit(students(), world, asset=world.board, category=world.hazard_cat,
           description="Sparking switchboard near the water cooler")
    issue = db.query(Issue).one()
    url = f"/issues/{issue.id}/priority/override"
    assert client.post(url, json={"score": 90, "reason": "short"}, headers=auth(world.ele_admin)).status_code == 422
    # dept admin cannot go below the safety floor, super admin can
    low = {"score": 10, "reason": "Checked on site, false alarm"}
    r = client.post(url, json=low, headers=auth(world.ele_admin))
    assert r.status_code == 403 and r.json()["code"] == "below_safety_floor"
    assert client.post(url, json=low, headers=auth(world.super)).status_code == 200
    db.expire_all()
    assert db.get(Issue, issue.id).priority_band == "low"
    # the underlying assessment keeps updating and is visible next to the override
    prio = client.get(f"/issues/{issue.id}/priority", headers=auth(world.ele_admin)).json()
    assert prio["override"]["reason"] and prio["assessment"]["band"] == "critical"
    assert client.delete(url, headers=auth(world.ele_admin)).status_code == 200
    db.expire_all()
    assert db.get(Issue, issue.id).priority_band == "critical"
    assert db.query(AuditEvent).filter(AuditEvent.action.like("priority_override%")).count() == 2


# ------------------------------------------------------------------------ Test J
def _resolved_bin_issue(client, db, world, students, submit, auth, n=5):
    people = students(n)
    for s in people:
        submit(s, world, category=world.bin_cat, title="Dustbin dirty",
               description="Dustbin garbage cleaning is needed in the corridor")
    issue = db.query(Issue).filter(Issue.category_id == world.bin_cat.id).one()
    _resolve_issue(client, auth, db, issue, world.cln_admin, world.cln_staff, verify=False)
    assert db.get(Issue, issue.id).status == "resolved"       # no verification needed for this category
    return people, issue.id, {c.created_by: c.id for c in db.query(Complaint).all()}


def test_J_single_dissent_flags_review_and_threshold_reopens(client, db, world, students, submit, auth):
    people, issue_id, cids = _resolved_bin_issue(client, db, world, students, submit, auth)
    fb = lambda s, **kw: client.post(f"/complaints/{cids[s.id]}/feedback", headers=auth(s), json=kw)  # noqa: E731

    r = fb(people[0], rating=1, resolved_for_me=False, still_unresolved=True)
    assert r.status_code == 201 and r.json()["dissent"] is True
    db.expire_all()
    issue = db.get(Issue, issue_id)
    assert issue.status == "resolved"                           # one student never reopens it alone
    assert issue.needs_review and issue.needs_review_reason == "dissent"
    notification_service.dispatch_pending()
    assert db.query(Notification).filter(Notification.recipient_id == world.cln_admin.id,
                                         Notification.type == "feedback_dissent").count() == 1

    assert fb(people[1], rating=5, resolved_for_me=True).status_code == 201
    db.expire_all()
    assert db.get(Issue, issue_id).status == "resolved"

    assert fb(people[2], rating=2, resolved_for_me=False).status_code == 201   # low rating + not resolved = dissent
    db.expire_all()
    issue = db.get(Issue, issue_id)
    assert issue.status == "reopened" and issue.reopen_count == 1
    assert {c.status.value for c in db.query(Complaint).all()} == {"reopened"}
    owner = client.get(f"/complaints/{cids[people[2].id]}", headers=auth(people[2])).json()
    assert owner["feedback_state"] == "submitted" and owner["resolution_summary"] is None
    assert issue.needs_review is False
    # a new cycle starts: the issue can be assigned again
    assert client.post(f"/issues/{issue_id}/assignments", json={"staff_ids": [world.cln_staff.id]},
                       headers=auth(world.cln_admin)).status_code == 201


def test_admin_can_reopen_resolved_issue_manually(client, db, world, students, submit, auth):
    people, issue_id, _ = _resolved_bin_issue(client, db, world, students, submit, auth)
    assert client.post(f"/issues/{issue_id}/reopen", json={"reason": "new evidence"},
                       headers=auth(world.wat_admin)).status_code == 404     # other department
    assert client.post(f"/issues/{issue_id}/reopen", json={"reason": "new evidence"},
                       headers=auth(world.cln_admin)).status_code == 200
    db.expire_all()
    assert db.get(Issue, issue_id).status == "reopened"


def test_resolved_issues_close_after_feedback_window(db, client, world, students, submit, auth):
    from datetime import timedelta
    from app.core.timeutil import utcnow
    from app.services import feedback_service
    people, issue_id, _ = _resolved_bin_issue(client, db, world, students, submit, auth)
    assert feedback_service.close_expired(db) == 0
    issue = db.get(Issue, issue_id)
    issue.resolved_at = utcnow() - timedelta(days=8)
    db.commit()
    assert feedback_service.close_expired(db) == 1
    db.expire_all()
    assert db.get(Issue, issue_id).status == "closed"


def test_open_dissent_review_blocks_auto_close(db, client, world, students, submit, auth):
    from datetime import timedelta
    from app.core.timeutil import utcnow
    from app.services import feedback_service
    people, issue_id, cids = _resolved_bin_issue(client, db, world, students, submit, auth)
    client.post(f"/complaints/{cids[people[0].id]}/feedback", headers=auth(people[0]),
                json={"rating": 1, "resolved_for_me": False, "still_unresolved": True})
    issue = db.get(Issue, issue_id)
    issue.resolved_at = utcnow() - timedelta(days=30)
    db.commit()
    assert feedback_service.close_expired(db) == 0


# ------------------------------------------------------------- escalation & SLA
def test_escalation_fires_once_per_repeat_window_and_records_recipients(client, db, world, students, submit, auth):
    student = students()
    submit(student, world, asset=world.board, category=world.hazard_cat,
           description="Sparking switchboard near the water cooler")
    issue = db.query(Issue).one()
    assert issue.priority_band == "critical" and issue.sla_resolution_due_at is not None
    assert sla_service.run_issue_escalations(db) == 2            # dept_admin + hod, immediate rules
    assert sla_service.run_issue_escalations(db) == 0            # same window: nothing new
    db.expire_all()
    events = db.query(EscalationEvent).all()
    assert {tuple(e.recipient_ids) for e in events} == {(world.ele_admin.id,), (world.hod.id,)}
    assert db.get(Issue, issue.id).escalation_level == 2
    notification_service.dispatch_pending()
    assert db.query(Notification).filter(Notification.recipient_id == world.hod.id,
                                         Notification.type == "escalated").count() == 1
    # students are never told about escalations
    assert db.query(Notification).filter(Notification.type == "escalated",
                                         Notification.recipient_id == student.id).count() == 0


def test_unassigned_critical_issue_escalates_after_15_minutes(db, client, world, students, submit):
    from datetime import timedelta
    from app.core.timeutil import utcnow
    submit(students(), world, asset=world.board, category=world.hazard_cat,
           description="Sparking switchboard near the water cooler")
    sla_service.run_issue_escalations(db)
    issue = db.query(Issue).one()
    issue.first_reported_at = utcnow() - timedelta(minutes=20)
    db.commit()
    assert sla_service.run_issue_escalations(db) == 1            # unassigned_crit_15 -> dept admin
    issue.first_reported_at = utcnow() - timedelta(minutes=40)
    db.commit()
    assert sla_service.run_issue_escalations(db) >= 1            # 30-min HOD rule now due


def test_sla_deadlines_anchor_to_first_report(db, client, world, students, submit):
    submit(students(), world, asset=world.board, category=world.hazard_cat,
           description="Sparking switchboard near the water cooler")
    issue = db.query(Issue).one()
    from app.core.timeutil import as_utc
    assert (as_utc(issue.sla_resolution_due_at) - as_utc(issue.first_reported_at)).total_seconds() == 8 * 3600


def test_priority_refresh_skips_insignificant_changes(db, client, world, students, submit):
    from app.services import priority_service
    submit(students(), world, asset=world.cooler1, category=world.cooler_cat)
    from app.models.priority import PriorityAssessment
    before = db.query(PriorityAssessment).count()
    priority_service.refresh_active(db)
    assert db.query(PriorityAssessment).count() == before        # scored again, <2 points: no new row


# ---------------------------------------------------------- reliability & misc
def test_notification_failure_never_rolls_back_the_complaint(client, db, world, students, submit, monkeypatch):
    def boom(*_):
        raise RuntimeError("mail server down")

    monkeypatch.setitem(notification_service.HANDLERS, "complaint_submitted", boom)
    submit(students(), world, asset=world.cooler1, category=world.cooler_cat)    # still 201
    assert db.query(Complaint).count() == 1 and db.query(Issue).count() == 1
    failed = db.query(DomainEvent).filter(DomainEvent.event_type == "complaint_submitted").one()
    assert failed.processed_at is None and failed.attempts >= 1 and "mail server down" in failed.last_error


def test_state_machine_table():
    t = issue_service.can_transition
    assert t("open", "assigned") and t("in_progress", "resolved") and t("resolved", "reopened")
    assert not t("open", "resolved") and not t("assigned", "resolved") and not t("closed", "resolved")
    assert not t("rejected", "open") and not t("merged", "open") and not t("open", "in_progress")


def test_notifications_endpoints(client, db, world, students, submit, auth):
    s = students()
    submit(s, world, asset=world.cooler1, category=world.cooler_cat)
    notification_service.dispatch_pending()
    assert client.get("/notifications/unread-count", headers=auth(s)).json()["unread"] == 1
    items = client.get("/notifications", headers=auth(s)).json()
    assert items[0]["type"] == "complaint_submitted"
    other = students()
    assert client.post(f"/notifications/{items[0]['id']}/read", headers=auth(other)).status_code == 404
    assert client.post(f"/notifications/{items[0]['id']}/read", headers=auth(s)).status_code == 200
    assert client.get("/notifications/unread-count", headers=auth(s)).json()["unread"] == 0
    assert client.post("/notifications/read-all", headers=auth(s)).json()["marked"] == 0


def test_report_linked_notifications_are_grouped_for_routine_issues(client, db, world, students, submit, auth):
    for s in students(4):
        submit(s, world, category=world.bin_cat, title="Dustbin dirty",
               description="Dustbin garbage cleaning is needed in the corridor")
    notification_service.dispatch_pending()
    rows = db.query(Notification).filter(Notification.recipient_id == world.cln_admin.id,
                                         Notification.type == "report_linked").all()
    assert len(rows) == 1 and rows[0].count == 3                  # one grouped row, not three alerts


def test_reports_are_department_scoped(client, db, world, students, submit, auth):
    submit(students(), world, asset=world.cooler1, category=world.cooler_cat)
    wat = client.get("/reports/department-summary", headers=auth(world.wat_admin)).json()
    assert wat["total_issues"] == 1 and wat["total_reports"] == 1
    assert client.get("/reports/department-summary", headers=auth(world.ele_admin)).json()["total_issues"] == 0
    assert client.get(f"/reports/department-summary?department_id={world.depts['WAT'].id}",
                      headers=auth(world.ele_admin)).status_code == 404
    assert client.get("/reports/department-summary", headers=auth(world.hod)).json()["total_issues"] == 1
    assert client.get("/reports/staff-workload", headers=auth(world.super)).status_code == 200


def test_classification_correction_moves_issue_between_departments(client, db, world, students, submit, auth):
    submit(students(), world, asset=world.cooler1, category=world.cooler_cat)
    issue = _only_issue(db)
    task = _assign(client, auth, world.wat_admin, issue.id, world.wat_staff)
    r = client.patch(f"/issues/{issue.id}/classification", headers=auth(world.wat_admin),
                     json={"category_id": world.hazard_cat.id, "reason": "actually an electrical fault"})
    assert r.status_code == 404                                   # dept admin cannot see ELE categories
    r = client.patch(f"/issues/{issue.id}/classification", headers=auth(world.super),
                     json={"category_id": world.hazard_cat.id, "reason": "actually an electrical fault"})
    assert r.status_code == 200, r.text
    db.expire_all()
    moved = db.get(Issue, issue.id)
    assert moved.department_id == world.depts["ELE"].id and moved.status == "open"
    assert db.get(Assignment, task).status == "cancelled"
    assert moved.sla_anchor_at is not None
    assert client.get(f"/issues/{issue.id}", headers=auth(world.wat_admin)).status_code == 404
    assert client.get(f"/issues/{issue.id}", headers=auth(world.ele_admin)).status_code == 200
    # stale edits are refused
    r = client.patch(f"/issues/{issue.id}/classification", headers=auth(world.super),
                     json={"category_id": world.cooler_cat.id, "reason": "changed my mind", "expected_version": 1})
    assert r.status_code == 409 and r.json()["code"] == "stale_version"
