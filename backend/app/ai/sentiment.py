"""Sentiment analysis for complaint text, using a distilbert-sst2 pipeline."""

from functools import lru_cache


@lru_cache(maxsize=1)
def _get_sentiment_pipeline():
    from transformers import pipeline

    return pipeline(
        "sentiment-analysis",
        model="distilbert-base-uncased-finetuned-sst-2-english",
    )


def analyze_sentiment(text: str) -> dict:
    """Returns {"label": "POSITIVE"|"NEGATIVE", "score": float}."""
    pipe = _get_sentiment_pipeline()
    result = pipe(text)[0]
    return {"label": result["label"], "score": float(result["score"])}
