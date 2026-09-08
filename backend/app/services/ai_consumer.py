"""
AI Consumer.
Reads from 'raw-news', validates, runs the version-specific processor
(PROCESSOR_VERSION: v1 pass-through, v2 FinBERT sentiment, v3 later),
persists to Postgres, and fans new rows out to /ws/feed via Redis pub/sub.

The processor is the only version-aware piece — this loop is unchanged
across V1/V2/V3.
"""
import asyncio
import json

import redis.asyncio as aioredis
from confluent_kafka import Consumer

from app.config import settings
from app.core.events import publish_new_article
from app.database import async_session
from app.models.article import RawArticle
from app.models.database import ArticleORM
from app.processors import Enrichment, get_processor

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


async def save_article(raw_article: RawArticle, enrichment: Enrichment) -> bool:
    """Persists one validated + enriched article to Postgres.
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
        sentiment=enrichment.sentiment,
        confidence=enrichment.confidence,
        impact_score=enrichment.impact_score,
        processed_at=enrichment.processed_at,
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


def _ws_payload(raw_article: RawArticle, enrichment: Enrichment) -> str:
    """Article JSON for /ws/feed clients, with any enrichment merged in."""
    data = raw_article.model_dump(mode="json")
    data.update(enrichment.model_dump(mode="json", exclude_none=True))
    return json.dumps(data)


async def run_forever() -> None:
    """Continuously polls Kafka for new messages, processes and saves each
    one, then commits the offset only after handling it."""
    processor = get_processor(settings.processor_version)
    print(f"AI Consumer starting (PROCESSOR_VERSION={settings.processor_version}). Loading processor...")
    await processor.startup()
    print(f"Processor '{processor.version}' ready. Press Ctrl+C to stop.\n")

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
                enrichment = await processor.process(raw_article)
                saved = await save_article(raw_article, enrichment)
                status = "saved" if saved else "duplicate (skipped)"
                extra = f" [{enrichment.sentiment} {enrichment.confidence}]" if enrichment.sentiment else ""
                print(f"[{status}]{extra} {raw_article.source}: {raw_article.title}")
                if saved:
                    # Fan out to any connected /ws/feed clients. Best-effort:
                    # a failure here doesn't block the offset commit.
                    await publish_new_article(redis_client, _ws_payload(raw_article, enrichment))
            except Exception as e:
                print(f"Failed to process message: {e}")

            kafka_consumer.commit(msg)

    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    finally:
        await processor.shutdown()
        kafka_consumer.close()
        await redis_client.aclose()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(run_forever())
