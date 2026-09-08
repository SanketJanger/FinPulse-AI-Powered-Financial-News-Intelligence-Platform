"""
POST /api/search — semantic search over article embeddings.

Flow: embed the query with the same MiniLM model the consumer used ->
ChromaDB cosine kNN -> hydrate the hits from Postgres (so the response
carries full article rows) -> return them ordered by similarity.

Returns 503 if the embedder or vector store isn't available (e.g. a V1/V2
deployment, or ChromaDB down).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_embedder, get_vector_store
from app.models.database import ArticleORM
from app.schemas.article import ArticleResponse, SearchHit, SearchRequest, SearchResponse

logger = logging.getLogger("finpulse.search")
router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
    embedder=Depends(get_embedder),
    vector_store=Depends(get_vector_store),
) -> SearchResponse:
    if embedder is None or vector_store is None or not vector_store.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic search unavailable (needs V3: embedder + ChromaDB)",
        )

    import asyncio

    query_vec = await asyncio.to_thread(embedder.encode_one, body.query)
    where = {"sentiment": body.sentiment} if body.sentiment else None

    try:
        hits = await vector_store.query(query_vec, k=body.k, where=where)
    except Exception as exc:  # noqa: BLE001
        logger.exception("vector query failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Vector store error"
        ) from exc

    if not hits:
        return SearchResponse(query=body.query, count=0, hits=[])

    # Hydrate from Postgres, preserving the similarity ordering.
    id_list = [h.id for h in hits]
    rows = (
        await db.scalars(select(ArticleORM).where(ArticleORM.id.in_(id_list)))
    ).all()
    by_id = {str(r.id): r for r in rows}

    results = [
        SearchHit(score=h.score, article=ArticleResponse.model_validate(by_id[h.id]))
        for h in hits
        if h.id in by_id
    ]
    return SearchResponse(query=body.query, count=len(results), hits=results)
