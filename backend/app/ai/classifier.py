"""
Zero-shot complaint classification.

Uses facebook/bart-large-mnli to classify complaint text into one of the
department categories, without needing to train a model ourselves.
"""

from functools import lru_cache

CANDIDATE_LABELS = [
    "electricity",
    "water supply",
    "sanitation",
    "road maintenance",
    "public safety",
    "noise complaint",
    "internet/telecom",
    "other",
]


@lru_cache(maxsize=1)
def _get_classifier():
    # Imported lazily so the rest of the app can run/test without torch
    # installed until this function is actually called.
    from transformers import pipeline

    return pipeline("zero-shot-classification", model="facebook/bart-large-mnli")


def classify_complaint(text: str) -> str:
    """Returns the single best-matching category label for the complaint text."""
    classifier = _get_classifier()
    result = classifier(text, candidate_labels=CANDIDATE_LABELS)
    return result["labels"][0]
