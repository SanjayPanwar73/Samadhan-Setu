"""Thin provider interface for the heavy AI components.

Production uses the real transformer models (loaded lazily). Tests call
``set_providers`` with deterministic fakes so no model is ever downloaded.
Every provider degrades gracefully: intake must still succeed when a model is
unavailable (design section 20).
"""

import logging
from dataclasses import dataclass
from typing import Callable

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Providers:
    # (text, labels) -> (best_label, confidence 0..1)
    classify: Callable[[str, list[str]], tuple[str, float]]
    # text -> 1-D float32 vector
    embed: Callable[[str], np.ndarray]
    # text -> (label, score) ; label in {"POSITIVE", "NEGATIVE"}
    sentiment: Callable[[str], tuple[str, float]]
    embedding_model_name: str = ""


def _real_classify(text: str, labels: list[str]) -> tuple[str, float]:
    from app.ai.classifier import _get_classifier

    # Each label is a separate premise/hypothesis pair. Batch short inputs so
    # the classifier can score several labels in one pass through its weights.
    batch_size = max(1, min(8, 4096 // max(len(text), 1)))
    result = _get_classifier()(text, candidate_labels=labels, batch_size=batch_size, num_workers=0)
    return result["labels"][0], float(result["scores"][0])


def _real_embed(text: str) -> np.ndarray:
    from app.ai.embeddings import get_embedding_model

    return np.asarray(get_embedding_model().encode([text])[0], dtype="float32")


def _real_sentiment(text: str) -> tuple[str, float]:
    from app.ai.sentiment import analyze_sentiment

    result = analyze_sentiment(text)
    return result["label"], float(result["score"])


_providers: Providers | None = None


def get_providers() -> Providers:
    global _providers
    if _providers is None:
        _providers = Providers(
            classify=_real_classify,
            embed=_real_embed,
            sentiment=_real_sentiment,
            embedding_model_name=settings.EMBEDDING_MODEL,
        )
    return _providers


def set_providers(providers: Providers | None) -> None:
    global _providers
    _providers = providers


def warm_intake_models() -> None:
    """Load the shared weights in the scheduler, outside request handling."""
    from app.ai.classifier import _get_classifier
    from app.ai.embeddings import get_embedding_model
    from app.ai.sentiment import _get_sentiment_pipeline

    for load in (_get_classifier, get_embedding_model, _get_sentiment_pipeline):
        try:
            load()
        except Exception:
            logger.exception("Could not preload %s", load.__name__)


def safe_classify(text: str, labels: list[str]) -> tuple[str | None, float]:
    if not labels:
        return None, 0.0
    try:
        return get_providers().classify(text, labels)
    except Exception:  # noqa: BLE001 - any model failure must not break intake
        logger.exception("classifier unavailable")
        return None, 0.0


def safe_embed(text: str) -> np.ndarray | None:
    try:
        vec = np.asarray(get_providers().embed(text), dtype="float32")
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0 else None
    except Exception:  # noqa: BLE001
        logger.exception("embedding model unavailable")
        return None


def safe_sentiment(text: str) -> tuple[str | None, float | None]:
    try:
        return get_providers().sentiment(text)
    except Exception:  # noqa: BLE001
        logger.exception("sentiment model unavailable")
        return None, None
