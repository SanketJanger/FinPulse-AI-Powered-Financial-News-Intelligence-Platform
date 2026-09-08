"""
GET /api/sentiment/stats — daily bullish / bearish / neutral counts.

Only rows the v2 processor has scored (processed_at IS NOT NULL) are
counted. Days are bucketed in UTC so the result doesn't shift with the
server's local timezone. Cached in Redis for `settings.sentiment_stats_ttl`
seconds (default 300 = 5 min).
"""
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis
from app.config import settings
from app.core.cache import cache_aside
from app.models.database import ArticleORM
from app.schemas.article import SentimentDayStats, SentimentStatsResponse

router = APIRouter(prefix="/api", tags=["sentiment"])

_DAY = func.date(func.timezone("UTC", ArticleORM.processed_at))
_VALID = ("bullish", "bearish", "neutral")


@router.get("/sentiment/stats", response_model=SentimentStatsResponse)
async def sentiment_stats(
    response: Response,
    days: int = Query(7, ge=1, le=90, description="How many days back to include"),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> SentimentStatsResponse:
    async def loader() -> dict:
        since = datetime.now(UTC) - timedelta(days=days)
        rows = (
            await db.execute(
                select(_DAY.label("day"), ArticleORM.sentiment, func.count().label("n"))
                .where(ArticleORM.processed_at.is_not(None), ArticleORM.processed_at >= since)
                .group_by(_DAY, ArticleORM.sentiment)
                .order_by(_DAY.desc())
            )
        ).all()

        buckets: dict[str, dict[str, int]] = defaultdict(lambda: {k: 0 for k in _VALID})
        order: list[str] = []
        for day, sentiment, n in rows:
            key = day.isoformat()
            if key not in buckets:
                order.append(key)
            if sentiment in _VALID:
                buckets[key][sentiment] += n

        days_out = [
            SentimentDayStats(date=day, total=sum(buckets[day].values()), **buckets[day])
            for day in order
        ]
        return SentimentStatsResponse(
            generated_at=datetime.now(UTC), days=days_out
        ).model_dump(mode="json")

    data, hit = await cache_aside(
        redis, f"sentiment:stats:v1:{days}", settings.sentiment_stats_ttl, loader
    )
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return SentimentStatsResponse.model_validate(data)
