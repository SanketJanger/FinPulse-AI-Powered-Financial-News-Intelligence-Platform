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

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9094"
    kafka_consumer_group: str = "finpulse-ai-consumer"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # Database
    database_url: str = ""
    supabase_url: str = ""
    supabase_key: str = ""

    # News sources
    newsapi_key: str = ""

    # AI
    groq_api_key: str = ""

    # Vector DB
    chroma_host: str = "localhost"
    chroma_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — import this everywhere instead of
    instantiating Settings() directly, so .env is only parsed once."""
    return Settings()


settings = get_settings()
