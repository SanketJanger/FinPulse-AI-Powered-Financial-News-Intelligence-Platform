"""
Async database engine and session factory for talking to Postgres.
Every service that needs to read/write the database imports from here,
rather than each creating its own separate connection.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields one AsyncSession per request and always
    closes it afterwards, even if the endpoint raises. Read-only endpoints
    never commit, so there's no commit here — writers commit explicitly."""
    async with async_session() as session:
        yield session
