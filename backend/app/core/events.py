"""
Cross-process fan-out of "a new article was saved".

The consumer runs in a different process from the API, so an in-memory
callback can't reach the WebSocket clients. Instead the consumer publishes
to a Redis pub/sub channel and every API worker's /ws/feed handler
subscribes to it.
"""
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger("finpulse.events")

CHANNEL = settings.new_articles_channel


async def publish_new_article(redis: Redis, article_json: str) -> None:
    """Best-effort broadcast. A pub/sub failure must not stop the consumer
    from committing the Kafka offset — the article is already safely in
    Postgres and will show up on the next /api/feed fetch regardless."""
    try:
        await redis.publish(CHANNEL, article_json)
    except (RedisError, OSError) as exc:
        logger.warning("failed to publish new article to %s: %s", CHANNEL, exc)
