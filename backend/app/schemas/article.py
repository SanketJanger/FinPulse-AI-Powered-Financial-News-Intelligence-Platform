"""
API response models. These are deliberately separate from RawArticle
(the ingestion/Kafka model) and ArticleORM (the database row) so that the
public API shape can evolve without dragging those along, and vice versa.
"""
from datetime import datetime
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


class HealthResponse(BaseModel):
    api: str
    redis: str
    kafka: str
    database: str
    kafka_topics: list[str] | None = None
