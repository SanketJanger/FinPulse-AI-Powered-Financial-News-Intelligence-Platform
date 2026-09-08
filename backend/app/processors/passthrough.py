"""
v1 processor — stores the article as-is, no enrichment.
"""
from app.models.article import RawArticle
from app.processors.base import BaseArticleProcessor, Enrichment


class PassThroughProcessor(BaseArticleProcessor):
    version = "v1"

    async def process(self, article: RawArticle) -> Enrichment:
        return Enrichment()
