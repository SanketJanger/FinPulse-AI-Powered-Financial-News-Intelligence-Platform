"""
GET /api/alerts — articles that crossed the high-impact threshold.

The consumer streams these to the Kafka 'alerts' topic in real time; this
endpoint is the durable view, read straight from the articles table so it
can never drift from what actually triggered an alert.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import settings
from app.models.database import ArticleORM
from app.schemas.article import AlertsResponse, ArticleResponse

router = APIRouter(prefix="/api", tags=["alerts"])

_RECENCY = func.coalesce(ArticleORM.processed_at, ArticleORM.fetched_at)


@router.get("/alerts", response_model=AlertsResponse)
async def get_alerts(
    limit: int = Query(50, ge=1, le=200),
    since: datetime | None = Query(None, description="only alerts at/after this ISO timestamp"),
    db: AsyncSession = Depends(get_db),
) -> AlertsResponse:
    filters = [ArticleORM.impact_score >= settings.alert_impact_threshold]
    if since is not None:
        filters.append(_RECENCY >= since)

    rows = (
        await db.scalars(
            select(ArticleORM).where(*filters).order_by(_RECENCY.desc()).limit(limit)
        )
    ).all()

    return AlertsResponse(
        threshold=settings.alert_impact_threshold,
        count=len(rows),
        alerts=[ArticleResponse.model_validate(r) for r in rows],
    )
