import time
from typing import Awaitable, Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.responses import Response as StarletteResponse

RequestResponseCall = Callable[[Request], Awaitable[Response]]

# Prometheus metrics (exposed on /metrics)
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)

# Endpoints that do NOT require auth (public)
_PUBLIC_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc", "/auth/token"}


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseCall) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start

        path = request.url.path
        REQUEST_COUNT.labels(
            method=request.method,
            path=path,
            status=response.status_code,
        ).inc()
        REQUEST_LATENCY.labels(method=request.method, path=path).observe(duration)

        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Optional JWT auth middleware.
    Enabled only when app.state.auth_enabled is True.
    Skips public endpoints. On failure returns 401/403 JSON.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseCall) -> Response:
        # Skip if auth not enabled at app level
        if not getattr(request.app.state, "auth_enabled", False):
            return await call_next(request)

        path = request.url.path
        if path in _PUBLIC_PATHS or path.startswith("/auth/"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"detail": "Missing or invalid Authorization header"},
                status_code=401,
            )

        token = auth_header[len("Bearer "):]
        try:
            from src.auth.token_auth import token_auth
            payload = token_auth.verify_token(token)
            request.state.token_payload = payload
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=401)

        return await call_next(request)


async def metrics_endpoint(request: Request) -> StarletteResponse:
    """Prometheus /metrics endpoint."""
    return StarletteResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
