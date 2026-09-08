"""
v2 processor — FinBERT sentiment enrichment.

The model is loaded once in `startup()`. `process()` runs the (blocking)
inference in a worker thread so the consumer's event loop stays free.
Any failure for a single article is swallowed: we log it and return an
empty Enrichment, so the raw article is still persisted.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.analysis.finbert import FinBERTAnalyzer
from app.config import settings
from app.models.article import RawArticle
from app.processors.base import BaseArticleProcessor, Enrichment

logger = logging.getLogger("finpulse.processor.v2")


NEUTRAL_IMPACT = 3


def impact_from_sentiment(label: str, confidence: float) -> int:
    """Map a sentiment call to a 0-10 'market impact' bucket.

    Neutral carries no directional signal, so it floors at 3 regardless of
    how confident the model is. Only bullish/bearish scale with confidence.
    """
    if label == "neutral":
        return NEUTRAL_IMPACT
    if confidence > 0.9:
        return 8
    if confidence > 0.8:
        return 6
    if confidence > 0.7:
        return 5
    return NEUTRAL_IMPACT


def _text_for(article: RawArticle) -> str:
    """Headline carries most of the signal; append the description when we
    have one for a bit more context."""
    if article.description:
        return f"{article.title}. {article.description}"
    return article.title


class FinBERTProcessor(BaseArticleProcessor):
    version = "v2"

    def __init__(self, analyzer: FinBERTAnalyzer | None = None):
        self.analyzer = analyzer or FinBERTAnalyzer(model_name=settings.finbert_model)

    async def startup(self) -> None:
        # Loading pulls weights from disk/HF and can take a few seconds —
        # keep it off the event loop.
        await asyncio.to_thread(self.analyzer.load)

    async def process(self, article: RawArticle) -> Enrichment:
        try:
            result = await asyncio.to_thread(self.analyzer.analyze, _text_for(article))
        except Exception:
            logger.exception("FinBERT failed for %s — storing without sentiment", article.url)
            return Enrichment()

        return Enrichment(
            sentiment=result.label,
            confidence=round(result.confidence, 4),
            impact_score=impact_from_sentiment(result.label, result.confidence),
            processed_at=datetime.now(UTC),
        )
