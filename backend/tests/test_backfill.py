"""Test K: the V1 -> V2 backfill on a database shaped like the pre-contract schema."""

import pytest
from sqlalchemy import text

from app.ai import priority_v2 as pv
from app.models.audit_event import AuditEvent
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.department_membership import DepartmentMembership
from app.models.feedback import Feedback
from app.models.issue import Issue
from app.models.issue_link import IssueLink
from app.models.priority import PriorityAssessment
from app.models.user import User, UserRole
from app.models.work import Assignment, ResolutionReport
from scripts import migrate_v2_backfill as backfill

LEGACY_COLUMNS = [
    "issue_root_id INTEGER", "assigned_to INTEGER", "priority_score FLOAT", "priority_breakdown TEXT",
    "repeat_count INTEGER DEFAULT 1", "sla_deadline DATETIME", "escalation_level INTEGER DEFAULT 0",
    "last_escalated_at DATETIME",
]


@pytest.fixture()
def v1(db, make_user):
    """Pre-contract database: V2 tables plus the V1-only complaint columns, filled with V1-style rows."""
    for col in LEGACY_COLUMNS:
        db.execute(text(f"ALTER TABLE complaints ADD COLUMN {col}"))
    elec = Department(name="Electricity Board", category="electricity")
    water = Department(name="Water Works", category="water supply")
    other = Department(name="General Grievance", category="other")
    db.add_all([elec, water, other])
    db.flush()
    ns = type("V1", (), {})()
    ns.elec, ns.water, ns.other = elec, water, other
    ns.student1 = make_user(UserRole.user)                       # V1 name, no enrollment number
    ns.student2 = make_user(UserRole.user, enrollment_no="EN42")
    ns.staff = make_user(UserRole.staff, department_id=water.id)
    ns.lost_staff = make_user(UserRole.staff)                     # never had a department
    ns.admin = make_user(UserRole.admin)
    ns.mgmt = make_user(UserRole.management)

    def complaint(cid, title, status, dept, author, root=None, assigned=None, score=None):
        db.execute(text(
            "INSERT INTO complaints (id, title, description, category, status, department_id, created_by, "
            "assigned_to, issue_root_id, priority_score, sla_deadline, created_at, updated_at, people_affected) "
            "VALUES (:id, :t, :d, :c, :s, :dept, :by, :a, :root, :p, '2026-11-20 10:00:00', "
            "'2026-11-01 09:00:00', '2026-11-02 09:00:00', 5)"),
            {"id": cid, "t": title, "d": f"{title} - detailed description", "c": "water supply", "s": status,
             "dept": dept.id, "by": author.id, "a": assigned.id if assigned else None, "root": root or cid, "p": score})

    complaint(1, "No water in hostel", "pending", water, ns.student1, assigned=ns.staff, score=62.5)
    complaint(2, "Water not coming", "pending", water, ns.student2, root=1, assigned=ns.staff, score=62.5)
    complaint(3, "Tap dry again", "pending", water, ns.student1, root=1, assigned=ns.staff, score=62.5)
    complaint(4, "Street light out", "resolved", elec, ns.student2, assigned=ns.staff, score=41.0)
    complaint(5, "Something else entirely", "pending", other, ns.student1, score=12.0)
    db.execute(text("INSERT INTO resolution_history (complaint_id, resolution_text, resolved_by) "
                    "VALUES (4, 'Replaced the fuse and tested the circuit', :s)"), {"s": ns.staff.id})
    db.execute(text("INSERT INTO feedback (complaint_id, user_id, rating, comment) VALUES (4, :u, 5, 'thanks')"),
               {"u": ns.student2.id})
    for hid, cid, action in ((1, 1, "created"), (2, 1, "assigned"), (3, 4, "status_changed")):
        db.execute(text("INSERT INTO complaint_history (id, complaint_id, action, detail, actor_id, created_at) "
                        "VALUES (:i, :c, :a, 'detail', NULL, '2026-11-01 09:30:00')"), {"i": hid, "c": cid, "a": action})
    db.commit()
    return ns


