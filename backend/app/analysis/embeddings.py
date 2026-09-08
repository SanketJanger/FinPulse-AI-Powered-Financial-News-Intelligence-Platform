"""
sentence-transformers embedding wrapper.

`all-MiniLM-L6-v2` -> 384-dim vectors. Model loads once (`.load()` at
startup); `.encode()` is blocking, so async callers use asyncio.to_thread.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("finpulse.embeddings")


class Embedder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self.dim: int | None = None

    @property
    def ready(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        logger.info("loading embedding model '%s' ...", self.model_name)
        self._model = SentenceTransformer(self.model_name)
        self.dim = self._model.get_sentence_embedding_dimension()
        logger.info("embedding model ready (dim=%d)", self.dim)

    def encode(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            raise RuntimeError("Embedder.load() has not been called")
        vecs = self._model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )
        return vecs.tolist()

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0]
