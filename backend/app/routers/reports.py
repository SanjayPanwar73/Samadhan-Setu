"""Department reports for dept admins, HODs and super admins. Aggregates only: no student data."""

from collections import Counter, defaultdict
from statistics import mean, median

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.timeutil import as_utc, utcnow
from app.deps import Scope, get_scope, require_role
from app.models.category import Category
from app.models.feedback import Feedback
from app.models.issue import ACTIVE_STATUSES, Issue
from app.models.priority import EscalationEvent
from app.models.user import User
from app.models.work import Assignment

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(require_role("dept_admin", "hod", "super_admin"))])


def _issues(db: Session, scope: Scope, department_id: int | None):
    q = db.query(Issue)
    if department_id is not None:
        if not scope.can_access(department_id):
            raise HTTPException(404, "Department not found")
        q = q.filter(Issue.department_id == department_id)
    elif not scope.is_global:
        q = q.filter(Issue.department_id.in_(scope.department_ids))
    return q


def _hours(i: Issue) -> float | None:
    if i.resolved_at is None or i.first_reported_at is None:
        return None
    return (as_utc(i.resolved_at) - as_utc(i.first_reported_at)).total_seconds() / 3600


@router.get("/department-summary")
def department_summary(department_id: int | None = Query(None, ge=1), db: Session = Depends(get_db),
                       scope: Scope = Depends(get_scope)):
    issues = _issues(db, scope, department_id).all()
    now = utcnow()
    active = [i for i in issues if i.status in ACTIVE_STATUSES]
    times = [h for h in map(_hours, issues) if h is not None]
    return {
        "total_issues": len(issues), "total_reports": sum(i.report_count for i in issues),
        "by_status": dict(Counter(i.status for i in issues)),
        "by_band": dict(Counter(i.priority_band or "unrated" for i in active)),
        "critical_or_high": sum(1 for i in active if i.priority_band in ("critical", "high")),
        "unassigned": sum(1 for i in active if i.status in ("open", "reopened")),
        "overdue": sum(1 for i in active if i.sla_resolution_due_at and as_utc(i.sla_resolution_due_at) < now),
        "escalated": sum(1 for i in active if i.escalation_level > 0),
        "reopened_issues": sum(1 for i in issues if i.reopen_count > 0),
        "reopen_rate": round(sum(1 for i in issues if i.reopen_count > 0) / len(issues), 3) if issues else 0.0,
        "avg_resolution_hours": round(mean(times), 2) if times else None,
        "median_resolution_hours": round(median(times), 2) if times else None,
    }


@router.get("/resolution-times")
def resolution_times(department_id: int | None = Query(None, ge=1), db: Session = Depends(get_db),
                     scope: Scope = Depends(get_scope)):
    names = {c.id: c.name for c in db.query(Category).all()}
    buckets = defaultdict(list)
    for i in _issues(db, scope, department_id).filter(Issue.resolved_at.isnot(None)).all():
        h = _hours(i)
        if h is not None:
            buckets[names.get(i.category_id, "Unknown")].append(h)
    return [{"category": k, "count": len(v), "avg_hours": round(mean(v), 2), "median_hours": round(median(v), 2)}
            for k, v in sorted(buckets.items())]


@router.get("/staff-workload")
def staff_workload(department_id: int | None = Query(None, ge=1), db: Session = Depends(get_db),
                   scope: Scope = Depends(get_scope)):
    ids = [i.id for i in _issues(db, scope, department_id).all()]
    if not ids:
        return []
    now = utcnow()
    out = {}
    for a in db.query(Assignment).filter(Assignment.issue_id.in_(ids)).all():
        row = out.setdefault(a.staff_id, {"staff_id": a.staff_id, "active": 0, "completed": 0, "overdue": 0})
        if a.status in ("assigned", "acknowledged", "in_progress", "awaiting_verification"):
            row["active"] += 1
            if a.due_at and as_utc(a.due_at) < now:
                row["overdue"] += 1
        elif a.status == "completed":
            row["completed"] += 1
    names = {u.id: u.name for u in db.query(User).filter(User.id.in_(list(out)))} if out else {}
    return [{**r, "name": names.get(r["staff_id"])} for r in out.values()]


@router.get("/satisfaction")
def satisfaction(department_id: int | None = Query(None, ge=1), db: Session = Depends(get_db),
                 scope: Scope = Depends(get_scope)):
    ids = [i.id for i in _issues(db, scope, department_id).all()]
    rows = db.query(Feedback).filter(Feedback.issue_id.in_(ids)).all() if ids else []
    n = len(rows)
    return {"responses": n,
            "avg_rating": round(mean(f.rating for f in rows), 2) if n else None,
            "satisfaction_rate": round(sum(1 for f in rows if f.resolved_for_me) / n, 3) if n else None,
            "dissent_rate": round(sum(1 for f in rows if f.still_unresolved) / n, 3) if n else None}


@router.get("/repeat-failures")
def repeat_failures(department_id: int | None = Query(None, ge=1), db: Session = Depends(get_db),
                    scope: Scope = Depends(get_scope)):
    from datetime import timedelta
    since = utcnow() - timedelta(days=90)
    counts = Counter()
    for i in _issues(db, scope, department_id).filter(Issue.created_at >= since).all():
        counts[("asset", i.asset_id) if i.asset_id else ("location", i.location_id)] += 1
    return [{"kind": k[0], "id": k[1], "issues_90d": n} for k, n in counts.most_common(20) if n >= 2]


@router.get("/trends")
def trends(department_id: int | None = Query(None, ge=1), weeks: int = Query(8, ge=1, le=52),
           db: Session = Depends(get_db), scope: Scope = Depends(get_scope)):
    now = utcnow()
    opened, resolved = Counter(), Counter()

    def week(d):
        return max(0, int((now - as_utc(d)).days // 7))

    for i in _issues(db, scope, department_id).all():
        if i.first_reported_at and week(i.first_reported_at) < weeks:
            opened[week(i.first_reported_at)] += 1
        if i.resolved_at and week(i.resolved_at) < weeks:
            resolved[week(i.resolved_at)] += 1
    return [{"weeks_ago": w, "opened": opened[w], "resolved": resolved[w]} for w in range(weeks - 1, -1, -1)]


@router.get("/escalations")
def escalations(department_id: int | None = Query(None, ge=1), offset: int = Query(0, ge=0, le=100_000),
                limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
                scope: Scope = Depends(get_scope)):
    ids = [i.id for i in _issues(db, scope, department_id).all()]
    if not ids:
        return []
    rows = (db.query(EscalationEvent).filter(EscalationEvent.issue_id.in_(ids))
            .order_by(EscalationEvent.id.desc()).offset(offset).limit(limit).all())
    return [{"issue_id": e.issue_id, "level": e.level, "rule": e.rule_key, "reason": e.reason,
             "recipient_ids": e.recipient_ids, "at": e.created_at} for e in rows]
