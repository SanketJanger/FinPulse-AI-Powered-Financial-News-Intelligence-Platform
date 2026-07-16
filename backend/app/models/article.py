"""
Pydantic models describing the shape of a news article.
RawArticle: what we get from NewsAPI/RSS, before any AI processing.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RawArticle(BaseModel):
    """Represents one article exactly as fetched, before AI processing.
    This is what gets published to the 'raw-news' Kafka topic."""

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(..., min_length=1, max_length=500)
    content: Optional[str] = Field(default=None, max_length=50000)
    description: Optional[str] = Field(default=None, max_length=2000)
    url: str = Field(..., description="Unique identifier for deduplication")
    source: str = Field(..., description="News source name, e.g. 'NewsAPI' or 'Reuters RSS'")
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
