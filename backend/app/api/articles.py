"""
GET /api/article/{id} — fetch a single article by its UUID.

An invalid UUID string is rejected by FastAPI's path validation with a
422 before this handler runs; a well-formed UUID that isn't in the table
returns 404.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.database import ArticleORM
from app.schemas.article import ArticleResponse

router = APIRouter(prefix="/api", tags=["articles"])


@router.get(
    "/article/{article_id}",
    response_model=ArticleResponse,
    responses={404: {"description": "No article with that id"}},
)
async def get_article(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ArticleResponse:
    article = await db.get(ArticleORM, article_id)
    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article {article_id} not found",
        )
    return ArticleResponse.model_validate(article)
