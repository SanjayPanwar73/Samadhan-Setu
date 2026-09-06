"""Shared sentence-transformer model for the AI modules."""

from functools import lru_cache


@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")
