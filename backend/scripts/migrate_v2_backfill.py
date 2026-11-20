"""One-time (re-runnable) migration of V1 data into the V2 model.

Run AFTER `alembic upgrade b2d4f6a8c0e2` and BEFORE the contract revision c3e5a7b9d1f3:

    python -m scripts.migrate_v2_backfill --dry-run     # report only, nothing is saved
    python -m scripts.migrate_v2_backfill               # migrate and verify
    python -m scripts.migrate_v2_backfill --mapping map.json   # {"Old department name": "WAT"}
    python -m scripts.reembed                           # then compute embeddings

What it does (design section 21): seeds the V2 structure, maps old departments, converts roles
and department memberships, turns every V1 issue group (issue_root_id) into one issue with
`system_migration` links, copies history to audit_events and resolutions to resolution_reports,
and verifies row counts and a checksum of the original complaint text. Re-running skips
everything already migrated. Legacy columns are read with raw SQL because the ORM models no
longer declare them.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import bindparam, inspect, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.ai import priority_v2 as pv
from app.core.database import SessionLocal, engine
from app.models.audit_event import AuditEvent
from app.models.category import Category
from app.models.complaint import Complaint, ComplaintStatus
from app.models.department import Department
from app.models.department_membership import DepartmentMembership
from app.models.feedback import Feedback
from app.models.issue import Issue
from app.models.issue_link import IssueLink
from app.models.location import Location
from app.models.priority import PriorityAssessment
from app.models.user import User, UserRole
from app.models.work import Assignment, ResolutionReport
from app.services import issue_service, sla_service
from scripts.seed_org import seed_structure

# (keyword in "<name> <category>" of the old department, V2 department code), first match wins.
KEYWORD_MAP = [("water", "WAT"), ("electric", "ELE"), ("sanit", "CLN"), ("clean", "CLN"), ("road", "CLN"),
               ("mainten", "CLN"), ("account", "ACC"), ("fee", "ACC"), ("bill", "ACC")]
ROLE_MAP = {UserRole.user: UserRole.student, UserRole.admin: UserRole.super_admin,
            UserRole.management: UserRole.hod}
STATUS_MAP = {"pending": "open", "in_progress": "in_progress", "resolved": "resolved",
              "rejected": "rejected", "reopened": "reopened"}
LEGACY_COLUMNS = {"issue_root_id", "assigned_to", "priority_score", "sla_deadline"}


def _dt(value):
    if value is None or isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if isinstance(value, datetime) and value.tzinfo is None else value
    return datetime.fromisoformat(str(value).replace(" ", "T")).replace(tzinfo=timezone.utc)


def _json(value):
    if isinstance(value, (dict, list)) or value is None:
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def complaint_checksum(db: Session) -> str:
    """Hash of the immutable V1 facts (id, title, description, author). Must not change."""
    h = hashlib.sha256()
    for row in db.execute(text("SELECT id, title, description, created_by FROM complaints ORDER BY id")):
        h.update(repr(tuple(row)).encode())
    return h.hexdigest()


def build_department_map(db: Session, depts: dict, overrides: dict | None = None) -> dict[int, int]:
    overrides = overrides or {}
    mapping = {}
    for old in db.query(Department).filter(Department.code.is_(None)).all():
        code = overrides.get(old.name)
        if code is None:
            label = f"{old.name} {old.category or ''}".lower()
            code = next((c for kw, c in KEYWORD_MAP if kw in label), "TRI")
        mapping[old.id] = depts[code].id
    return mapping


def migrate_users(db: Session, dept_map: dict, depts: dict, report: dict) -> None:
    triage = depts["TRI"]
    real = [d for c, d in depts.items() if not d.is_system]
    for user in db.query(User).all():
        old_dept = user.department_id
        if user.role in ROLE_MAP:
            if user.role == UserRole.user and not user.enrollment_no:
                report["students_without_enrollment"] += 1
            user.role = ROLE_MAP[user.role]
        have = {m.department_id for m in db.query(DepartmentMembership).filter(DepartmentMembership.user_id == user.id)}
        wanted: list[int] = []
        if user.role == UserRole.staff:
            target = dept_map.get(old_dept) if old_dept in dept_map else (old_dept if old_dept in {d.id for d in real} else None)
            if target is None:
                target = triage.id
                report["staff_in_triage"] += 1
            wanted, user.department_id = [target], target
        elif user.role == UserRole.hod:
            wanted = [d.id for d in real]   # V1 management saw everything; super admin can narrow this later
        for dept_id in wanted:
            if dept_id not in have:
                db.add(DepartmentMembership(user_id=user.id, department_id=dept_id))
        if user.role == UserRole.dept_admin and old_dept in dept_map:
            user.department_id = dept_map[old_dept]
    db.flush()


def _legacy_location(db: Session) -> Location:
    root = db.query(Location).filter(Location.parent_id.is_(None), Location.name == "Legacy complaints").first()
    if root is None:
        root = Location(kind="campus", name="Legacy complaints", path="Legacy complaints")
        db.add(root)
        db.flush()
    child = db.query(Location).filter(Location.parent_id == root.id, Location.name == "Unknown location").first()
    if child is None:
        child = Location(parent_id=root.id, kind="building", name="Unknown location",
                         path="Legacy complaints > Unknown location")
        db.add(child)
        db.flush()
    return child


def _pick_category(db: Session, dept_id: int, v1_category: str | None) -> Category:
    cats = db.query(Category).filter(Category.department_id == dept_id, Category.is_active.is_(True)).order_by(Category.id).all()
    tokens = [t for t in (v1_category or "").lower().replace("/", " ").split() if len(t) > 3]
    for c in cats:
        if any(t in c.name.lower() for t in tokens):
            return c
    return cats[0]


def migrate_complaints(db: Session, dept_map: dict, depts: dict, report: dict) -> None:
    triage_id = depts["TRI"].id
    location = _legacy_location(db)
    admin = db.query(User).filter(User.role == UserRole.super_admin).order_by(User.id).first()
    rows = db.execute(text(
        "SELECT id, category, priority_score, priority_breakdown, status, department_id, created_by, "
        "assigned_to, issue_root_id, sla_deadline, created_at, updated_at FROM complaints ORDER BY id")).mappings().all()
    legacy = {r["id"]: r for r in rows}
    groups: dict[int, list[int]] = {}
    for r in rows:
        groups.setdefault(r["issue_root_id"] or r["id"], []).append(r["id"])

    for root_id, ids in groups.items():
        complaints = db.query(Complaint).filter(Complaint.id.in_(ids)).order_by(Complaint.id).all()
        if all(c.issue_id for c in complaints):
            report["skipped_already_migrated"] += len(complaints)
            continue
        root = legacy.get(root_id) or legacy[ids[0]]
        v2_dept = dept_map.get(root["department_id"], triage_id) if root["department_id"] else triage_id
        dept = db.query(Department).filter(Department.id == v2_dept).one()
        category = _pick_category(db, v2_dept, root["category"])
        status = STATUS_MAP.get(str(root["status"]), "open")
        if status == "open" and root["assigned_to"]:
            status = "assigned"
        created = [_dt(legacy[i]["created_at"]) for i in ids]
        issue = Issue(ticket_no=issue_service.next_ticket_no(db, dept), department_id=v2_dept, category_id=category.id,
                      location_id=location.id, title=complaints[0].title, status=status,
                      first_reported_at=min(created), last_reported_at=max(created),
                      last_progress_at=_dt(root["updated_at"]) or min(created),
                      resolved_at=_dt(root["updated_at"]) if status == "resolved" else None)
        db.add(issue)
        db.flush()
        for c in complaints:
            c.department_id, c.category_id, c.location_id = v2_dept, category.id, location.id
            c.is_anonymous = False
            issue_service.link_complaint(db, c, issue, link_type="system_migration", algorithm_version="migration-v1")
        issue_service.recompute_counts(db, issue)
        issue_service.refresh_summary(db, issue)

        score = float(root["priority_score"] or 0.0)
        band = pv.band_for(score, pv.DEFAULT_BANDS)
        assessment = PriorityAssessment(
            issue_id=issue.id, score=score, band=band, factors={"legacy_breakdown": _json(root["priority_breakdown"])},
            reason_codes=["LEGACY_V1_SCORE"], algorithm_version="v1-legacy", config_version="migration",
            trigger="migration", is_current=True)
        db.add(assessment)
        db.flush()
        issue.priority_score, issue.priority_band, issue.current_assessment_id = score, band, assessment.id
        sla_service.apply_deadlines(db, issue)
        if root["sla_deadline"] and status in ("open", "assigned", "in_progress", "reopened"):
            issue.sla_resolution_due_at = _dt(root["sla_deadline"])    # keep the promise already made

        assignment = None
        staff_id = root["assigned_to"]
        if staff_id and db.query(User).filter(User.id == staff_id).first():
            a_status = {"assigned": "assigned", "in_progress": "in_progress", "resolved": "completed",
                        "rejected": "cancelled", "reopened": "assigned"}.get(status, "assigned")
            assignment = Assignment(issue_id=issue.id, staff_id=staff_id, assigned_by=admin.id if admin else staff_id,
                                    is_lead=True, status=a_status, priority_at_assignment=band,
                                    task_description="Migrated from V1")
            db.add(assignment)
            db.flush()
        if status == "resolved":
            _migrate_resolution(db, issue, ids, assignment, admin, report)
        report["issues_created"] += 1
        report["complaints_linked"] += len(complaints)
    db.flush()


def _migrate_resolution(db: Session, issue: Issue, complaint_ids: list[int], assignment, admin, report) -> None:
    row = db.execute(text(
        "SELECT resolution_text, resolved_by, resolved_at FROM resolution_history "
        "WHERE complaint_id IN :ids ORDER BY id DESC LIMIT 1").bindparams(bindparam("ids", expanding=True)),
        {"ids": complaint_ids}).mappings().first()
    if row is None:
        return
    staff_id = row["resolved_by"]
    if assignment is None:
        assignment = Assignment(issue_id=issue.id, staff_id=staff_id, assigned_by=admin.id if admin else staff_id,
                                is_lead=True, status="completed", priority_at_assignment=issue.priority_band,
                                task_description="Migrated from V1")
        db.add(assignment)
        db.flush()
    resolved_at = _dt(row["resolved_at"])
    issue.resolved_at = resolved_at or issue.resolved_at
    summary = (row["resolution_text"] or "")[:500]
    report_row = ResolutionReport(issue_id=issue.id, assignment_id=assignment.id, cycle=1, submitted_by=staff_id,
                                  action_taken=row["resolution_text"], public_summary=summary, completed_at=resolved_at,
                                  status="approved", verified_by=staff_id, verified_at=resolved_at)
    db.add(report_row)
    db.flush()
    report["resolutions_migrated"] += 1
    seen = set()
    for fb in db.query(Feedback).filter(Feedback.complaint_id.in_(complaint_ids)).order_by(Feedback.id.desc()):
        fb.issue_id = issue.id
        if fb.complaint_id not in seen:       # one response per complaint per cycle
            fb.resolution_report_id = report_row.id
            seen.add(fb.complaint_id)


def migrate_history(db: Session, report: dict) -> None:
    done = {r[0] for r in db.query(AuditEvent.request_id).filter(AuditEvent.request_id.like("v1-history-%"))}
    rows = db.execute(text("SELECT id, complaint_id, action, detail, actor_id, created_at FROM complaint_history ORDER BY id")).mappings()
    issue_of = {c.id: c.issue_id for c in db.query(Complaint.id, Complaint.issue_id)}
    for h in rows:
        key = f"v1-history-{h['id']}"
        if key in done:
            continue
        db.add(AuditEvent(actor_id=h["actor_id"], actor_role="legacy", action=f"legacy_{h['action']}",
                          entity_type="complaint", entity_id=h["complaint_id"], issue_id=issue_of.get(h["complaint_id"]),
                          complaint_id=h["complaint_id"], after={"detail": h["detail"]}, request_id=key,
                          created_at=_dt(h["created_at"])))
        report["history_rows"] += 1


def verify(db: Session, before: str, report: dict) -> list[str]:
    problems = []
    total = db.query(Complaint).count()
    if db.query(Complaint).filter(Complaint.issue_id.is_(None)).count():
        problems.append("some complaints are not linked to an issue")
    if db.query(IssueLink).filter(IssueLink.unlinked_at.is_(None)).count() != total:
        problems.append("active issue_links do not match the complaint count")
    counted = sum(i.report_count for i in db.query(Issue))
    if counted != total:
        problems.append(f"issue report counts ({counted}) differ from complaints ({total})")
    if complaint_checksum(db) != before:
        problems.append("complaint text/author checksum changed")
    if db.query(User).filter(User.role.in_(list(ROLE_MAP))).count():
        problems.append("some users still have V1 roles")
    report["verified"] = not problems
    return problems


def run(db: Session, overrides: dict | None = None) -> dict:
    cols = {c["name"] for c in inspect(db.get_bind()).get_columns("complaints")}
    if not LEGACY_COLUMNS <= cols:
        raise SystemExit("The V1 columns are already gone (contract migration applied). Nothing to backfill.")
    report = {k: 0 for k in ("students_without_enrollment", "staff_in_triage", "issues_created", "complaints_linked",
                             "skipped_already_migrated", "resolutions_migrated", "history_rows")}
    before = complaint_checksum(db)
    depts = seed_structure(db, sample_places=False)
    dept_map = build_department_map(db, depts, overrides)
    report["department_map"] = {old: new for old, new in dept_map.items()}
    migrate_users(db, dept_map, depts, report)
    migrate_complaints(db, dept_map, depts, report)
    migrate_history(db, report)
    for old_id in dept_map:                       # old departments stay for reference but are retired
        db.query(Department).filter(Department.id == old_id).update({"is_active": False})
    db.flush()
    report["problems"] = verify(db, before, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="run everything, print the report, then roll back")
    parser.add_argument("--mapping", help="JSON file: {\"Old department name\": \"WAT\"}")
    args = parser.parse_args()
    overrides = json.load(open(args.mapping)) if args.mapping else None
    db = SessionLocal()
    try:
        report = run(db, overrides)
        print(json.dumps(report, indent=2, default=str))
        if report["problems"] or args.dry_run:
            db.rollback()
            print("ROLLED BACK" + (" (dry run)" if args.dry_run else " (verification failed)"))
            return 1 if report["problems"] else 0
        db.commit()
        print("Backfill committed. Next: python -m scripts.reembed, then review, then alembic upgrade head.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
