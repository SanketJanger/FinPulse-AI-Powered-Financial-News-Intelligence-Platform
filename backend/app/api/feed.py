"""
GET /api/feed — paginated, filterable list of stored articles.

Ordering key is coalesce(published_at, fetched_at) so rows with no
publisher timestamp (common for RSS) still sort sensibly, and the same
expression is used for date filtering so the filter matches the sort.

Cached read-through in Redis for `settings.feed_cache_ttl` seconds
(default 60). The cache key includes every query parameter, so different
filter/page combinations are cached independently.
"""
import logging
from datetime import datetime
from math import ceil

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis
from app.config import settings
from app.core.cache import cache_aside
from app.models.database import ArticleORM
from app.schemas.article import ArticleResponse, FeedResponse, PageMeta

logger = logging.getLogger("finpulse.feed")
router = APIRouter(prefix="/api", tags=["feed"])

# coalesce(published_at, fetched_at) — used for both sort and date filter.
_ORDER_KEY = func.coalesce(ArticleORM.published_at, ArticleORM.fetched_at)


def _cache_key(
    page: int,
    page_size: int,
    source: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    sentiment: str | None,
) -> str:
    return (
        "feed:v2:"
        f"{page}:{page_size}:"
        f"{source or '*'}:"
        f"{date_from.isoformat() if date_from else '*'}:"
        f"{date_to.isoformat() if date_to else '*'}:"
        f"{sentiment or '*'}"
    )


@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    response: Response,
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    source: str | None = Query(None, description="Exact source name, e.g. 'CNBC RSS'"),
    date_from: datetime | None = Query(
        None, description="Only articles at/after this ISO timestamp"
    ),
    date_to: datetime | None = Query(
        None, description="Only articles at/before this ISO timestamp"
    ),
    sentiment: str | None = Query(
        None,
        pattern="^(bullish|bearish|neutral)$",
        description="V2 filter: bullish | bearish | neutral",
    ),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> FeedResponse:
    async def loader() -> dict:
        filters = []
        if source is not None:
            filters.append(ArticleORM.source == source)
        if date_from is not None:
            filters.append(_ORDER_KEY >= date_from)
        if date_to is not None:
            filters.append(_ORDER_KEY <= date_to)
        if sentiment is not None:
            filters.append(ArticleORM.sentiment == sentiment)

        total = await db.scalar(
            select(func.count()).select_from(ArticleORM).where(*filters)
        )

        rows = (
            await db.scalars(
                select(ArticleORM)
                .where(*filters)
                .order_by(_ORDER_KEY.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()

        total_pages = ceil(total / page_size) if total else 0
        payload = FeedResponse(
            items=[ArticleResponse.model_validate(r) for r in rows],
            meta=PageMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1,
            ),
        )
        return payload.model_dump(mode="json")

    data, hit = await cache_aside(
        redis,
        _cache_key(page, page_size, source, date_from, date_to, sentiment),
        settings.feed_cache_ttl,
        loader,
    )
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return FeedResponse.model_validate(data)
