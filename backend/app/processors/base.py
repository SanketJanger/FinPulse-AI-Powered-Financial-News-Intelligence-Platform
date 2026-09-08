"""
Article processors.

A processor is the single seam where each deployable version does its
version-specific enrichment of an incoming article, without the Kafka
consumer loop having to know which version is running:

    v1  PassThroughProcessor   — no enrichment (Phase 3/4)
    v2  FinBERTProcessor       — sentiment / confidence / impact_score (Phase 5)
    v3  ...                    — + LLM summary / embeddings (Phase 6)

`process()` returns an Enrichment; the consumer merges its non-None fields
onto the row it writes. A processor must never raise for a single bad
article — on failure it logs and returns an empty Enrichment so the raw
article is still stored.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel

from app.models.article import RawArticle


class Enrichment(BaseModel):
    """The V2+ columns. All optional — v1 returns this empty, and any
    individual v3 step (summary, entities, embedding) that fails just
    leaves its field None."""

    # v2
    sentiment: str | None = None
    confidence: float | None = None
    impact_score: int | None = None
    processed_at: datetime | None = None

    # v3
    summary: str | None = None
    tickers: list[str] | None = None
    companies: list[str] | None = None
    category: str | None = None
    embedding_id: str | None = None


class BaseArticleProcessor(ABC):
    #: "v1" | "v2" | "v3" — matches settings.processor_version
    version: str = "base"

    async def startup(self) -> None:
        """Load models / open resources. Called once before the consume
        loop starts. Default: nothing to do."""

    async def shutdown(self) -> None:
        """Release resources. Called once on shutdown. Default: no-op."""

    @abstractmethod
    async def process(self, article: RawArticle) -> Enrichment:
        """Return version-specific enrichment for one article."""
