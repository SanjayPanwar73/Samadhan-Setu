"""Sentiment analysis for complaint text, using a distilbert-sst2 pipeline."""

from app.ai.runtime import load_model, shared_model


@shared_model
def _get_sentiment_pipeline():
    from transformers import pipeline

    return load_model("distilbert-base-uncased-finetuned-sst-2-english",
                      lambda path: pipeline("sentiment-analysis", model=path))


def analyze_sentiment(text: str) -> dict:
    """Returns {"label": "POSITIVE"|"NEGATIVE", "score": float}."""
    pipe = _get_sentiment_pipeline()
    result = pipe(text, truncation=True)[0]
    return {"label": result["label"], "score": float(result["score"])}
