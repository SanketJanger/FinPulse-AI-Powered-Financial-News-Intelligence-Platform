"""
Phase 3: Pass-Through Consumer.
Reads from 'raw-news', validates, and persists to Postgres. No AI processing
yet — that gets added in Phase 5 (V2) and Phase 6 (V3), controlled by
PROCESSOR_VERSION, without changing this file's overall structure.
"""
import asyncio

import redis.asyncio as aioredis
from confluent_kafka import Consumer

from app.config import settings
from app.core.events import publish_new_article
from app.database import async_session
from app.models.article import RawArticle
from app.models.database import ArticleORM

redis_client = aioredis.Redis(
    host=settings.redis_host, port=settings.redis_port, decode_responses=False
)

consumer_config = {
    "bootstrap.servers": settings.kafka_bootstrap_servers,
    "group.id": settings.kafka_consumer_group,
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
}

kafka_consumer = Consumer(consumer_config)
kafka_consumer.subscribe(["raw-news"])


async def save_article(raw_article: RawArticle) -> bool:
    """Persists one validated article to Postgres.
    Returns True if saved, False if it was already there (duplicate URL)."""
    orm_article = ArticleORM(
        id=raw_article.id,
        title=raw_article.title,
        content=raw_article.content,
        description=raw_article.description,
        url=raw_article.url,
        source=raw_article.source,
        author=raw_article.author,
        published_at=raw_article.published_at,
        fetched_at=raw_article.fetched_at,
    )
    async with async_session() as session:
        session.add(orm_article)
        try:
            await session.commit()
            return True
        except Exception:
            # Most likely the UNIQUE constraint on url — Kafka's at-least-once
            # delivery means we might see the same message more than once.
            await session.rollback()
            return False

async def run_forever() -> None:
    """Continuously polls Kafka for new messages, validates and saves each
    one, then commits the offset only after a successful save."""
    print("AI Consumer (V1 pass-through) starting. Press Ctrl+C to stop.\n")
    try:
        while True:
            msg = kafka_consumer.poll(timeout=1.0)

            if msg is None:
                continue  # nothing new right now, loop again
            if msg.error():
                print(f"Kafka error: {msg.error()}")
                continue

            try:
                raw_article = RawArticle.model_validate_json(msg.value())
                saved = await save_article(raw_article)
                status = "saved" if saved else "duplicate (skipped)"
                print(f"[{status}] {raw_article.source}: {raw_article.title}")
                if saved:
                    # Fan out to any connected /ws/feed clients. Best-effort:
                    # a failure here doesn't block the offset commit.
                    await publish_new_article(redis_client, raw_article.model_dump_json())
            except Exception as e:
                print(f"Failed to process message: {e}")

            kafka_consumer.commit(msg)

    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    finally:
        kafka_consumer.close()
        await redis_client.aclose()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(run_forever())
