"""Pure scoring maths for duplicate grouping (design section 8.3). No database access."""

import math

import numpy as np

ALGORITHM_VERSION = "group-v2.0"

WEIGHTS = {"asset": 0.35, "location": 0.20, "semantic": 0.35, "time": 0.10}


def asset_signal(complaint_asset_id: int | None, issue_asset_id: int | None) -> float:
    if complaint_asset_id is not None and issue_asset_id is not None:
        return 1.0 if complaint_asset_id == issue_asset_id else 0.0
    if complaint_asset_id is None and issue_asset_id is None:
        return 0.5
    return 0.3


def location_signal(same_leaf: bool, same_parent: bool) -> float:
    if same_leaf:
        return 1.0
    return 0.6 if same_parent else 0.0


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def semantic_signal(cos: float) -> float:
    """0 at cos <= 0.50, 1 at cos >= 0.90, linear in between."""
    return max(0.0, min(1.0, (cos - 0.50) / 0.40))


def time_signal(days_since_last_report: float) -> float:
    return math.exp(-max(0.0, days_since_last_report) / 7.0)


def combine(asset: float, location: float, semantic: float, time_: float) -> float:
    return (
        WEIGHTS["asset"] * asset
        + WEIGHTS["location"] * location
        + WEIGHTS["semantic"] * semantic
        + WEIGHTS["time"] * time_
    )


def classify_outcome(
    score: float,
    *,
    same_asset: bool,
    same_leaf: bool,
    semantic: float,
    ambiguous: bool,
    high: float = 0.80,
    medium: float = 0.55,
) -> str:
    """Returns ``high`` | ``medium`` | ``low``. The ambiguity cap keeps two identical
    assets in one corridor from merging when the student could not name the asset."""
    if score >= high:
        confident = same_asset or (not ambiguous and same_leaf and semantic >= 0.75)
        if confident and not ambiguous:
            return "high"
        return "medium"
    if score >= medium:
        return "medium"
    return "low"
