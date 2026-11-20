"""Precision and recall of duplicate matching on labelled pairs (design section 13.10).

    python -m scripts.evaluate_grouping

Uses the deterministic scoring maths with a bag-of-words embedding, so it runs without any model
download. Replace `embed` with the real model to measure it on your own labelled pairs. Results
describe these fixtures only.
"""

import hashlib
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai import grouping as g


def embed(text: str) -> np.ndarray:
    v = np.zeros(128, dtype="float32")
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % 128] += 1
    n = np.linalg.norm(v)
    return v / n if n else v


# (text a, asset a, text b, asset b, same leaf, ambiguous, label_is_duplicate)
PAIRS = [
    ("Water cooler broken in corridor 3", 1, "Cooler near corridor 3 is broken", 1, True, False, True),
    ("Water cooler broken in corridor 3", 1, "Water cooler broken in corridor 3", 2, True, False, False),   # two coolers
    ("Water cooler broken in corridor 3", 1, "Water cooler broken in corridor 3", None, True, True, False),  # cannot tell which
    ("Dustbin not cleaned in block A", None, "Dustbin is not cleaned in block A", None, True, False, True),
    ("Dustbin not cleaned in block A", None, "Projector flickering in room 12", None, True, False, False),
    ("Fan not working in room 4", 5, "Fan in room 4 not working", 5, True, False, True),
    ("Fan not working in room 4", 5, "Light bulb fused in room 4", 6, True, False, False),
    ("Washroom dirty on second floor", None, "Second floor washroom is dirty", None, True, False, True),
]


def predict(a, asset_a, b, asset_b, same_leaf, ambiguous) -> bool:
    if asset_a is not None and asset_b is not None:
        return asset_a == asset_b                      # asset identity decides
    cos = g.cosine(embed(a), embed(b))
    sem = g.semantic_signal(cos)
    score = g.combine(g.asset_signal(asset_a, asset_b), g.location_signal(same_leaf, not same_leaf), sem, 1.0)
    return g.classify_outcome(score, same_asset=False, same_leaf=same_leaf, semantic=sem, ambiguous=ambiguous) == "high"


def main() -> int:
    tp = fp = fn = tn = 0
    for a, aa, b, ab, leaf, amb, label in PAIRS:
        pred = predict(a, aa, b, ab, leaf, amb)
        tp += pred and label
        fp += pred and not label
        fn += (not pred) and label
        tn += (not pred) and not label
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    print(f"pairs={len(PAIRS)} tp={tp} fp={fp} fn={fn} tn={tn}")
    print(f"precision={precision:.2f} recall={recall:.2f}")
    print("same-corridor-different-asset negatives merged:", fp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
