"""
Similarity search over complaint text using sentence-transformers embeddings
and an in-memory FAISS index. The index is persisted to disk so it survives
app restarts, and rebuilt/loaded at startup.
"""

import os

import numpy as np

from app.ai.embeddings import get_embedding_model

INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "faiss_index.bin")
ID_MAP_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "faiss_ids.npy")

EMBED_DIM = 384  # all-MiniLM-L6-v2 output dimension


class SimilarityIndex:
    """Wraps a FAISS index + parallel array of complaint IDs."""

    def __init__(self):
        import faiss

        self.faiss = faiss
        if os.path.exists(INDEX_PATH) and os.path.exists(ID_MAP_PATH):
            self.index = faiss.read_index(INDEX_PATH)
            self.ids = np.load(ID_MAP_PATH).tolist()
        else:
            self.index = faiss.IndexFlatL2(EMBED_DIM)
            self.ids = []

    def add(self, complaint_id: int, text: str):
        embedder = get_embedding_model()
        vector = embedder.encode([text]).astype("float32")
        self.index.add(vector)
        self.ids.append(complaint_id)
        self._persist()

    def search(self, text: str, top_k: int = 5) -> list[tuple[int, float]]:
        if self.index.ntotal == 0:
            return []
        embedder = get_embedding_model()
        vector = embedder.encode([text]).astype("float32")
        distances, indices = self.index.search(vector, min(top_k, self.index.ntotal))
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            results.append((self.ids[idx], float(dist)))
        return results

    def _persist(self):
        self.faiss.write_index(self.index, INDEX_PATH)
        np.save(ID_MAP_PATH, np.array(self.ids))


_index_singleton: SimilarityIndex | None = None


def get_index() -> SimilarityIndex:
    global _index_singleton
    if _index_singleton is None:
        _index_singleton = SimilarityIndex()
    return _index_singleton


def find_similar(text: str, top_k: int = 5) -> list[tuple[int, float]]:
    """Returns [(complaint_id, distance), ...] sorted by similarity (lower distance = closer)."""
    return get_index().search(text, top_k)
