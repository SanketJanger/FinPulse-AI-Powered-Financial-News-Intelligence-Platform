"""
Request logging middleware. Logs one line per HTTP request with method,
path, status code and wall-clock duration. Kept as a Starlette
BaseHTTPMiddleware so it wraps every route including the ones added later.
"""
import logging
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("finpulse.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # The global exception handler turns this into a 500 response;
            # we just make sure the failure still shows up in the access log.
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "%s %s -> 500 (%.1fms)", request.method, request.url.path, elapsed_ms
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
