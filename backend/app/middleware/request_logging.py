"""
Request logging middleware for tracking API requests and performance.
"""
import time
import uuid
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("sakra.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs every HTTP request with:
    - HTTP method and path
    - Response status code
    - Request duration in milliseconds
    - Unique request ID (also added to response headers)
    - Client IP address
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        # Extract client IP, considering proxies
        client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not client_ip and request.client:
            client_ip = request.client.host

        # Store request_id in request state for downstream access
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "request_error | method=%s path=%s duration_ms=%.2f request_id=%s client_ip=%s error=%s",
                request.method,
                request.url.path,
                duration_ms,
                request_id,
                client_ip,
                str(exc),
            )
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            "request_completed | method=%s path=%s status=%d duration_ms=%.2f request_id=%s client_ip=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
            client_ip,
        )

        # Add request ID to response headers for traceability
        response.headers["X-Request-ID"] = request_id
        return response
