"""Shared sentence-transformer model for the AI modules.

The model name comes from ``EMBEDDING_MODEL`` (default all-MiniLM-L6-v2). A multilingual
option such as paraphrase-multilingual-MiniLM-L12-v2 also yields 384 dimensions and
handles Hindi/Hinglish better. Changing it requires re-embedding existing complaints.
"""

from app.ai.runtime import load_model, shared_model
from app.core.config import settings


@shared_model
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    name = settings.EMBEDDING_MODEL
    hub_id = name if "/" in name else f"sentence-transformers/{name}"
    return load_model(name, SentenceTransformer, hub_id=hub_id)
