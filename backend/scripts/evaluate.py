"""
Evaluation harness for the AI modules — produces the numbers needed for the
project report / viva.

Run from the backend/ directory (after seeding):
    python -m scripts.evaluate

Notes on methodology:
- Classification is evaluated against a small hand-labeled test set (below)
  since we don't have ground-truth labels for the seeded complaints.
- Priority is evaluated by comparing compute_priority() output against a
  human-assigned "expected priority rank" for the same test set (MAE/RMSE
  on a 0-100 scale, plus Precision@K for the top-K most urgent items).
- Similarity is evaluated with a small set of known-duplicate pairs vs.
  known-distinct pairs, checking whether find_similar() correctly ranks
  duplicates closer than non-duplicates.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
import numpy as np

from app.ai.classifier import classify_complaint
from app.ai.sentiment import analyze_sentiment
from app.ai.priority import compute_priority

# --- Classification test set: (text, true_category) ---
CLASSIFICATION_TEST_SET = [
    ("Power has been out in our street for 6 hours straight.", "electricity"),
    ("No water coming from the tap since morning.", "water supply"),
    ("Garbage has piled up and not been collected for days.", "sanitation"),
    ("There is a massive pothole causing traffic jams daily.", "road maintenance"),
    ("Robbery reported twice this month in our neighborhood.", "public safety"),
    ("Construction noise starts before sunrise every day.", "noise complaint"),
    ("Broadband connection has been down for a week.", "internet/telecom"),
    ("Streetlights on the entire road are non-functional.", "electricity"),
    ("Drainage is blocked and water is stagnating.", "sanitation"),
    ("Mobile signal is extremely weak in this area.", "internet/telecom"),
]

# --- Priority test set: (text, people_affected, age_days, repeat_count, expected_rank) ---
# expected_rank: 1 = most urgent ... N = least urgent (assigned by hand)
PRIORITY_TEST_SET = [
    ("No water supply for entire block for 3 days, health risk.", 200, 3, 4, 1),
    ("Minor streetlight flicker on a quiet lane.", 5, 1, 1, 6),
    ("Sewage overflow near school, urgent.", 150, 2, 3, 2),
    ("Small pothole, minor inconvenience.", 10, 5, 1, 5),
    ("Repeated power outages affecting whole colony for a week.", 300, 7, 5, 1),
    ("Slightly loud music one evening.", 3, 1, 1, 6),
]

# --- Similarity test set: known duplicate pairs and known distinct pairs ---
DUPLICATE_PAIRS = [
    ("No electricity since last night in our area.", "Power has been out since yesterday night here."),
    ("Water supply has stopped for two days.", "No water for the past two days in our locality."),
]
DISTINCT_PAIRS = [
    ("No electricity since last night.", "Garbage has not been collected in a week."),
    ("Loud construction noise every morning.", "Mobile network signal is very weak."),
]


def eval_classification():
    print("\n=== Classification Evaluation ===")
    y_true, y_pred = [], []
    for text, true_label in CLASSIFICATION_TEST_SET:
        pred = classify_complaint(text)
        y_true.append(true_label)
        y_pred.append(pred)
        print(f"  '{text[:50]}...' -> predicted={pred}, true={true_label}")

    acc = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, average="macro", zero_division=0)
    recall = recall_score(y_true, y_pred, average="macro", zero_division=0)
    f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)

    print(f"\n  Accuracy:  {acc:.3f}")
    print(f"  Precision: {precision:.3f}")
    print(f"  Recall:    {recall:.3f}")
    print(f"  F1:        {f1:.3f}")
    return {"accuracy": acc, "precision": precision, "recall": recall, "f1": f1}


def eval_priority():
    print("\n=== Priority Evaluation ===")
    scores = []
    for text, people_affected, age_days, repeat_count, expected_rank in PRIORITY_TEST_SET:
        sentiment = analyze_sentiment(text)
        severity = sentiment["score"] if sentiment["label"] == "NEGATIVE" else 1 - sentiment["score"]
        score = compute_priority(severity, people_affected, age_days, repeat_count)
        scores.append((text, score, expected_rank))
        print(f"  '{text[:50]}...' -> score={score:.2f}, expected_rank={expected_rank}")

    # Convert scores to predicted ranks (1 = highest score = most urgent)
    sorted_by_score = sorted(scores, key=lambda x: -x[1])
    predicted_ranks = {text: rank + 1 for rank, (text, _, _) in enumerate(sorted_by_score)}

    true_ranks = np.array([r for _, _, r in scores])
    pred_ranks = np.array([predicted_ranks[text] for text, _, _ in scores])

    mae = np.mean(np.abs(true_ranks - pred_ranks))
    rmse = np.sqrt(np.mean((true_ranks - pred_ranks) ** 2))

    # Precision@K: of the top-K predicted urgent items, how many are truly top-K urgent?
    k = 2
    top_k_predicted = {text for text, _, _ in sorted_by_score[:k]}
    top_k_true = {text for text, _, r in scores if r <= k}
    precision_at_k = len(top_k_predicted & top_k_true) / k

    print(f"\n  Rank MAE:       {mae:.3f}")
    print(f"  Rank RMSE:      {rmse:.3f}")
    print(f"  Precision@{k}:    {precision_at_k:.3f}")
    return {"mae": mae, "rmse": rmse, "precision_at_k": precision_at_k}


def eval_similarity():
    print("\n=== Similarity Evaluation ===")
    from sentence_transformers import SentenceTransformer, util

    model = SentenceTransformer("all-MiniLM-L6-v2")

    correct = 0
    total = 0

    for a, b in DUPLICATE_PAIRS:
        emb = model.encode([a, b])
        sim = util.cos_sim(emb[0], emb[1]).item()
        is_correct = sim > 0.6  # threshold: should be flagged similar
        correct += int(is_correct)
        total += 1
        print(f"  DUPLICATE pair sim={sim:.3f} -> {'PASS' if is_correct else 'FAIL'}")

    for a, b in DISTINCT_PAIRS:
        emb = model.encode([a, b])
        sim = util.cos_sim(emb[0], emb[1]).item()
        is_correct = sim <= 0.6  # threshold: should NOT be flagged similar
        correct += int(is_correct)
        total += 1
        print(f"  DISTINCT pair  sim={sim:.3f} -> {'PASS' if is_correct else 'FAIL'}")

    y_true = [1] * len(DUPLICATE_PAIRS) + [0] * len(DISTINCT_PAIRS)
    y_pred = []
    for a, b in DUPLICATE_PAIRS + DISTINCT_PAIRS:
        emb = model.encode([a, b])
        sim = util.cos_sim(emb[0], emb[1]).item()
        y_pred.append(1 if sim > 0.6 else 0)

    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    print(f"\n  Precision: {precision:.3f}")
    print(f"  Recall:    {recall:.3f}")
    print(f"  F1:        {f1:.3f}")
    return {"precision": precision, "recall": recall, "f1": f1}


if __name__ == "__main__":
    print("Running AI evaluation harness...")
    classification_results = eval_classification()
    priority_results = eval_priority()
    similarity_results = eval_similarity()

    print("\n" + "=" * 50)
    print("SUMMARY (copy into your report)")
    print("=" * 50)
    print(f"Classification: {classification_results}")
    print(f"Priority:       {priority_results}")
    print(f"Similarity:     {similarity_results}")
