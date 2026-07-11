"""
FinPulse FastAPI entry point.
Phase 1 goal: just prove the app boots and can see Kafka + Redis.
Real endpoints (feed, search, alerts, trending, websocket) get added in Phase 4.
"""
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from confluent_kafka.admin import AdminClient
from fastapi import FastAPI

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.Redis(host=settings.redis_host, port=settings.redis_port)
    yield
    await app.state.redis.close()


app = FastAPI(title="FinPulse API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    """Confirms the API process is up and can reach Kafka + Redis.
    This is the first thing to check after `docker compose up`."""
    status = {"api": "ok", "kafka": "unknown", "redis": "unknown"}

    # Redis check
    try:
        pong = await app.state.redis.ping()
        status["redis"] = "ok" if pong else "unreachable"
    except Exception as e:
        status["redis"] = f"error: {e}"

    # Kafka check (lightweight metadata fetch, 2s timeout)
    try:
        admin = AdminClient({"bootstrap.servers": settings.kafka_bootstrap_servers})
        metadata = admin.list_topics(timeout=2)
        status["kafka"] = "ok"
        status["kafka_topics"] = list(metadata.topics.keys())
    except Exception as e:
        status["kafka"] = f"error: {e}"

    return status


@app.get("/")
async def root():
    return {"message": "FinPulse API — Phase 1 skeleton running", "version": settings.processor_version}
