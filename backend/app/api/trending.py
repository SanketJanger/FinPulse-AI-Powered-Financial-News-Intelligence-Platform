"""
GET /api/trending — top sources by article volume in a recent window.

Same cache-aside treatment as /api/feed: this is a GROUP BY aggregate, so
caching it for a minute takes real load off Postgres when a dashboard
polls it.
"""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis
from app.config import settings
from app.core.cache import cache_aside
from app.models.database import ArticleORM
from app.schemas.article import SourceCount, TrendingResponse

router = APIRouter(prefix="/api", tags=["trending"])

_ORDER_KEY = func.coalesce(ArticleORM.published_at, ArticleORM.fetched_at)


@router.get("/trending", response_model=TrendingResponse)
async def get_trending(
    response: Response,
    window_hours: int = Query(24, ge=1, le=168, description="Look-back window in hours"),
    limit: int = Query(10, ge=1, le=50, description="Number of sources to return"),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> TrendingResponse:
    async def loader() -> dict:
        since = datetime.now(UTC) - timedelta(hours=window_hours)
        rows = (
            await db.execute(
                select(ArticleORM.source, func.count().label("count"))
                .where(_ORDER_KEY >= since)
                .group_by(ArticleORM.source)
                .order_by(func.count().desc())
                .limit(limit)
            )
        ).all()

        top = [SourceCount(source=s, count=c) for s, c in rows]
        payload = TrendingResponse(
            window_hours=window_hours,
            total_articles=sum(sc.count for sc in top),
            top_sources=top,
        )
        return payload.model_dump(mode="json")

    data, hit = await cache_aside(
        redis, f"trending:v1:{window_hours}:{limit}", settings.feed_cache_ttl, loader
    )
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return TrendingResponse.model_validate(data)
