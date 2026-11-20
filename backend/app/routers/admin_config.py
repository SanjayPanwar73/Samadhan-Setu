"""Super-admin configuration: priority weights/bands, safety rules, SLA policies, escalation rules.
Every change is audited."""

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.ai import priority_v2 as pv
from app.core.database import get_db
from app.deps import require_role
from app.models.priority import EscalationRule, PriorityConfig, SafetyRule, SlaPolicy
from app.models.user import User
from app.services import audit_service

router = APIRouter(prefix="/admin/org", tags=["admin-config"])
SA = Depends(require_role("super_admin"))
BANDS = ("critical", "high", "medium", "low")
TRIGGERS = ("immediate", "unassigned_for", "no_progress_for", "sla_breach_risk", "sla_breached")


class PriorityConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weights: dict[str, float]
    bands: dict[str, float]
    params: dict = {}

    @field_validator("weights")
    @classmethod
    def weights_ok(cls, w):
        if set(w) != set(pv.DEFAULT_WEIGHTS):
            raise ValueError(f"weights must define exactly: {sorted(pv.DEFAULT_WEIGHTS)}")
        if any(v < 0 for v in w.values()) or abs(sum(w.values()) - 1.0) > 1e-6:
            raise ValueError("weights must be non-negative and sum to 1.0")
        return w

    @field_validator("bands")
    @classmethod
    def bands_ok(cls, b):
        if set(b) != set(BANDS):
            raise ValueError(f"bands must define exactly: {list(BANDS)}")
        if not (b["critical"] > b["high"] > b["medium"] > b["low"] >= 0) or b["critical"] > 100:
            raise ValueError("band minimums must strictly decrease from critical to low and stay within 0-100")
        return b


class SafetyRuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80)
    pattern: str = Field(min_length=2, max_length=500)
    applies_category_id: int | None = Field(default=None, ge=1)
    risk_level: float = Field(ge=0, le=1)
    floor_score: float | None = Field(default=None, ge=0, le=100)

    @field_validator("pattern")
    @classmethod
    def valid_regex(cls, p):
        try:
            re.compile(p)
        except re.error as exc:
            raise ValueError(f"invalid regular expression: {exc}")
        return p


class SafetyRulePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    risk_level: float | None = Field(default=None, ge=0, le=1)
    floor_score: float | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None


class SlaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department_id: int | None = Field(default=None, ge=1)
    band: str
    response_minutes: int = Field(ge=1, le=60 * 24 * 30)
    resolution_minutes: int = Field(ge=1, le=60 * 24 * 90)
    no_progress_minutes: int = Field(ge=1, le=60 * 24 * 30)

    @field_validator("band")
    @classmethod
    def band_ok(cls, v):
        if v not in BANDS:
            raise ValueError(f"band must be one of {list(BANDS)}")
        return v


class EscalationRuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department_id: int | None = Field(default=None, ge=1)
    band: str = "any"
    trigger: str
    after_minutes: int | None = Field(default=None, ge=0, le=60 * 24 * 30)
    repeat_minutes: int | None = Field(default=None, ge=1, le=60 * 24 * 30)
    notify_role: str

    @field_validator("trigger")
    @classmethod
    def trigger_ok(cls, v):
        if v not in TRIGGERS:
            raise ValueError(f"trigger must be one of {list(TRIGGERS)}")
        return v

    @field_validator("notify_role")
    @classmethod
    def role_ok(cls, v):
        if v not in ("dept_admin", "hod", "super_admin"):
            raise ValueError("notify_role must be dept_admin, hod or super_admin")
        return v

    @field_validator("band")
    @classmethod
    def band_ok(cls, v):
        if v != "any" and not all(b in BANDS for b in v.split(",")):
            raise ValueError("band must be 'any' or a comma-separated list of bands")
        return v


class EscalationRulePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    after_minutes: int | None = Field(default=None, ge=0)
    repeat_minutes: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


# -------------------------------------------------------------- priority config
@router.get("/priority-config")
def get_priority_config(db: Session = Depends(get_db), _: User = SA):
    cfg = db.query(PriorityConfig).filter(PriorityConfig.is_active.is_(True)).first()
    if cfg is None:
        return {"version": None, "source": "built-in defaults", "weights": pv.DEFAULT_WEIGHTS,
                "bands": pv.DEFAULT_BANDS, "params": pv.DEFAULT_PARAMS}
    return {"version": cfg.version, "source": "database", "weights": cfg.weights, "bands": cfg.bands,
            "params": cfg.params}


@router.put("/priority-config")
def put_priority_config(payload: PriorityConfigIn, db: Session = Depends(get_db), actor: User = SA):
    """Creates a new version and deactivates the previous one (old assessments keep their version)."""
    last = db.query(PriorityConfig).order_by(PriorityConfig.version.desc()).first()
    for old in db.query(PriorityConfig).filter(PriorityConfig.is_active.is_(True)):
        old.is_active = False
    cfg = PriorityConfig(version=(last.version + 1) if last else 1, weights=payload.weights, bands=payload.bands,
                         params={**pv.DEFAULT_PARAMS, **payload.params}, is_active=True, created_by=actor.id)
    db.add(cfg)
    db.flush()
    audit_service.record(db, actor=actor, action="priority_config_changed", entity_type="priority_config",
                         entity_id=cfg.id, after={"version": cfg.version, "weights": cfg.weights, "bands": cfg.bands})
    db.commit()
    return {"version": cfg.version}


