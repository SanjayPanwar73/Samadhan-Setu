"""
Zero-shot complaint classification.

Uses facebook/bart-large-mnli to classify complaint text into one of the
department categories, without needing to train a model ourselves.
"""

from app.ai.runtime import load_model, shared_model

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


@shared_model
def _get_classifier():
    # Imported lazily so the rest of the app can run/test without torch
    # installed until this function is actually called.
    from transformers import pipeline

    return load_model("facebook/bart-large-mnli",
                      lambda path: pipeline("zero-shot-classification", model=path))


def classify_complaint(text: str) -> str:
    """Returns the single best-matching category label for the complaint text."""
    classifier = _get_classifier()
    result = classifier(text, candidate_labels=CANDIDATE_LABELS)
    return result["labels"][0]
