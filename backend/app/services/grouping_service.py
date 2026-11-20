"""Duplicate detection: SQL hard filters, then scoring (design section 8)."""

from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.ai import grouping as g
from app.core.config import settings
from app.core.timeutil import as_utc, utcnow
from app.models.asset import Asset
from app.models.complaint import Complaint
from app.models.complaint_embedding import ComplaintEmbedding
from app.models.issue import ACTIVE_STATUSES, Issue
from app.models.location import Location


@dataclass
class ComplaintSpec:
    created_by: int
    department_id: int
    category_id: int
    location_id: int
    asset_id: int | None
    embedding: np.ndarray | None
    location_parent_id: int | None = None


@dataclass
class MatchResult:
    outcome: str                        # "link" | "new"
    issue: Issue | None = None          # target when linking
    score: float | None = None
    breakdown: dict | None = None
    suggestions: list = field(default_factory=list)   # [(Issue, score, breakdown)]
    recurrence_of: Issue | None = None
    needs_review_reason: str | None = None


def vector_from_bytes(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="float32")


def _issue_vectors(db: Session, issue_ids: list[int], per_issue: int = 20) -> dict[int, list[np.ndarray]]:
    rank = func.row_number().over(partition_by=Complaint.issue_id, order_by=Complaint.id.desc())
    ranked = (db.query(Complaint.issue_id, Complaint.id, rank.label("rank"))
              .join(ComplaintEmbedding, ComplaintEmbedding.complaint_id == Complaint.id)
              .filter(Complaint.issue_id.in_(issue_ids)).subquery())
    rows = (db.query(ranked.c.issue_id, ComplaintEmbedding.vector)
            .join(ComplaintEmbedding, ComplaintEmbedding.complaint_id == ranked.c.id)
            .filter(ranked.c.rank <= per_issue))
    out: dict[int, list[np.ndarray]] = {}
    for issue_id, blob in rows:
        out.setdefault(issue_id, []).append(vector_from_bytes(blob))
    return out


def _is_ambiguous(db: Session, spec: ComplaintSpec) -> bool:
    """No asset given and the location holds 2+ registered assets of the department."""
    if spec.asset_id is not None:
        return False
    n = (db.query(Asset.id).filter(Asset.location_id == spec.location_id,
                                   Asset.department_id == spec.department_id,
                                   Asset.is_active.is_(True)).limit(2).count())
    return n >= 2


def find_recurrence(db: Session, spec: ComplaintSpec) -> Issue | None:
    """A previously resolved/closed issue for the same asset (or same place and category)."""
    q = db.query(Issue).filter(Issue.department_id == spec.department_id,
                               Issue.status.in_(("resolved", "closed")))
    if spec.asset_id is not None:
        q = q.filter(Issue.asset_id == spec.asset_id)
    else:
        q = q.filter(Issue.category_id == spec.category_id, Issue.location_id == spec.location_id)
    return q.order_by(Issue.resolved_at.desc().nullslast(), Issue.id.desc()).first()


def in_recurrence_grace(issue: Issue) -> bool:
    return (issue.status == "resolved" and issue.resolved_at is not None
            and utcnow() - as_utc(issue.resolved_at) <= timedelta(hours=settings.RECURRENCE_GRACE_HOURS))


def find_match(db: Session, spec: ComplaintSpec) -> MatchResult:
    now = utcnow()

    # Asset identity: one active issue per asset (enforced by a partial unique index too).
    if spec.asset_id is not None:
        same_asset = (db.query(Issue).filter(Issue.asset_id == spec.asset_id,
                                             Issue.status.in_(ACTIVE_STATUSES)).first())
        if same_asset is not None:
            reason = None if same_asset.category_id == spec.category_id else "category_mismatch_same_asset"
            return MatchResult("link", same_asset, 1.0, {"rule": "same_asset"}, needs_review_reason=reason)
        return MatchResult("new", recurrence_of=find_recurrence(db, spec))

    if spec.embedding is None:
        return MatchResult("new", recurrence_of=find_recurrence(db, spec))


    q = (db.query(Issue).join(Location, Location.id == Issue.location_id)
         .filter(Issue.department_id == spec.department_id, Issue.category_id == spec.category_id,
                 Issue.status.in_(ACTIVE_STATUSES)))
    where = [Issue.location_id == spec.location_id]
    if spec.location_parent_id is not None:
        where.append(Location.parent_id == spec.location_parent_id)
    candidates = q.filter(or_(*where)).all()
    if not candidates:
        return MatchResult("new", recurrence_of=find_recurrence(db, spec))

    vectors = _issue_vectors(db, [i.id for i in candidates])
    ambiguous = _is_ambiguous(db, spec)
    scored = []
    for issue in candidates:
        vecs = vectors.get(issue.id) or []
        cos = max((g.cosine(spec.embedding, v) for v in vecs), default=0.0)
        same_leaf = issue.location_id == spec.location_id
        sig = {
            "asset": g.asset_signal(spec.asset_id, issue.asset_id),
            "location": g.location_signal(same_leaf, not same_leaf),
            "semantic": g.semantic_signal(cos),
            "time": g.time_signal((now - as_utc(issue.last_reported_at or issue.created_at)).total_seconds() / 86400),
        }
        score = g.combine(sig["asset"], sig["location"], sig["semantic"], sig["time"])
        outcome = g.classify_outcome(score, same_asset=False, same_leaf=same_leaf, semantic=sig["semantic"],
                                     ambiguous=ambiguous, high=settings.GROUP_HIGH_THRESHOLD,
                                     medium=settings.GROUP_MEDIUM_THRESHOLD)
        scored.append((score, issue, {**{k: round(v, 4) for k, v in sig.items()}, "cosine": round(cos, 4),
                                      "ambiguous": ambiguous, "outcome": outcome}))
    scored.sort(key=lambda t: -t[0])
    best_score, best_issue, best_bd = scored[0]

    if best_bd["outcome"] == "high":
        return MatchResult("link", best_issue, best_score, best_bd)

    suggestions = [(i, s, bd) for s, i, bd in scored[:3] if s >= settings.GROUP_MEDIUM_THRESHOLD]
    return MatchResult("new", suggestions=suggestions, recurrence_of=find_recurrence(db, spec),
                       needs_review_reason="possible_duplicate" if suggestions else None)
