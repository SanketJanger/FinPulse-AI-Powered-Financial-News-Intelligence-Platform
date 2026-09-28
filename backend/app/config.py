"""
Centralized application configuration using Pydantic Settings.
Loads from .env file; all services import `settings` from here.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    environment: Literal["development", "production"] = "development"
    processor_version: Literal["v1", "v2", "v3"] = "v1"

    # API
    # JSON list in .env, e.g. CORS_ORIGINS=["http://localhost:3000","https://app.finpulse.io"]
    cors_origins: list[str] = ["http://localhost:3000"]
    feed_cache_ttl: int = 60  # seconds the /api/feed response stays cached in Redis
    sentiment_stats_ttl: int = 300  # /api/sentiment/stats cache (5 min)

    # AI — V2 (Phase 5)
    finbert_model: str = "ProsusAI/finbert"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9094"
    kafka_consumer_group: str = "finpulse-ai-consumer"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    # Pub/sub channel the consumer publishes freshly-saved articles to,
    # and the /ws/feed WebSocket subscribes to for real-time push.
    new_articles_channel: str = "finpulse:new-articles"

    # AI — V3 (Phase 6)
    groq_model: str = "openai/gpt-oss-20b"
    groq_min_interval_ms: int = 2100  # client-side throttle for Groq free tier (~30 rpm)

    # Evaluation (Phase 8) — OpenAI is the ground-truth labeller / RAG judge,
    # kept separate from every model under test.
    openai_api_key: str = ""
    eval_label_model: str = "gpt-4o-mini"
    eval_groq_model: str = "openai/gpt-oss-120b"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dim
    chroma_collection: str = "articles"
    alert_impact_threshold: int = 8  # impact_score >= this -> publish to 'alerts'

    # Database
    database_url: str = ""
    supabase_url: str = ""
    supabase_key: str = ""

    # News sources
    newsapi_key: str = ""

    # AI
    groq_api_key: str = ""

    # Vector DB (host port 8002 -> container 8000; API owns host 8000)
    chroma_host: str = "localhost"
    chroma_port: int = 8002


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — import this everywhere instead of
    instantiating Settings() directly, so .env is only parsed once."""
    return Settings()


settings = get_settings()
