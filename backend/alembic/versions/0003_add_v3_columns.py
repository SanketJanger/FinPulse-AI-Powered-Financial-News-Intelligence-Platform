"""add V3 columns

Phase 6 (V3): LLM summary, extracted entities, category, and a pointer to
the article's vector in ChromaDB. All nullable — v1/v2 rows and any row
whose enrichment step failed simply leave them NULL.

Revision ID: 0003_add_v3_columns
Revises: 0002_add_v2_sentiment_columns
Create Date: 2026-09-07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_add_v3_columns"
down_revision: str | None = "0002_add_v2_sentiment_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "articles",
        sa.Column("tickers", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column("companies", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.add_column("articles", sa.Column("category", sa.String(length=32), nullable=True))
    op.add_column("articles", sa.Column("embedding_id", sa.Text(), nullable=True))
    op.create_index("ix_articles_category", "articles", ["category"])


def downgrade() -> None:
    op.drop_index("ix_articles_category", table_name="articles")
    op.drop_column("articles", "embedding_id")
    op.drop_column("articles", "category")
    op.drop_column("articles", "companies")
    op.drop_column("articles", "tickers")
    op.drop_column("articles", "summary")
