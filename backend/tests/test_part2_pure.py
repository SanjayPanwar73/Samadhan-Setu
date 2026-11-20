"""Pure-logic tests: no database, no HTTP, no models."""

import numpy as np

from app.ai import grouping as g
from app.ai import priority_v2 as pv


def _inputs(**kw):
    base = dict(category_severity=0.3, category_criticality=0.3, category_impact=0.3,
                expected_resolution_hours=48)
    base.update(kw)
    return pv.PriorityInputs(**base)


# -------------------------------------------------------------------- priority
def test_safety_rule_forces_critical_floor_even_with_one_report():
    rules = pv.match_safety_rules("Sparking switchboard near water cooler", pv.DEFAULT_SAFETY_RULES)
    r = pv.compute(_inputs(category_severity=0.2, matched_rules=rules, text="sparking switchboard"))
    assert r["score"] >= 80 and r["band"] == "critical"
    assert "SAFETY_FLOOR_APPLIED" in r["reason_codes"] and "SAFETY_RULE:ELECTRICAL_HAZARD" in r["reason_codes"]


def test_volume_alone_never_reaches_critical():
    r = pv.compute(_inputs(category_severity=0.2, distinct_reporters=500, report_count=900,
                           hours_since_first_report=500, distinct_locations=9, prior_issues_90d=9,
                           sla_elapsed_ratio=0.79))
    assert r["score"] <= 79 and r["band"] != "critical"
    assert "VOLUME_SATURATED" in r["reason_codes"]


def test_volume_is_saturating_not_linear():
    small = pv.compute(_inputs(distinct_reporters=5, report_count=5))["factors"]["affected_users"]["value"]
    big = pv.compute(_inputs(distinct_reporters=50, report_count=50))["factors"]["affected_users"]["value"]
    huge = pv.compute(_inputs(distinct_reporters=5000, report_count=5000))["factors"]["affected_users"]["value"]
    assert small < big <= huge == 1.0


def test_breached_sla_opens_the_critical_gate():
    base = dict(category_severity=0.5, category_criticality=1.0, category_impact=1.0, distinct_reporters=50,
                report_count=50, hours_since_first_report=1000, distinct_locations=4, prior_issues_90d=3,
                expected_resolution_hours=1)
    capped = pv.compute(_inputs(**base, sla_breached=False, sla_elapsed_ratio=0.5))
    breached = pv.compute(_inputs(**base, sla_breached=True))
    assert capped["score"] <= 79
    assert breached["critical_gate"] is True and breached["score"] >= capped["score"]


def test_people_affected_hint_is_ignored_by_the_model():
    assert "people_affected" not in pv.PriorityInputs.__dataclass_fields__


def test_weights_sum_to_one_and_every_factor_is_reported():
    assert abs(sum(pv.DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9
    out = pv.compute(_inputs())
    assert set(out["factors"]) == set(pv.DEFAULT_WEIGHTS)
    assert all({"value", "weight", "contribution"} <= set(f) for f in out["factors"].values())
    assert out["algorithm_version"] == pv.ALGORITHM_VERSION


def test_band_boundaries():
    b = pv.DEFAULT_BANDS
    assert [pv.band_for(s, b) for s in (0, 29.9, 30, 59.9, 60, 79.9, 80, 100)] == \
        ["low", "low", "medium", "medium", "high", "high", "critical", "critical"]


def test_asset_criticality_maps_one_to_five_onto_zero_to_one():
    lo = pv.compute(_inputs(asset_criticality=1))["factors"]["criticality"]["value"]
    hi = pv.compute(_inputs(asset_criticality=5))["factors"]["criticality"]["value"]
    assert lo == 0.0 and hi == 1.0


def test_hindi_keywords_trigger_rules_and_bad_regex_is_ignored():
    assert pv.match_safety_rules("बिजली में चिंगारी निकल रही है", pv.DEFAULT_SAFETY_RULES)
    assert pv.match_safety_rules("x", [{"name": "bad", "pattern": "(", "risk_level": 1.0}]) == []


def test_normal_text_does_not_match_safety_rules():
    assert pv.match_safety_rules("The dustbin has not been cleaned", pv.DEFAULT_SAFETY_RULES) == []


# -------------------------------------------------------------------- grouping
def test_semantic_signal_is_clamped_and_linear():
    assert g.semantic_signal(0.2) == 0.0 and g.semantic_signal(0.95) == 1.0
    assert abs(g.semantic_signal(0.70) - 0.5) < 1e-9


def test_asset_signal_table():
    assert g.asset_signal(1, 1) == 1.0 and g.asset_signal(1, 2) == 0.0
    assert g.asset_signal(None, None) == 0.5 and g.asset_signal(None, 3) == 0.3 and g.asset_signal(3, None) == 0.3


def test_location_and_time_signals():
    assert g.location_signal(True, False) == 1.0 and g.location_signal(False, True) == 0.6
    assert g.location_signal(False, False) == 0.0
    assert g.time_signal(0) == 1.0 and g.time_signal(7) < 0.37 and g.time_signal(-3) == 1.0


def test_identical_text_same_leaf_no_assets_links_automatically():
    score = g.combine(g.asset_signal(None, None), 1.0, 1.0, 1.0)
    assert score >= 0.80
    assert g.classify_outcome(score, same_asset=False, same_leaf=True, semantic=1.0, ambiguous=False) == "high"


def test_ambiguity_caps_two_identical_coolers_at_medium():
    # student did not pick an asset and the corridor has two coolers: never auto-merge
    score = g.combine(0.5, 1.0, 1.0, 1.0)
    assert g.classify_outcome(score, same_asset=False, same_leaf=True, semantic=1.0, ambiguous=True) == "medium"


def test_one_sided_asset_cannot_reach_high_even_for_identical_text():
    score = g.combine(g.asset_signal(None, 7), 1.0, 1.0, 1.0)
    assert score < 0.80
    assert g.classify_outcome(score, same_asset=False, same_leaf=True, semantic=1.0, ambiguous=False) == "medium"


def test_low_scores_create_new_issues():
    assert g.classify_outcome(0.3, same_asset=False, same_leaf=False, semantic=0.1, ambiguous=False) == "low"
    assert g.classify_outcome(0.549, same_asset=False, same_leaf=True, semantic=0.5, ambiguous=False) == "low"


def test_cosine_basics():
    a = np.array([1.0, 0.0]); b = np.array([0.0, 1.0])
    assert g.cosine(a, a) == 1.0 and g.cosine(a, b) == 0.0 and g.cosine(a, np.zeros(2)) == 0.0


def test_weights_sum_to_one():
    assert abs(sum(g.WEIGHTS.values()) - 1.0) < 1e-9


# --------------------------------------------------------------------- privacy
def test_pii_redaction_removes_emails_phones_and_enrollment_numbers():
    from app.services.privacy import redact_pii
    text = "I am raj, mail raj.k@college.edu or call 9876543210, enrollment 0801CS211001 and ENR00042."
    out, changed = redact_pii(text, extra_tokens=["raj"])
    assert changed
    for secret in ("raj.k@college.edu", "9876543210", "0801CS211001", "ENR00042"):
        assert secret not in out
    assert redact_pii("The cooler is broken", None) == ("The cooler is broken", False)


def test_anon_codes_are_random_per_call():
    from app.services.privacy import new_anon_code
    codes = {new_anon_code() for _ in range(50)}
    assert len(codes) > 40 and all(c.startswith("ANON-") and len(c) == 9 for c in codes)
