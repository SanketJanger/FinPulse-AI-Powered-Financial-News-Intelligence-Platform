"""
Processor factory. `PROCESSOR_VERSION` in the environment (via
settings.processor_version) decides which one the consumer runs.
"""
from app.config import settings
from app.processors.base import BaseArticleProcessor, Enrichment
from app.processors.passthrough import PassThroughProcessor

__all__ = ["BaseArticleProcessor", "Enrichment", "get_processor"]


def get_processor(version: str | None = None) -> BaseArticleProcessor:
    version = (version or settings.processor_version).lower()

    if version == "v1":
        return PassThroughProcessor()

    if version == "v2":
        # Imported lazily so v1 deployments don't need torch/transformers
        # installed just to start the consumer.
        from app.processors.finbert import FinBERTProcessor

        return FinBERTProcessor()

    if version == "v3":
        # Lazy for the same reason — plus groq / spacy / sentence-transformers
        # / chromadb.
        from app.processors.hybrid import HybridProcessor

        return HybridProcessor()

    raise ValueError(f"Unknown PROCESSOR_VERSION {version!r} (expected v1, v2 or v3)")
