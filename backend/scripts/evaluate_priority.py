"""Evaluate the priority model on a labelled fixture set (design section 13.10).

    python -m scripts.evaluate_priority            # print the report
    python -m scripts.evaluate_priority --snapshot # write/refresh the regression snapshot

Reports ordering correctness against a labelled ranking (Spearman rank correlation and pairwise
agreement) plus a snapshot diff so weight changes are visible. Numbers describe THESE fixtures
only; they are not an accuracy claim about real incidents.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai import priority_v2 as pv

SNAPSHOT = os.path.join(os.path.dirname(__file__), "priority_snapshot.json")
RULES = pv.DEFAULT_SAFETY_RULES


def case(text, rank, **kw):
    base = dict(category_severity=0.3, category_criticality=0.4, category_impact=0.3, expected_resolution_hours=48)
    base.update(kw)
    return {"text": text, "rank": rank, "inputs": base}


# rank 1 = most urgent (labelled by hand). Ties share a rank.
FIXTURES = {
    "sparking switchboard": case("Sparking switchboard near water cooler", 1, category_severity=0.9, category_criticality=0.8),
    "smoke in lab": case("Smoke and burning smell from lab socket", 1, category_severity=0.8, category_criticality=0.8, category_impact=0.7),
    "ceiling plaster falling": case("Plaster fall from ceiling in classroom", 3, category_severity=0.5, category_impact=0.6),
    "no water 200 students": case("No water supply in hostel block", 4, category_severity=0.6, category_criticality=0.7,
                                  distinct_reporters=60, report_count=60, hours_since_first_report=10, expected_resolution_hours=12),
    "exam hall power cut": case("Power outage in exam hall during exam", 4, category_severity=0.6, category_criticality=0.7,
                                category_impact=0.8, expected_resolution_hours=8, distinct_reporters=5, report_count=5),
    "repeat cooler failure": case("Water cooler not cooling again", 6, category_severity=0.4, category_criticality=0.5,
                                  prior_issues_90d=3, distinct_reporters=15, report_count=20, hours_since_first_report=30),
    "single cooler": case("Water cooler not working", 7, category_severity=0.4, category_criticality=0.5,
                          distinct_reporters=1, report_count=1),
    "dustbin x50": case("Dustbin not cleaned", 8, category_severity=0.2, category_criticality=0.3, category_impact=0.2,
                        distinct_reporters=50, report_count=50, hours_since_first_report=19, expected_resolution_hours=24),
    "fee receipt": case("Fee receipt not generated", 8, category_severity=0.3, category_criticality=0.4, category_impact=0.6,
                        expected_resolution_hours=72),
    "broken chair": case("One chair broken in class", 10, category_severity=0.2, category_criticality=0.3, category_impact=0.4),
}


def score_all():
    out = {}
    for name, c in FIXTURES.items():
        inputs = pv.PriorityInputs(**c["inputs"], text=c["text"], matched_rules=pv.match_safety_rules(c["text"], RULES))
        r = pv.compute(inputs)
        out[name] = {"score": r["score"], "band": r["band"], "reasons": r["reason_codes"]}
    return out


def _ranks(values):
    order = sorted(range(len(values)), key=lambda i: -values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(a, b):
    ra, rb = _ranks(a), _ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va, vb = sum((x - ma) ** 2 for x in ra), sum((y - mb) ** 2 for y in rb)
    return cov / ((va * vb) ** 0.5) if va and vb else 0.0


def pairwise_agreement(labels, scores):
    ok = total = 0
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            if labels[i] == labels[j]:
                continue
            total += 1
            ok += (scores[i] > scores[j]) == (labels[i] < labels[j]) and scores[i] != scores[j]
    return ok / total if total else 1.0


def evaluate() -> dict:
    scored = score_all()
    names = list(FIXTURES)
    labels = [FIXTURES[n]["rank"] for n in names]
    scores = [scored[n]["score"] for n in names]
    return {"scored": scored, "spearman": round(spearman([-l for l in labels], scores), 3),
            "pairwise_agreement": round(pairwise_agreement(labels, scores), 3),
            "hazards_critical": all(scored[n]["band"] == "critical" for n in ("sparking switchboard", "smoke in lab")),
            "volume_never_critical": all(scored[n]["band"] != "critical" for n in ("dustbin x50", "no water 200 students"))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true", help="write the regression snapshot")
    args = parser.parse_args()
    result = evaluate()
    print(json.dumps({k: v for k, v in result.items() if k != "scored"}, indent=2))
    for name, row in sorted(result["scored"].items(), key=lambda kv: -kv[1]["score"]):
        print(f"  {row['score']:6.1f}  {row['band']:8s}  {name}")
    current = {n: r["score"] for n, r in result["scored"].items()}
    if args.snapshot:
        json.dump(current, open(SNAPSHOT, "w"), indent=2, sort_keys=True)
        print("snapshot written")
    elif os.path.exists(SNAPSHOT):
        old = json.load(open(SNAPSHOT))
        diffs = {n: (old.get(n), v) for n, v in current.items() if old.get(n) != v}
        print("regression: no change" if not diffs else f"regression: {len(diffs)} score(s) changed: {diffs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
