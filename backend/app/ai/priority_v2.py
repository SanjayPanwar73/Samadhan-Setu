"""Interpretable priority model v2 (design section 13). Pure functions, no database."""

import math
import re
from dataclasses import dataclass, field

ALGORITHM_VERSION = "priority-v2.0"

DEFAULT_WEIGHTS = {
    "severity": 0.20,
    "safety": 0.20,
    "affected_users": 0.15,
    "criticality": 0.10,
    "sla_risk": 0.10,
    "duration": 0.08,
    "academic_impact": 0.07,
    "spread": 0.05,
    "recurrence": 0.05,
}

# band -> minimum score (checked from the top)
DEFAULT_BANDS = {"critical": 80, "high": 60, "medium": 30, "low": 0}

DEFAULT_PARAMS = {
    "n_max": 50,                 # saturation constant for affected users
    "non_critical_cap": 79,      # ceiling unless the critical gate passes
    "gate_severity": 0.6,
    "gate_safety": 0.5,
    "sentiment_bonus": 0.15,
    "impact_keywords": ["exam", "lab", "practical", "placement", "viva", "परीक्षा"],
    "impact_boost": 0.2,
}

# Built-in safety rules, used until a super admin defines rules in the database.
DEFAULT_SAFETY_RULES = [
    {"name": "ELECTRICAL_HAZARD", "risk_level": 1.0, "floor_score": 80.0,
     "pattern": r"spark|short.?circuit|exposed wire|open wire|electric shock|current (lag|maar)|करंट|चिंगारी"},
    {"name": "FIRE_OR_SMOKE", "risk_level": 1.0, "floor_score": 85.0,
     "pattern": r"\bfire\b|smoke|burning smell|burnt|आग|धुआं"},
    {"name": "GAS_LEAK", "risk_level": 1.0, "floor_score": 85.0, "pattern": r"gas leak|gas smell|गैस"},
    {"name": "STRUCTURAL_RISK", "risk_level": 0.8, "floor_score": 70.0,
     "pattern": r"ceiling (fall|collaps)|wall (crack|collaps)|building crack|plaster fall"},
    {"name": "WATER_CONTAMINATION", "risk_level": 0.7, "floor_score": None,
     "pattern": r"contaminat|sewage|foul smell|dirty water|दूषित|गंदा पानी"},
    {"name": "SLIP_OR_FLOOD", "risk_level": 0.5, "floor_score": None,
     "pattern": r"flood|water.?logging|slippery|overflow"},
]


def band_for(score: float, bands: dict) -> str:
    for name, minimum in sorted(bands.items(), key=lambda kv: -kv[1]):
        if score >= minimum:
            return name
    return "low"


def _norm_count(n: int, n_max: int) -> float:
    return min(1.0, math.log(1 + max(n, 0)) / math.log(1 + n_max))


def match_safety_rules(text: str, rules: list[dict]) -> list[dict]:
    hits = []
    for rule in rules:
        try:
            if re.search(rule["pattern"], text, re.IGNORECASE):
                hits.append(rule)
        except re.error:
            continue
    return hits


@dataclass
class PriorityInputs:
    category_severity: float = 0.3
    category_criticality: float = 0.3
    category_impact: float = 0.3
    expected_resolution_hours: float = 48
    asset_criticality: int | None = None      # 1-5
    matched_rules: list = field(default_factory=list)
    negative_sentiment: float = 0.0           # 0..1, mean strength of negative sentiment
    text: str = ""
    distinct_reporters: int = 1
    report_count: int = 1
    hours_since_first_report: float = 0.0
    distinct_locations: int = 1
    prior_issues_90d: int = 0
    sla_elapsed_ratio: float = 0.0
    sla_breached: bool = False


def compute(inputs: PriorityInputs, weights: dict | None = None, bands: dict | None = None,
            params: dict | None = None) -> dict:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    b = bands or DEFAULT_BANDS
    p = {**DEFAULT_PARAMS, **(params or {})}

    rule_risk = max((r["risk_level"] for r in inputs.matched_rules), default=0.0)
    floor = max((r["floor_score"] for r in inputs.matched_rules if r.get("floor_score")), default=None)

    severity = min(1.0, max(inputs.category_severity, rule_risk)
                   + p["sentiment_bonus"] * max(0.0, min(1.0, inputs.negative_sentiment)))
    safety = rule_risk
    affected = 0.8 * _norm_count(inputs.distinct_reporters, p["n_max"]) \
        + 0.2 * _norm_count(inputs.report_count, p["n_max"])
    if inputs.asset_criticality is not None:
        criticality = (min(5, max(1, inputs.asset_criticality)) - 1) / 4
    else:
        criticality = inputs.category_criticality
    duration = min(1.0, inputs.hours_since_first_report / (2 * max(inputs.expected_resolution_hours, 1)))
    impact = inputs.category_impact
    lowered = inputs.text.lower()
    if any(k.lower() in lowered for k in p["impact_keywords"]):
        impact = min(1.0, impact + p["impact_boost"])
    spread = min(1.0, max(0, inputs.distinct_locations - 1) / 3)
    recurrence = min(1.0, inputs.prior_issues_90d / 3)
    sla_risk = 1.0 if inputs.sla_breached else min(1.0, max(0.0, inputs.sla_elapsed_ratio))

    normalized = {
        "severity": severity, "safety": safety, "affected_users": affected,
        "criticality": criticality, "sla_risk": sla_risk, "duration": duration,
        "academic_impact": impact, "spread": spread, "recurrence": recurrence,
    }
    factors = {
        name: {"value": round(value, 4), "weight": w[name], "contribution": round(100 * w[name] * value, 3)}
        for name, value in normalized.items()
    }
    raw = 100 * sum(w[n] * v for n, v in normalized.items())

    reasons: list[str] = []
    score = raw
    if floor is not None and score < floor:
        score = floor
        reasons.append("SAFETY_FLOOR_APPLIED")
    for r in inputs.matched_rules:
        reasons.append(f"SAFETY_RULE:{r['name']}")

    gate = (severity >= p["gate_severity"] or safety >= p["gate_safety"]
            or inputs.sla_breached or (floor or 0) >= b.get("critical", 80))
    if not gate and score > p["non_critical_cap"]:
        score = p["non_critical_cap"]
        reasons.append("CRITICAL_GATE_CAPPED")
    if affected >= 0.9:
        reasons.append("VOLUME_SATURATED")
    if inputs.sla_breached:
        reasons.append("SLA_BREACHED")
    elif sla_risk >= 0.8:
        reasons.append("SLA_AT_RISK")
    if inputs.prior_issues_90d >= 1:
        reasons.append(f"RECURRENCE_{inputs.prior_issues_90d}_IN_90D")

    final = max(0.0, min(100.0, round(score, 1)))
    return {
        "score": final,
        "band": band_for(final, b),
        "raw_score": round(raw, 2),
        "factors": factors,
        "reason_codes": reasons,
        "critical_gate": bool(gate),
        "safety_floor": floor,
        "algorithm_version": ALGORITHM_VERSION,
    }
