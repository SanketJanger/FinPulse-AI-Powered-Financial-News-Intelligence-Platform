"""add V2 sentiment columns

Phase 5 (V2): FinBERT enrichment. All columns nullable so existing rows and
the v1 pass-through processor remain valid — a NULL sentiment simply means
"not analysed".

Revision ID: 0002_add_v2_sentiment_columns
Revises: 0001_initial_articles
Create Date: 2026-09-07
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_add_v2_sentiment_columns"
down_revision: str | None = "0001_initial_articles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("sentiment", sa.String(length=16), nullable=True))
    op.add_column("articles", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("articles", sa.Column("impact_score", sa.Integer(), nullable=True))
    op.add_column(
        "articles", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True)
    )
    # /api/feed?sentiment=... filters on this; /api/sentiment/stats groups by day.
    op.create_index("ix_articles_sentiment", "articles", ["sentiment"])
    op.create_index("ix_articles_processed_at", "articles", ["processed_at"])


def downgrade() -> None:
    op.drop_index("ix_articles_processed_at", table_name="articles")
    op.drop_index("ix_articles_sentiment", table_name="articles")
    op.drop_column("articles", "processed_at")
    op.drop_column("articles", "impact_score")
    op.drop_column("articles", "confidence")
    op.drop_column("articles", "sentiment")