# ------------------------------------------------------------------ safety rules
@router.get("/safety-rules")
def list_safety_rules(db: Session = Depends(get_db), _: User = SA):
    rows = db.query(SafetyRule).order_by(SafetyRule.id).all()
    if not rows:
        return [{"id": None, "builtin": True, **r} for r in pv.DEFAULT_SAFETY_RULES]
    return [{"id": r.id, "builtin": False, "name": r.name, "pattern": r.pattern, "risk_level": r.risk_level,
             "floor_score": r.floor_score, "applies_category_id": r.applies_category_id,
             "is_active": r.is_active} for r in rows]


@router.post("/safety-rules", status_code=201)
def create_safety_rule(payload: SafetyRuleIn, db: Session = Depends(get_db), actor: User = SA):
    # The first DB rule replaces the built-in set, so seed the defaults once to keep them.
    if db.query(SafetyRule).count() == 0:
        for r in pv.DEFAULT_SAFETY_RULES:
            db.add(SafetyRule(name=r["name"], pattern=r["pattern"], risk_level=r["risk_level"],
                              floor_score=r["floor_score"]))
    rule = SafetyRule(**payload.model_dump())
    db.add(rule)
    db.flush()
    audit_service.record(db, actor=actor, action="safety_rule_created", entity_type="safety_rule",
                         entity_id=rule.id, after=payload.model_dump())
    db.commit()
    return {"id": rule.id}


@router.patch("/safety-rules/{rule_id}")
def patch_safety_rule(rule_id: int, payload: SafetyRulePatch, db: Session = Depends(get_db), actor: User = SA):
    rule = db.query(SafetyRule).filter(SafetyRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(404, "Rule not found")
    changes = payload.model_dump(exclude_unset=True)
    before = {k: getattr(rule, k) for k in changes}
    for k, v in changes.items():
        setattr(rule, k, v)
    audit_service.record(db, actor=actor, action="safety_rule_updated", entity_type="safety_rule",
                         entity_id=rule.id, before=before, after=changes)
    db.commit()
    return {"id": rule.id}


# --------------------------------------------------------------------------- SLA
@router.get("/sla-policies")
def list_sla(db: Session = Depends(get_db), _: User = SA):
    rows = db.query(SlaPolicy).order_by(SlaPolicy.department_id, SlaPolicy.band).all()
    if not rows:
        from app.services.sla_service import DEFAULT_SLA

        return [{"id": None, "builtin": True, "department_id": None, "band": b, "response_minutes": r,
                 "resolution_minutes": s, "no_progress_minutes": n} for b, (r, s, n) in DEFAULT_SLA.items()]
    return [{"id": r.id, "builtin": False, "department_id": r.department_id, "band": r.band,
             "response_minutes": r.response_minutes, "resolution_minutes": r.resolution_minutes,
             "no_progress_minutes": r.no_progress_minutes} for r in rows]


@router.put("/sla-policies")
def put_sla(payload: SlaIn, db: Session = Depends(get_db), actor: User = SA):
    row = db.query(SlaPolicy).filter(SlaPolicy.band == payload.band,
                                     SlaPolicy.department_id == payload.department_id).first()
    before = None
    if row is None:
        row = SlaPolicy(**payload.model_dump())
        db.add(row)
    else:
        before = {"response_minutes": row.response_minutes, "resolution_minutes": row.resolution_minutes,
                  "no_progress_minutes": row.no_progress_minutes}
        row.response_minutes, row.resolution_minutes = payload.response_minutes, payload.resolution_minutes
        row.no_progress_minutes = payload.no_progress_minutes
    db.flush()
    audit_service.record(db, actor=actor, action="sla_policy_changed", entity_type="sla_policy",
                         entity_id=row.id, before=before, after=payload.model_dump())
    db.commit()
    return {"id": row.id}


# ------------------------------------------------------------ escalation rules
@router.get("/escalation-rules")
def list_rules(db: Session = Depends(get_db), _: User = SA):
    rows = db.query(EscalationRule).order_by(EscalationRule.id).all()
    if not rows:
        from app.services.sla_service import DEFAULT_ESCALATION_RULES

        return [{"id": None, "builtin": True, "key": k, "trigger": t, "band": b, "after_minutes": a,
                 "repeat_minutes": r, "notify_role": role} for k, t, b, a, r, role in DEFAULT_ESCALATION_RULES]
    return [{"id": r.id, "builtin": False, "department_id": r.department_id, "band": r.band,
             "trigger": r.trigger, "after_minutes": r.after_minutes, "repeat_minutes": r.repeat_minutes,
             "notify_role": r.notify_role, "is_active": r.is_active} for r in rows]


@router.post("/escalation-rules", status_code=201)
def create_rule(payload: EscalationRuleIn, db: Session = Depends(get_db), actor: User = SA):
    rule = EscalationRule(**payload.model_dump())
    db.add(rule)
    db.flush()
    audit_service.record(db, actor=actor, action="escalation_rule_created", entity_type="escalation_rule",
                         entity_id=rule.id, after=payload.model_dump())
    db.commit()
    return {"id": rule.id}


@router.patch("/escalation-rules/{rule_id}")
def patch_rule(rule_id: int, payload: EscalationRulePatch, db: Session = Depends(get_db), actor: User = SA):
    rule = db.query(EscalationRule).filter(EscalationRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(404, "Rule not found")
    changes = payload.model_dump(exclude_unset=True)
    before = {k: getattr(rule, k) for k in changes}
    for k, v in changes.items():
        setattr(rule, k, v)
    audit_service.record(db, actor=actor, action="escalation_rule_updated", entity_type="escalation_rule",
                         entity_id=rule.id, before=before, after=changes)
    db.commit()
    return {"id": rule.id}
