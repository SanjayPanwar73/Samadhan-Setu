"""Priority assessments, overrides and effective priority (design section 13)."""

from datetime import timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.ai import priority_v2 as pv
from app.core.errors import DomainError
from app.core.roles import has_role
from app.core.timeutil import as_utc, utcnow
from app.models.asset import Asset
from app.models.category import Category
from app.models.complaint import Complaint
from app.models.issue import Issue
from app.models.issue_link import IssueLink
from app.models.priority import PriorityAssessment, PriorityConfig, PriorityOverride, SafetyRule
from app.models.user import User
from app.services import audit_service, notification_service, sla_service

MIN_OVERRIDE_REASON = 10


def load_config(db: Session) -> tuple[dict, dict, dict, str]:
    cfg = db.query(PriorityConfig).filter(PriorityConfig.is_active.is_(True)).first()
    if cfg:
        return cfg.weights, cfg.bands, cfg.params, f"db-v{cfg.version}"
    return pv.DEFAULT_WEIGHTS, pv.DEFAULT_BANDS, pv.DEFAULT_PARAMS, "default"


def load_safety_rules(db: Session, category_id: int | None) -> list[dict]:
    rows = db.query(SafetyRule).filter(SafetyRule.is_active.is_(True)).all()
    if not rows:
        return pv.DEFAULT_SAFETY_RULES
    return [{"name": r.name, "pattern": r.pattern, "risk_level": r.risk_level, "floor_score": r.floor_score}
            for r in rows if r.applies_category_id in (None, category_id)]


def active_override(db: Session, issue_id: int) -> PriorityOverride | None:
    now = utcnow()
    row = (db.query(PriorityOverride).filter(PriorityOverride.issue_id == issue_id,
                                             PriorityOverride.cleared_at.is_(None))
           .order_by(PriorityOverride.id.desc()).first())
    if row and row.expires_at and as_utc(row.expires_at) <= now:
        return None
    return row


def current_assessment(db: Session, issue_id: int) -> PriorityAssessment | None:
    return (db.query(PriorityAssessment).filter(PriorityAssessment.issue_id == issue_id,
                                                PriorityAssessment.is_current.is_(True))
            .order_by(PriorityAssessment.id.desc()).first())


def _gather(db: Session, issue: Issue) -> pv.PriorityInputs:
    cat = db.query(Category).filter(Category.id == issue.category_id).first()
    asset = db.query(Asset).filter(Asset.id == issue.asset_id).first() if issue.asset_id else None
    rows = (db.query(Complaint).join(IssueLink, IssueLink.complaint_id == Complaint.id)
            .filter(IssueLink.issue_id == issue.id, IssueLink.unlinked_at.is_(None))
            .order_by(Complaint.created_at.desc()).limit(100).all())
    text = " ".join(f"{c.title}. {c.description}" for c in rows) or issue.title
    negatives = [c.sentiment_score for c in rows
                 if (c.sentiment_label or "").upper() == "NEGATIVE" and c.sentiment_score is not None]
    now = utcnow()
    first = as_utc(issue.first_reported_at) or now

    since = now - timedelta(days=90)
    prior = db.query(func.count(Issue.id)).filter(Issue.id != issue.id, Issue.created_at >= since)
    prior = prior.filter(Issue.asset_id == issue.asset_id) if issue.asset_id else \
        prior.filter(Issue.location_id == issue.location_id, Issue.category_id == issue.category_id)

    ratio, breached = 0.0, False
    if issue.sla_resolution_due_at:
        start = as_utc(issue.sla_anchor_at) or first
        total = (as_utc(issue.sla_resolution_due_at) - start).total_seconds()
        ratio = (now - start).total_seconds() / total if total > 0 else 1.0
        breached = now >= as_utc(issue.sla_resolution_due_at)

    return pv.PriorityInputs(
        category_severity=cat.base_severity if cat else 0.3,
        category_criticality=cat.default_criticality if cat else 0.3,
        category_impact=cat.impact_level if cat else 0.3,
        expected_resolution_hours=cat.expected_resolution_hours if cat else 48,
        asset_criticality=asset.criticality if asset else None,
        matched_rules=pv.match_safety_rules(text, load_safety_rules(db, issue.category_id)),
        negative_sentiment=(sum(negatives) / len(negatives)) if negatives else 0.0,
        text=text,
        distinct_reporters=issue.distinct_reporter_count or 1,
        report_count=issue.report_count or 1,
        hours_since_first_report=(now - first).total_seconds() / 3600,
        distinct_locations=len({c.location_id for c in rows if c.location_id}) or 1,
        prior_issues_90d=prior.scalar() or 0,
        sla_elapsed_ratio=ratio,
        sla_breached=breached,
    )


