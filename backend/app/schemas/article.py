"""
API response models. These are deliberately separate from RawArticle
(the ingestion/Kafka model) and ArticleORM (the database row) so that the
public API shape can evolve without dragging those along, and vice versa.
"""
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ArticleResponse(BaseModel):
    """One article as returned by the API."""

    # from_attributes lets us build this straight from an ArticleORM instance.
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None = None
    content: str | None = None
    url: str
    source: str
    author: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime

    # V2 (Phase 5) — null when the article was stored by the v1 processor.
    sentiment: str | None = None
    confidence: float | None = None
    impact_score: int | None = None
    processed_at: datetime | None = None

    # V3 (Phase 6) — null under v1/v2, or when that enrichment step failed.
    summary: str | None = None
    tickers: list[str] | None = None
    companies: list[str] | None = None
    category: str | None = None
    embedding_id: str | None = None


class PageMeta(BaseModel):
    """Pagination envelope shared by any list endpoint."""

    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_prev: bool


class FeedResponse(BaseModel):
    items: list[ArticleResponse]
    meta: PageMeta


class SourceCount(BaseModel):
    source: str
    count: int


class TrendingResponse(BaseModel):
    """Top sources by article volume within a recent time window."""

    window_hours: int
    total_articles: int
    top_sources: list[SourceCount]


class SentimentDayStats(BaseModel):
    date: date
    bullish: int = 0
    bearish: int = 0
    neutral: int = 0
    total: int = 0


class SentimentStatsResponse(BaseModel):
    generated_at: datetime
    days: list[SentimentDayStats]


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    k: int = Field(5, ge=1, le=50, description="how many results to return")
    sentiment: str | None = Field(
        None, pattern="^(bullish|bearish|neutral)$", description="optional filter"
    )


class SearchHit(BaseModel):
    score: float  # cosine similarity in [0, 1], higher = closer
    article: ArticleResponse


class SearchResponse(BaseModel):
    query: str
    count: int
    hits: list[SearchHit]


class AlertsResponse(BaseModel):
    threshold: int
    count: int
    alerts: list[ArticleResponse]


class HealthResponse(BaseModel):
    api: str
    redis: str
    kafka: str
    database: str
    kafka_topics: list[str] | None = None
