from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.complaint import Complaint, ComplaintStatus

router = APIRouter(
    prefix="/management",
    tags=["management"],
    dependencies=[Depends(require_role("management", "admin"))],
)


@router.get("/priority-queue")
def priority_queue(db: Session = Depends(get_db), limit: int = 20):
    complaints = (
        db.query(Complaint)
        .filter(Complaint.status.in_([ComplaintStatus.pending, ComplaintStatus.in_progress]))
        .order_by(Complaint.priority_score.desc())
        .all()
    )
    groups = {}
    for complaint in complaints:
        normalized_title = " ".join((complaint.title or "").lower().split())
        key = complaint.issue_root_id or complaint.id
        group = groups.setdefault(
            key,
            {
                "id": complaint.id,
                "title": complaint.title,
                "category": complaint.category,
                "priority_score": complaint.priority_score,
                "status": complaint.status,
                "escalation_level": complaint.escalation_level,
                "report_count": 0,
                "complaint_ids": [],
            },
        )
        group["report_count"] += 1
        group["complaint_ids"].append(complaint.id)
        group["priority_score"] = max(
            group["priority_score"] or 0, complaint.priority_score or 0
        )
        group["escalation_level"] = max(
            group["escalation_level"] or 0, complaint.escalation_level or 0
        )
    return sorted(
        groups.values(),
        key=lambda group: group["priority_score"] or 0,
        reverse=True,
    )[:limit]


@router.get("/category-distribution")
def category_distribution(db: Session = Depends(get_db)):
    rows = (
        db.query(Complaint.category, func.count(Complaint.id))
        .group_by(Complaint.category)
        .all()
    )
    return [{"category": category or "unclassified", "count": count} for category, count in rows]


@router.get("/sla-violations")
def sla_violations(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    count = (
        db.query(func.count(Complaint.id))
        .filter(
            Complaint.status.in_([ComplaintStatus.pending, ComplaintStatus.in_progress]),
            Complaint.sla_deadline < now,
        )
        .scalar()
    )
    return {"sla_violations_count": count}


@router.get("/resolution-trends")
def resolution_trends(db: Session = Depends(get_db)):
    # Average resolution time (days) grouped by category, for resolved complaints.
    # EXTRACT(EPOCH ...) is compatible with PostgreSQL, including Neon.
    rows = (
        db.query(
            Complaint.category,
            func.avg(
                extract("epoch", Complaint.updated_at - Complaint.created_at) / 86400
            ).label("avg_days"),
        )
        .filter(Complaint.status == ComplaintStatus.resolved)
        .group_by(Complaint.category)
        .all()
    )
    return [
        {"category": category or "unclassified", "avg_resolution_days": round(avg_days or 0, 2)}
        for category, avg_days in rows
    ]