def sync_effective(db: Session, issue: Issue) -> None:
    """Copy the effective priority (override, else assessment) onto the issue and refresh SLA."""
    override = active_override(db, issue.id)
    if override:
        issue.priority_score, issue.priority_band = override.score, override.band
    else:
        cur = current_assessment(db, issue.id)
        if cur:
            issue.priority_score, issue.priority_band = cur.score, cur.band
            issue.current_assessment_id = cur.id
    sla_service.apply_deadlines(db, issue)


def assess(db: Session, issue: Issue, trigger: str) -> PriorityAssessment | None:
    weights, bands, params, cfg_version = load_config(db)
    result = pv.compute(_gather(db, issue), weights, bands, params)
    previous = current_assessment(db, issue.id)

    if trigger == "scheduled" and previous and previous.band == result["band"] \
            and abs(previous.score - result["score"]) < 2:
        sync_effective(db, issue)  # aging still moves the SLA clock
        return None

    if previous:
        previous.is_current = False
    factors = dict(result["factors"])
    factors["_meta"] = {"raw_score": result["raw_score"], "critical_gate": result["critical_gate"],
                        "safety_floor": result["safety_floor"]}
    row = PriorityAssessment(issue_id=issue.id, score=result["score"], band=result["band"],
                             factors=factors, reason_codes=result["reason_codes"],
                             algorithm_version=result["algorithm_version"], config_version=cfg_version,
                             trigger=trigger, is_current=True)
    db.add(row)
    db.flush()
    sync_effective(db, issue)
    return row


def refresh_active(db: Session) -> int:
    from app.models.issue import ACTIVE_STATUSES

    n = 0
    for issue in db.query(Issue).filter(Issue.status.in_(ACTIVE_STATUSES)).all():
        if assess(db, issue, "scheduled") is not None:
            n += 1
    db.commit()
    return n


# ------------------------------------------------------------------ overrides
def set_override(db: Session, issue: Issue, actor: User, score: float, reason: str,
                 expires_at=None) -> PriorityOverride:
    reason = (reason or "").strip()
    if len(reason) < MIN_OVERRIDE_REASON:
        raise DomainError("reason_required", f"A reason of at least {MIN_OVERRIDE_REASON} characters is required", 422)
    cur = current_assessment(db, issue.id)
    floor = ((cur.factors or {}).get("_meta") or {}).get("safety_floor") if cur else None
    if floor is not None and score < floor and not has_role(actor, "super_admin"):
        raise DomainError("below_safety_floor", "Only a super admin can set a priority below the safety floor", 403)
    _, bands, _, _ = load_config(db)
    before = {"score": issue.priority_score, "band": issue.priority_band}
    existing = active_override(db, issue.id)
    if existing:
        existing.cleared_at, existing.cleared_by = utcnow(), actor.id
    override = PriorityOverride(issue_id=issue.id, score=score, band=pv.band_for(score, bands),
                                reason=reason, overridden_by=actor.id, expires_at=expires_at)
    db.add(override)
    db.flush()
    sync_effective(db, issue)
    audit_service.record(db, actor=actor, action="priority_override_set", entity_type="issue",
                         entity_id=issue.id, issue_id=issue.id, before=before,
                         after={"score": score, "band": override.band}, reason=reason)
    if "critical" in (before["band"], override.band) or "high" in (before["band"], override.band):
        notification_service.emit(db, "priority_override", issue_id=issue.id, payload={"reason": reason})
    return override


def clear_override(db: Session, issue: Issue, actor: User) -> None:
    override = active_override(db, issue.id)
    if not override:
        raise DomainError("no_override", "No active override to clear", 404)
    before = {"score": issue.priority_score, "band": issue.priority_band}
    override.cleared_at, override.cleared_by = utcnow(), actor.id
    db.flush()
    sync_effective(db, issue)
    audit_service.record(db, actor=actor, action="priority_override_cleared", entity_type="issue",
                         entity_id=issue.id, issue_id=issue.id, before=before,
                         after={"score": issue.priority_score, "band": issue.priority_band})
