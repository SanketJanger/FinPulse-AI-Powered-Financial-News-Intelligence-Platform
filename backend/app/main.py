"""
FinPulse FastAPI entry point.

Assembles the app: lifespan-managed Redis + DB engine (+ embedder /
ChromaDB for V3 semantic search), CORS, request logging, consistent error
responses, and the read/stream routes.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import alerts, articles, feed, health, search, sentiment, trending, websocket
from app.config import settings
from app.core.middleware import RequestLoggingMiddleware
from app.database import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
)
logger = logging.getLogger("finpulse")


async def _init_semantic_search(app: FastAPI) -> None:
    """Best-effort: load the query embedder and connect to ChromaDB so
    POST /api/search works. On any failure (deps missing, Chroma down)
    leave them unset — the endpoint then returns 503."""
    app.state.embedder = None
    app.state.vector_store = None
    try:
        from app.analysis.embeddings import Embedder
        from app.analysis.vector_store import VectorStore

        embedder = Embedder(model_name=settings.embedding_model)
        await asyncio.to_thread(embedder.load)

        store = VectorStore(
            host=settings.chroma_host,
            port=settings.chroma_port,
            collection=settings.chroma_collection,
        )
        await asyncio.to_thread(store.connect)

        app.state.embedder = embedder
        app.state.vector_store = store
        logger.info("semantic search ready")
    except Exception as exc:  # noqa: BLE001
        logger.warning("semantic search disabled: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.Redis(
        host=settings.redis_host, port=settings.redis_port, decode_responses=False
    )
    logger.info("FinPulse API starting (env=%s, version=%s)", settings.environment, settings.processor_version)
    await _init_semantic_search(app)
    yield
    await app.state.redis.aclose()
    await engine.dispose()
    logger.info("FinPulse API stopped")


app = FastAPI(title="FinPulse API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)


# ── Error handling ───────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """422 — bad query params / path values. Keep FastAPI's rich error
    list, just under a stable top-level shape."""
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    """404 and any other explicitly-raised HTTPException."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    """500 — anything we didn't anticipate. Log the full traceback, return
    a generic message so internals don't leak to the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Routes ───────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(feed.router)
app.include_router(articles.router)
app.include_router(trending.router)
app.include_router(sentiment.router)
app.include_router(search.router)
app.include_router(alerts.router)
app.include_router(websocket.router)


@app.get("/", tags=["ops"])
async def root():
    return {
        "service": "FinPulse API",
        "version": app.version,
        "processor_version": settings.processor_version,
        "docs": "/docs",
    }
