"""Part 2 acceptance tests A, B, C plus intake edge cases."""

import threading

from app.models.complaint import Complaint
from app.models.duplicate_suggestion import DuplicateSuggestion
from app.models.issue import Issue
from app.models.issue_link import IssueLink


def test_A_fifty_students_same_cooler_make_one_issue(client, db, world, students, submit, auth):
    people = students(50)
    for s in people:
        submit(s, world, asset=world.cooler1, category=world.cooler_cat)

    issues = db.query(Issue).all()
    assert len(issues) == 1
    issue = issues[0]
    assert issue.report_count == 50 and issue.distinct_reporter_count == 50
    assert db.query(Complaint).count() == 50
    assert db.query(IssueLink).filter(IssueLink.unlinked_at.is_(None)).count() == 50
    assert issue.ticket_no == "WAT-001"

    queue = client.get("/issues", headers=auth(world.wat_admin)).json()
    assert queue["total"] == 1 and queue["items"][0]["report_count"] == 50


def test_B_two_coolers_with_asset_picker_stay_separate(db, world, students, submit):
    a, b = students(2)
    submit(a, world, asset=world.cooler1, category=world.cooler_cat)
    submit(b, world, asset=world.cooler2, category=world.cooler_cat)
    assert db.query(Issue).count() == 2


def test_B_unknown_asset_is_capped_at_medium_and_suggests(db, world, students, submit):
    a, b = students(2)
    submit(a, world, asset=world.cooler1, category=world.cooler_cat)
    r = submit(b, world, category=world.cooler_cat)          # "I don't know" which cooler
    assert r.json()["outcome"] == "possible_duplicate"
    assert db.query(Issue).count() == 2
    assert db.query(DuplicateSuggestion).count() == 1
    provisional = db.query(Issue).filter(Issue.asset_id.is_(None)).one()
    assert provisional.needs_review and provisional.needs_review_reason == "possible_duplicate"


def test_admin_accepting_a_suggestion_relinks_and_merges(client, db, world, students, submit, auth):
    a, b = students(2)
    submit(a, world, asset=world.cooler1, category=world.cooler_cat)
    submit(b, world, category=world.cooler_cat)
    suggestion = db.query(DuplicateSuggestion).one()
    r = client.post(f"/duplicate-suggestions/{suggestion.id}/accept", headers=auth(world.wat_admin))
    assert r.status_code == 200, r.text
    db.expire_all()
    target = db.query(Issue).filter(Issue.asset_id == world.cooler1.id).one()
    assert target.report_count == 2 and target.distinct_reporter_count == 2
    emptied = db.query(Issue).filter(Issue.asset_id.is_(None)).one()
    assert emptied.status == "merged" and emptied.merged_into_id == target.id and emptied.report_count == 0


def test_C_concurrent_submissions_create_exactly_one_issue(client, db, world, students, auth):
    # Resolve fixture ORM objects on their owning thread. Each concurrent
    # request gets plain data and uses its own API database session.
    headers = [auth(student) for student in students(10)]
    body = {"title": "Water cooler is broken", "description": "The water cooler near the corridor is broken",
            "location_id": world.c3.id, "asset_id": world.cooler1.id,
            "category_id": world.cooler_cat.id, "department_id": world.cooler_cat.department_id}
    results, errors = [], []

    def go(header):
        try:
            r = client.post("/complaints", headers=header, json=body)
            results.append(r.status_code)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=go, args=(header,)) for header in headers]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert not errors
    assert results == [201] * 10, results
    db.expire_all()
    issues = db.query(Issue).filter(Issue.asset_id == world.cooler1.id).all()
    assert len(issues) == 1
    assert issues[0].report_count == 10
    assert db.query(Complaint).count() == 10


def test_same_student_cannot_double_report(client, db, world, students, submit, auth):
    s = students()
    first = submit(s, world, asset=world.cooler1, category=world.cooler_cat).json()
    r = client.post("/complaints", headers=auth(s), json={
        "title": "Water cooler is broken", "description": "Still the water cooler is broken",
        "location_id": world.c3.id, "asset_id": world.cooler1.id,
        "category_id": world.cooler_cat.id})
    assert r.status_code == 409
    assert r.json()["code"] == "already_reported" and r.json()["complaint_id"] == first["complaint_id"]
    assert db.query(Complaint).count() == 1


