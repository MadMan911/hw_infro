import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseCall
from starlette.requests import Request
from starlette.responses import Response

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response as StarletteResponse


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


async def metrics_endpoint(request: Request) -> StarletteResponse:
    """Prometheus /metrics endpoint."""
    return StarletteResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
