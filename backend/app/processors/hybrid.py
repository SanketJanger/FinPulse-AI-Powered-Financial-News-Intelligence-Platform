"""
v3 processor — the hybrid pipeline.

Per article:
  FinBERT sentiment  ->  sentiment / confidence / impact_score
  Groq (1 call)      ->  2-sentence summary + category      (optional)
  regex + spaCy NER  ->  tickers / companies
  MiniLM embedding   ->  384-dim vector, upserted to ChromaDB
                         embedding_id = str(article.id)

Every stage is independently guarded: FinBERT staying up is the only hard
requirement; a failure in summary / entities / embedding / vector upsert
is logged and that field is left None, so the article is still stored and
still appears in /api/feed.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.analysis.embeddings import Embedder
from app.analysis.finbert import FinBERTAnalyzer
from app.analysis.groq_client import GroqSummarizer
from app.analysis.tickers import extract_entities
from app.analysis.vector_store import VectorStore
from app.config import settings
from app.models.article import RawArticle
from app.processors.base import BaseArticleProcessor, Enrichment
from app.processors.finbert import impact_from_sentiment

logger = logging.getLogger("finpulse.processor.v3")


def _sentiment_text(article: RawArticle) -> str:
    return f"{article.title}. {article.description}" if article.description else article.title


class HybridProcessor(BaseArticleProcessor):
    version = "v3"

    def __init__(
        self,
        analyzer: FinBERTAnalyzer | None = None,
        summarizer: GroqSummarizer | None = None,
        embedder: Embedder | None = None,
        vector_store: VectorStore | None = None,
    ):
        self.analyzer = analyzer or FinBERTAnalyzer(model_name=settings.finbert_model)
        self.summarizer = summarizer or GroqSummarizer(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            min_interval_ms=settings.groq_min_interval_ms,
        )
        self.embedder = embedder or Embedder(model_name=settings.embedding_model)
        self.vector_store = vector_store or VectorStore(
            host=settings.chroma_host,
            port=settings.chroma_port,
            collection=settings.chroma_collection,
        )
        self._vectors_ok = False

    async def startup(self) -> None:
        await asyncio.to_thread(self.analyzer.load)
        await asyncio.to_thread(self.embedder.load)
        try:
            await asyncio.to_thread(self.vector_store.connect)
            self._vectors_ok = True
        except Exception:
            logger.exception("ChromaDB unreachable — embeddings will be computed but not stored")
        logger.info(
            "v3 ready (groq=%s, chroma=%s)",
            "on" if self.summarizer.available else "off (no key)",
            "on" if self._vectors_ok else "off",
        )

    async def process(self, article: RawArticle) -> Enrichment:
        enr = Enrichment(processed_at=datetime.now(UTC))

        # 1. Sentiment (hard requirement) --------------------------------
        try:
            s = await asyncio.to_thread(self.analyzer.analyze, _sentiment_text(article))
            enr.sentiment = s.label
            enr.confidence = round(s.confidence, 4)
            enr.impact_score = impact_from_sentiment(s.label, s.confidence)
        except Exception:
            logger.exception("FinBERT failed for %s", article.url)

        # 2. Summary + category (optional) -----------------------------
        try:
            result = await self.summarizer.summarize(article.title, article.description)
            if result:
                enr.summary = result.summary
                enr.category = result.category
        except Exception:
            logger.exception("summary step failed for %s", article.url)

        # 3. Entity extraction ---------------------------------------
        try:
            blob = " ".join(filter(None, [article.title, article.description, article.content]))
            tickers, companies = await asyncio.to_thread(extract_entities, blob)
            enr.tickers = tickers or None
            enr.companies = companies or None
        except Exception:
            logger.exception("entity extraction failed for %s", article.url)

        # 4. Embedding + vector upsert ------------------------------
        try:
            text = article.title
            if enr.summary:
                text = f"{article.title}. {enr.summary}"
            elif article.description:
                text = f"{article.title}. {article.description}"
            vec = await asyncio.to_thread(self.embedder.encode_one, text)

            if self._vectors_ok:
                await self.vector_store.upsert(
                    doc_id=str(article.id),
                    embedding=vec,
                    document=text,
                    metadata={
                        "source": article.source,
                        "sentiment": enr.sentiment,
                        "category": enr.category,
                        "impact_score": enr.impact_score,
                        "tickers": enr.tickers,
                        "published_at": article.published_at.isoformat()
                        if article.published_at
                        else None,
                    },
                )
                enr.embedding_id = str(article.id)
        except Exception:
            logger.exception("embedding step failed for %s", article.url)

        return enr