def test_client_request_id_makes_submit_idempotent(client, db, world, students, auth):
    s = students()
    body = {"title": "Water cooler is broken", "description": "The water cooler is broken here",
            "location_id": world.c3.id, "asset_id": world.cooler1.id, "category_id": world.cooler_cat.id,
            "client_request_id": "req-12345678"}
    r1 = client.post("/complaints", json=body, headers=auth(s))
    r2 = client.post("/complaints", json=body, headers=auth(s))
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["complaint_id"] == r2.json()["complaint_id"] and r2.json()["existing"] is True
    assert db.query(Complaint).count() == 1


def test_asset_must_belong_to_selected_location(client, world, students, auth):
    r = client.post("/complaints", headers=auth(students()), json={
        "title": "Water cooler is broken", "description": "The water cooler is broken here",
        "location_id": world.c4.id, "asset_id": world.cooler1.id, "category_id": world.cooler_cat.id})
    assert r.status_code == 422 and r.json()["code"] == "invalid_asset"


def test_unclassifiable_text_goes_to_triage(client, db, world, students, auth):
    r = client.post("/complaints", headers=auth(students()), json={
        "title": "Something odd happened", "description": "zzz qqq xxx nothing matches any category",
        "location_id": world.c3.id})
    assert r.status_code == 201
    issue = db.query(Issue).one()
    assert issue.needs_review and issue.needs_review_reason == "unclassified_triage"


def test_people_affected_hint_is_not_trusted(client, db, world, students, auth):
    r = client.post("/complaints", headers=auth(students()), json={
        "title": "Dustbin is dirty", "description": "Dustbin garbage cleaning needed in the corridor",
        "location_id": world.c3.id, "category_id": world.bin_cat.id, "people_affected": 100000})
    assert r.status_code == 201
    assert db.query(Issue).one().priority_band != "critical"


def test_recurrence_after_resolution_creates_new_linked_issue(client, db, world, students, submit, auth):
    from app.services import feedback_service  # noqa: F401  (import check only)
    a, b = students(2)
    submit(a, world, asset=world.cooler1, category=world.cooler_cat)
    old = db.query(Issue).one()
    old.status, old.resolved_at = "resolved", __import__("app.core.timeutil", fromlist=["x"]).utcnow()
    db.commit()
    submit(b, world, asset=world.cooler1, category=world.cooler_cat)
    db.expire_all()
    issues = db.query(Issue).order_by(Issue.id).all()
    assert len(issues) == 2 and issues[1].recurrence_of_issue_id == issues[0].id
    assert issues[0].needs_review_reason == "recurrence_dissent"


def test_relink_updates_counts_on_both_issues_and_audits(client, db, world, students, submit, auth):
    from app.models.audit_event import AuditEvent
    a, b = students(2)
    submit(a, world, asset=world.cooler1, category=world.cooler_cat)
    submit(b, world, asset=world.cooler2, category=world.cooler_cat)
    c_b = db.query(Complaint).filter(Complaint.created_by == b.id).one()
    target = db.query(Issue).filter(Issue.asset_id == world.cooler1.id).one()
    r = client.post(f"/complaints/{c_b.id}/relink", headers=auth(world.wat_admin),
                    json={"issue_id": target.id, "reason": "same physical cooler"})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(Issue, target.id).report_count == 2
    assert db.query(Issue).filter(Issue.asset_id == world.cooler2.id).one().status == "merged"
    assert db.query(AuditEvent).filter(AuditEvent.action == "complaint_relinked").count() == 1
    # history is kept: the old link row is closed, not deleted
    assert db.query(IssueLink).filter(IssueLink.complaint_id == c_b.id).count() == 2


def test_relink_across_departments_is_rejected(client, db, world, students, submit, auth):
    a, b = students(2)
    submit(a, world, asset=world.cooler1, category=world.cooler_cat)
    submit(b, world, asset=world.board, category=world.hazard_cat, description="sparking switchboard hazard")
    c_b = db.query(Complaint).filter(Complaint.created_by == b.id).one()
    water_issue = db.query(Issue).filter(Issue.asset_id == world.cooler1.id).one()
    r = client.post(f"/complaints/{c_b.id}/relink", headers=auth(world.super),
                    json={"issue_id": water_issue.id, "reason": "wrong department"})
    assert r.status_code == 409 and r.json()["code"] == "cross_department"
