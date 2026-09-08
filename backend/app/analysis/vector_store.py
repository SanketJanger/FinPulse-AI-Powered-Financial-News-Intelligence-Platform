"""
ChromaDB vector store wrapper.

One collection ("articles" by default), cosine space so a query distance
maps cleanly to a similarity score of `1 - distance` in [0, 1].

The chromadb HttpClient is synchronous; the public methods here wrap it in
asyncio.to_thread so the API / consumer event loop is never blocked.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("finpulse.vectorstore")


@dataclass(frozen=True)
class VectorHit:
    id: str
    score: float  # 1 - cosine_distance, higher = closer
    metadata: dict


class VectorStore:
    def __init__(self, host: str, port: int, collection: str = "articles"):
        self.host = host
        self.port = port
        self.collection_name = collection
        self._client = None
        self._collection = None

    @property
    def ready(self) -> bool:
        return self._collection is not None

    def connect(self) -> None:
        """Blocking — call once at startup (via to_thread from async)."""
        if self._collection is not None:
            return
        import chromadb

        self._client = chromadb.HttpClient(host=self.host, port=self.port)
        self._client.heartbeat()  # raises if the server isn't reachable
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name, metadata={"hnsw:space": "cosine"}
        )
        logger.info(
            "chroma connected: %s:%s/%s (count=%d)",
            self.host, self.port, self.collection_name, self._collection.count(),
        )

    async def upsert(
        self, doc_id: str, embedding: list[float], document: str, metadata: dict
    ) -> None:
        import asyncio

        if self._collection is None:
            raise RuntimeError("VectorStore.connect() has not been called")
        # Chroma rejects None / list values in metadata — coerce.
        clean = {k: _scalar(v) for k, v in metadata.items() if v is not None}
        await asyncio.to_thread(
            self._collection.upsert,
            ids=[doc_id],
            embeddings=[embedding],
            documents=[document],
            metadatas=[clean],
        )

    async def query(
        self, embedding: list[float], k: int, where: dict | None = None
    ) -> list[VectorHit]:
        import asyncio

        if self._collection is None:
            raise RuntimeError("VectorStore.connect() has not been called")
        res = await asyncio.to_thread(
            self._collection.query,
            query_embeddings=[embedding],
            n_results=k,
            where=where or None,
        )
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        hits = []
        for i, doc_id in enumerate(ids):
            dist = dists[i] if i < len(dists) else 1.0
            hits.append(
                VectorHit(id=doc_id, score=round(1.0 - float(dist), 4), metadata=metas[i] or {})
            )
        return hits

    async def count(self) -> int:
        import asyncio

        if self._collection is None:
            return 0
        return await asyncio.to_thread(self._collection.count)


def _scalar(v):
    if isinstance(v, (list, tuple, set)):
        return ", ".join(str(x) for x in v)
    if isinstance(v, (str, int, float, bool)):
        return v
    return str(v)
