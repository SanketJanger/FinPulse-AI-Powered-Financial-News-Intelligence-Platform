"""
WS /ws/feed — pushes each newly-stored article to connected clients in
real time.

Mechanism: the consumer publishes article JSON to a Redis pub/sub channel
after every successful insert; this handler subscribes to that channel and
forwards each message. Two concurrent tasks run per connection — one
forwards pub/sub -> client, the other drains inbound frames purely to
notice when the client goes away — and whichever finishes first tears the
other down.

Message shapes sent to the client:
  {"type": "connected"}
  {"type": "article", "data": { ...ArticleResponse-ish JSON... }}
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from redis.exceptions import RedisError
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.api.deps import get_ws_redis
from app.config import settings

logger = logging.getLogger("finpulse.ws")
router = APIRouter(tags=["feed"])


async def _forward(websocket: WebSocket, pubsub) -> None:
    """Relay messages from the Redis channel to this client until the
    socket breaks."""
    while True:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if message is None:
            continue
        data = message["data"]
        if isinstance(data, (bytes, bytearray)):
            data = data.decode()
        try:
            payload = json.loads(data)
        except (TypeError, ValueError):
            payload = {"raw": data}
        await websocket.send_json({"type": "article", "data": payload})


async def _drain(websocket: WebSocket) -> None:
    """We don't expect inbound messages, but we must keep receiving so a
    client disconnect surfaces as WebSocketDisconnect instead of hanging."""
    while True:
        await websocket.receive_text()


@router.websocket("/ws/feed")
async def ws_feed(websocket: WebSocket, redis=Depends(get_ws_redis)) -> None:
    await websocket.accept()
    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(settings.new_articles_channel)
    except (RedisError, OSError) as exc:
        logger.warning("ws_feed: could not subscribe to Redis: %s", exc)
        await websocket.close(code=1011, reason="pub/sub unavailable")
        return

    await websocket.send_json({"type": "connected"})

    tasks = [
        asyncio.create_task(_forward(websocket, pubsub)),
        asyncio.create_task(_drain(websocket)),
    ]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        # Surface a non-disconnect error (e.g. Redis dropped) in the log.
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                logger.warning("ws_feed task ended with error: %s", exc)
    finally:
        for task in tasks:
            task.cancel()
        try:
            await pubsub.unsubscribe(settings.new_articles_channel)
            await pubsub.aclose()
        except (RedisError, OSError):
            pass
