import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("bos.requests")

_ALLOWED_METHODS = "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS"


class TraceBlockMiddleware(BaseHTTPMiddleware):
    """RFC 9110: TRACE must return 405 with an Allow header."""
    async def dispatch(self, request: Request, call_next):
        if request.method == "TRACE":
            return Response(
                content="Method Not Allowed",
                status_code=405,
                headers={"Allow": _ALLOWED_METHODS},
            )
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:8]
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000)
        logger.info(
            "[%s] %s %s → %d (%dms)",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-Id"] = request_id
        return response
