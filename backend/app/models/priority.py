"""Priority configuration, safety rules, assessments, overrides, SLA and escalation."""

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, false, func, true,
)

from app.core.database import Base


class PriorityConfig(Base):
    __tablename__ = "priority_configs"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(Integer, nullable=False)
    weights = Column(JSON, nullable=False)
    bands = Column(JSON, nullable=False)
    params = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=false(), default=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SafetyRule(Base):
    __tablename__ = "safety_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    pattern = Column(Text, nullable=False)  # regex, case-insensitive, multilingual allowed
    applies_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    risk_level = Column(Float, nullable=False)
    floor_score = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=true(), default=True)


class PriorityAssessment(Base):
    __tablename__ = "priority_assessments"
    __table_args__ = (Index("ix_assessments_issue_current", "issue_id", "is_current"),)

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False)
    score = Column(Float, nullable=False)
    band = Column(String, nullable=False)
    factors = Column(JSON, nullable=False)
    reason_codes = Column(JSON, nullable=False)
    algorithm_version = Column(String, nullable=False)
    config_version = Column(String, nullable=False)
    trigger = Column(String, nullable=False)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    is_current = Column(Boolean, nullable=False, server_default=true(), default=True)


class PriorityOverride(Base):
    __tablename__ = "priority_overrides"
    __table_args__ = (Index("ix_overrides_issue", "issue_id"),)

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False)
    score = Column(Float, nullable=False)
    band = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    overridden_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    cleared_at = Column(DateTime(timezone=True), nullable=True)
    cleared_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class SlaPolicy(Base):
    __tablename__ = "sla_policies"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)  # null = global
    band = Column(String, nullable=False)
    response_minutes = Column(Integer, nullable=False)
    resolution_minutes = Column(Integer, nullable=False)
    no_progress_minutes = Column(Integer, nullable=False)


class EscalationRule(Base):
    __tablename__ = "escalation_rules"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    band = Column(String, nullable=False)  # critical | high | medium | low | any
    trigger = Column(String, nullable=False)
    after_minutes = Column(Integer, nullable=True)  # null = use the SLA policy value
    repeat_minutes = Column(Integer, nullable=True)  # null = fire once
    notify_role = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=true(), default=True)


class EscalationEvent(Base):
    __tablename__ = "escalation_events"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("escalation_rules.id"), nullable=True)
    rule_key = Column(String, nullable=False)  # stable key, also for built-in default rules
    level = Column(Integer, nullable=False)
    recipient_ids = Column(JSON, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
