"""Retrieval-augmented resolution suggestions.

Retrieval works without Ollama. Generation is an optional local enhancement and
never blocks the advisory endpoint when Ollama is unavailable.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any

import numpy as np

from app.ai.embeddings import get_embedding_model

INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "resolution_index.faiss")
ID_MAP_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "resolution_index_ids.npy"
)
METADATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "resolution_index_metadata.json"
)
EMBED_DIM = 384
SIMILARITY_THRESHOLD = 0.5


def embed_resolution(resolution_text: str) -> np.ndarray:
    vector = get_embedding_model().encode([resolution_text]).astype("float32")
    import faiss

    faiss.normalize_L2(vector)
    return vector[0]


class ResolutionIndex:
    def __init__(self):
        import faiss

        self.faiss = faiss
        if os.path.exists(INDEX_PATH) and os.path.exists(ID_MAP_PATH):
            self.index = faiss.read_index(INDEX_PATH)
            self.ids = np.load(ID_MAP_PATH).astype("int64").tolist()
        else:
            self.index = faiss.IndexFlatIP(EMBED_DIM)
            self.ids = []
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> dict[str, dict[str, Any]]:
        if not os.path.exists(METADATA_PATH):
            return {}
        with open(METADATA_PATH, "r", encoding="utf-8") as metadata_file:
            return json.load(metadata_file)

    def add(self, resolution_id: int, embedding: np.ndarray) -> None:
        vector = np.asarray(embedding, dtype="float32").reshape(1, -1).copy()
        self.faiss.normalize_L2(vector)
        self.index.add(vector)
        self.ids.append(resolution_id)
        self._persist()

    def _persist(self) -> None:
        self.faiss.write_index(self.index, INDEX_PATH)
        np.save(ID_MAP_PATH, np.asarray(self.ids, dtype="int64"))
        with open(METADATA_PATH, "w", encoding="utf-8") as metadata_file:
            json.dump(self.metadata, metadata_file)

    def search(self, complaint_text: str, top_k: int) -> list[dict]:
        if self.index.ntotal == 0:
            return []
        query = embed_resolution(complaint_text).reshape(1, -1)
        scores, indices = self.index.search(query, min(top_k, self.index.ntotal))
        results = []
        for score, index in zip(scores[0], indices[0]):
            if index < 0 or float(score) < SIMILARITY_THRESHOLD:
                continue
            resolution_id = self.ids[index]
            metadata = self.metadata.get(str(resolution_id))
            if metadata:
                results.append(
                    {
                        "complaint_id": metadata["complaint_id"],
                        "resolution_text": metadata["resolution_text"],
                        "similarity": round(float(score), 4),
                    }
                )
        return results


_resolution_index: ResolutionIndex | None = None


def get_resolution_index() -> ResolutionIndex:
    global _resolution_index
    if _resolution_index is None:
        _resolution_index = ResolutionIndex()
    return _resolution_index


def load_resolution_index() -> ResolutionIndex:
    """Initialize the singleton during application startup."""
    return get_resolution_index()


def add_resolution_to_index(
    resolution_id: int, embedding: np.ndarray, complaint_id: int | None = None,
    resolution_text: str | None = None,
) -> None:
    index = get_resolution_index()
    if resolution_id in index.ids:
        return
    if complaint_id is None or resolution_text is None:
        from app.core.database import SessionLocal
        from app.models.resolution_history import ResolutionHistory

        db = SessionLocal()
        try:
            record = db.query(ResolutionHistory).filter(ResolutionHistory.id == resolution_id).first()
            if record is None:
                return
            complaint_id = record.complaint_id
            resolution_text = record.resolution_text
        finally:
            db.close()
    index.metadata[str(resolution_id)] = {
        "complaint_id": complaint_id,
        "resolution_text": resolution_text,
    }
    index.add(resolution_id, embedding)


def retrieve_similar_resolutions(
    complaint_text: str, top_k: int = 3
) -> list[dict]:
    return get_resolution_index().search(complaint_text, top_k)


def generate_suggestion(
    complaint_text: str, retrieved: list[dict]
) -> str | None:
    if not retrieved:
        return None
    prompt = (
        "You are assisting municipal complaint staff. Suggest a concise, practical "
        "resolution action based only on this complaint and the similar resolved cases. "
        "Do not claim that the suggestion is certain.\n\n"
        f"New complaint:\n{complaint_text}\n\n"
        "Similar resolved cases:\n"
        + "\n".join(
            f"- {case['resolution_text']}" for case in retrieved
        )
        + "\n\nSuggested action:"
    )
    payload = json.dumps({"model": "phi3", "prompt": prompt, "stream": False}).encode()
    request = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
        suggestion = result.get("response")
        return suggestion.strip() if isinstance(suggestion, str) and suggestion.strip() else None
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
