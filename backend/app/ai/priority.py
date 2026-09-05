"""
Priority scoring — a hand-tuned, explainable weighted formula rather than a
black-box model. This is deliberate: for a viva/report you can point at each
weight and justify it, instead of saying "the model decided."

Score is on a 0-100 scale, higher = more urgent.
"""

# Weights sum to 1.0 — adjust these to change what the system prioritizes.
WEIGHTS = {
    "severity": 0.35,       # how bad the complaint itself is (from sentiment, 0-1)
    "people_affected": 0.30,  # how many people impacted, log-scaled
    "age_days": 0.20,        # how long it's been open
    "repeat_count": 0.15,    # how many times this/similar issue was reported
}

import math


def _normalize_people_affected(people_affected: int) -> float:
    # log-scale so 1 person isn't 0 and 10,000 people doesn't blow past 1.0
    return min(math.log1p(people_affected) / math.log1p(1000), 1.0)


def _normalize_age(age_days: float) -> float:
    # complaints older than 14 days are treated as maximally urgent on this axis
    return min(age_days / 14.0, 1.0)


def _normalize_repeat(repeat_count: int) -> float:
    # 5+ repeats of the same issue = max urgency on this axis
    return min(repeat_count / 5.0, 1.0)


def compute_priority(
    severity: float,
    people_affected: int,
    age_days: float,
    repeat_count: int,
) -> float:
    """
    severity: 0.0-1.0, typically derived from sentiment negativity/confidence
    people_affected: raw count
    age_days: how many days since the complaint was created
    repeat_count: how many times this issue has recurred
    """
    severity = max(0.0, min(severity, 1.0))

    score = (
        WEIGHTS["severity"] * severity
        + WEIGHTS["people_affected"] * _normalize_people_affected(people_affected)
        + WEIGHTS["age_days"] * _normalize_age(age_days)
        + WEIGHTS["repeat_count"] * _normalize_repeat(repeat_count)
    )
    return round(score * 100, 2)
