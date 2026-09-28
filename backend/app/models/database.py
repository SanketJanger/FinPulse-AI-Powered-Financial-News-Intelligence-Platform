"""
SQLAlchemy ORM models — the database-table equivalent of our Pydantic
RawArticle model. Pydantic validates data shape in Python; SQLAlchemy
maps Python objects to actual database rows.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Every ORM model inherits from this. SQLAlchemy uses it to keep
    track of all defined tables."""
    pass


class ArticleORM(Base):
    __tablename__ = "articles"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # ── V2 (Phase 5): FinBERT enrichment ──────────────────────────────
    # All nullable. NULL means "not analysed" — true for every row written
    # by the v1 pass-through processor, and for rows predating Phase 5.
    sentiment: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    impact_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # ── V3 (Phase 6): LLM summary + entities + embedding pointer ───────
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tickers: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    companies: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    embedding_id: Mapped[str | None] = mapped_column(Text, nullable=True)
