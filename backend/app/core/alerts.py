"""
High-impact alerts.

When an enriched article scores impact_score >= settings.alert_impact_threshold
the consumer publishes a compact alert to the Kafka 'alerts' topic — the
streaming interface for any downstream notifier. The durable, queryable
record is just the article row itself (GET /api/alerts reads Postgres),
so there's no separate alerts table to keep in sync.
"""
from __future__ import annotations

import json
import logging

from confluent_kafka import Producer

from app.config import settings
from app.models.article import RawArticle
from app.processors import Enrichment

logger = logging.getLogger("finpulse.alerts")

ALERTS_TOPIC = "alerts"


def make_alert_producer() -> Producer:
    return Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})


def should_alert(enrichment: Enrichment) -> bool:
    return (
        enrichment.impact_score is not None
        and enrichment.impact_score >= settings.alert_impact_threshold
    )


def publish_alert(producer: Producer, article: RawArticle, enrichment: Enrichment) -> None:
    """Best-effort. A produce failure is logged, never raised — the article
    is already saved and still shows up under GET /api/alerts."""
    payload = {
        "article_id": str(article.id),
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "sentiment": enrichment.sentiment,
        "confidence": enrichment.confidence,
        "impact_score": enrichment.impact_score,
        "summary": enrichment.summary,
        "tickers": enrichment.tickers,
        "category": enrichment.category,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "detected_at": (enrichment.processed_at.isoformat() if enrichment.processed_at else None),
    }
    try:
        producer.produce(
            ALERTS_TOPIC,
            key=str(article.id),
            value=json.dumps(payload),
        )
        producer.poll(0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to publish alert for %s: %s", article.url, exc)