def test_backfill_converts_everything_and_verifies(db, v1):
    report = backfill.run(db)
    db.commit()
    assert report["problems"] == [] and report["verified"] is True
    assert report["issues_created"] == 3 and report["complaints_linked"] == 5

    # one issue per V1 group, with the preserved complaints linked
    water = db.query(Issue).filter(Issue.title == "No water in hostel").one()
    assert water.ticket_no == "WAT-001" and water.report_count == 3 and water.distinct_reporter_count == 2
    assert water.status == "assigned" and water.priority_score == 62.5 and water.priority_band == "high"
    assert db.query(IssueLink).filter(IssueLink.issue_id == water.id, IssueLink.link_type == "system_migration",
                                      IssueLink.unlinked_at.is_(None)).count() == 3
    elec = db.query(Issue).filter(Issue.title == "Street light out").one()
    assert elec.ticket_no == "ELE-001" and elec.status == "resolved"
    triage = db.query(Issue).filter(Issue.title == "Something else entirely").one()
    assert triage.ticket_no == "TRI-001" and triage.status == "open"
    assert db.query(Complaint).filter(Complaint.issue_id.is_(None)).count() == 0
    assert {c.status.value for c in db.query(Complaint).filter(Complaint.issue_id == water.id)} == {"assigned"}

    # priority is kept as a legacy assessment until the next refresh
    legacy = db.query(PriorityAssessment).filter(PriorityAssessment.issue_id == water.id).one()
    assert legacy.algorithm_version == "v1-legacy" and legacy.is_current and legacy.score == 62.5
    assert pv.band_for(legacy.score, pv.DEFAULT_BANDS) == legacy.band
    assert water.sla_resolution_due_at is not None

    # assignment and resolution, feedback pointing at the migrated report
    a = db.query(Assignment).filter(Assignment.issue_id == water.id).one()
    assert a.staff_id == v1.staff.id and a.is_lead and a.status == "assigned"
    r = db.query(ResolutionReport).filter(ResolutionReport.issue_id == elec.id).one()
    assert r.cycle == 1 and r.status == "approved" and "fuse" in r.action_taken
    fb = db.query(Feedback).one()
    assert fb.issue_id == elec.id and fb.resolution_report_id == r.id


def test_backfill_maps_departments_roles_and_memberships(db, v1):
    report = backfill.run(db)
    db.commit()
    codes = {d.id: d.code for d in db.query(Department)}
    mapped = {old: codes[new] for old, new in report["department_map"].items()}
    assert mapped == {v1.elec.id: "ELE", v1.water.id: "WAT", v1.other.id: "TRI"}
    assert db.get(Department, v1.water.id).is_active is False        # retired, not deleted

    roles = {u.id: u.role for u in db.query(User)}
    assert roles[v1.student1.id] == UserRole.student and roles[v1.admin.id] == UserRole.super_admin
    assert roles[v1.mgmt.id] == UserRole.hod and roles[v1.staff.id] == UserRole.staff
    assert report["students_without_enrollment"] == 1

    wat = next(d.id for d in db.query(Department) if d.code == "WAT")
    tri = next(d.id for d in db.query(Department) if d.code == "TRI")
    member = lambda u: {m.department_id for m in db.query(DepartmentMembership).filter(DepartmentMembership.user_id == u.id)}  # noqa: E731
    assert member(v1.staff) == {wat} and db.get(User, v1.staff.id).department_id == wat
    assert member(v1.lost_staff) == {tri} and report["staff_in_triage"] == 1     # fixed later by a super admin
    assert len(member(v1.mgmt)) == 4 and tri not in member(v1.mgmt)               # every real department
    assert member(v1.admin) == set() and member(v1.student1) == set()


def test_backfill_copies_history_and_is_rerunnable(db, v1):
    backfill.run(db)
    db.commit()
    assert db.query(AuditEvent).filter(AuditEvent.request_id.like("v1-history-%")).count() == 3
    ev = db.query(AuditEvent).filter(AuditEvent.request_id == "v1-history-2").one()
    assert ev.action == "legacy_assigned" and ev.actor_role == "legacy" and ev.issue_id is not None

    before = (db.query(Issue).count(), db.query(IssueLink).count(), db.query(AuditEvent).count(),
              db.query(Assignment).count(), db.query(ResolutionReport).count())
    again = backfill.run(db)
    db.commit()
    assert again["problems"] == [] and again["issues_created"] == 0 and again["skipped_already_migrated"] == 5
    after = (db.query(Issue).count(), db.query(IssueLink).count(), db.query(AuditEvent).count(),
             db.query(Assignment).count(), db.query(ResolutionReport).count())
    assert before == after


def test_department_mapping_can_be_overridden(db, v1):
    report = backfill.run(db, overrides={"General Grievance": "ACC"})
    codes = {d.id: d.code for d in db.query(Department)}
    assert codes[report["department_map"][v1.other.id]] == "ACC"


def test_original_complaint_text_is_never_modified(db, v1):
    before = backfill.complaint_checksum(db)
    backfill.run(db)
    db.commit()
    assert backfill.complaint_checksum(db) == before


def test_migrated_database_works_with_the_v2_api(client, db, v1, auth):
    backfill.run(db)
    db.commit()
    admin = db.get(User, v1.admin.id)
    items = client.get("/issues", headers=auth(admin)).json()
    assert items["total"] == 3
    student = db.get(User, v1.student2.id)
    mine = client.get("/complaints/me", headers=auth(student)).json()
    assert {c["title"] for c in mine} == {"Water not coming", "Street light out"}
    assert next(c for c in mine if c["title"] == "Street light out")["status"] == "resolved"
    assert client.get("/auth/me", headers=auth(db.get(User, v1.student1.id))).json()["needs_enrollment_no"] is True


def test_backfill_refuses_to_run_after_contract(db):
    with pytest.raises(SystemExit):
        backfill.run(db)          # no legacy columns in this schema
