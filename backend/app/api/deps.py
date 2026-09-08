"""
Shared FastAPI dependencies for the API routes.
"""
from redis.asyncio import Redis
from starlette.requests import Request
from starlette.websockets import WebSocket

# Re-exported so routes can `from app.api.deps import get_db`.
from app.database import get_db  # noqa: F401


def get_redis(request: Request) -> Redis:
    """The Redis client is created once in the app lifespan and stashed on
    app.state; hand routes that same pooled client."""
    return request.app.state.redis


def get_embedder(request: Request):
    """Embedder loaded in the lifespan, or None if sentence-transformers
    wasn't available / failed to load (V1/V2 deployments)."""
    return getattr(request.app.state, "embedder", None)


def get_vector_store(request: Request):
    """ChromaDB wrapper from the lifespan, or None if it couldn't connect."""
    return getattr(request.app.state, "vector_store", None)


def get_ws_redis(websocket: WebSocket) -> Redis:
    """Same client, but WebSocket handlers get `websocket` instead of
    `request` injected, so they need their own accessor."""
    return websocket.app.state.redis
