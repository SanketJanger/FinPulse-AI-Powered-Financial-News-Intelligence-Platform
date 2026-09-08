"""
GET /health — liveness + dependency probe.

Same behaviour as the Phase 1 version, now with a Pydantic response model
and a Postgres check added (Phase 3 introduced the database dependency).
Never raises: a dependency being down is reported in the body, not as a
5xx, so an orchestrator can distinguish "process alive" from "fully ready".
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis
from app.config import settings
from app.schemas.article import HealthResponse

router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthResponse)
async def health(
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> HealthResponse:
    result = HealthResponse(api="ok", redis="unknown", kafka="unknown", database="unknown")

    try:
        pong = await redis.ping()
        result.redis = "ok" if pong else "unreachable"
    except Exception as exc:  # noqa: BLE001 - report, don't crash
        result.redis = f"error: {exc}"

    try:
        await db.execute(text("SELECT 1"))
        result.database = "ok"
    except Exception as exc:  # noqa: BLE001
        result.database = f"error: {exc}"

    try:
        # Imported lazily so a missing/broken kafka lib can't stop the
        # process from booting and serving /health at all.
        from confluent_kafka.admin import AdminClient

        admin = AdminClient({"bootstrap.servers": settings.kafka_bootstrap_servers})
        metadata = admin.list_topics(timeout=2)
        result.kafka = "ok"
        result.kafka_topics = sorted(metadata.topics.keys())
    except Exception as exc:  # noqa: BLE001
        result.kafka = f"error: {exc}"

    return result
