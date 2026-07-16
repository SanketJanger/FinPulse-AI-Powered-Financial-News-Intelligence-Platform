"""
Async database engine and session factory for talking to Postgres.
Every service that needs to read/write the database imports from here,
rather than each creating its own separate connection.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)

async_session = async_sessionmaker(engine, expire_on_commit=False)
