from time import time
import re
from typing import Callable
from prometheus_client import CollectorRegistry, CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from fastapi import APIRouter, Response

registry = CollectorRegistry()
REQUEST_COUNT = Counter(
    "cb_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status", "adapter_version"],
    registry=registry,
)
REQUEST_LATENCY = Histogram(
    "cb_request_latency_seconds",
    "Request latency (seconds)",
    ["method", "path", "adapter_version"],
    registry=registry,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)
TOKENS_USED = Counter(
    "cb_tokens_total",
    "Total LLM tokens consumed",
    ["model"],
    registry=registry,
)

router = APIRouter()

@router.get("/metrics")
async def metrics() -> Response:
    data = generate_latest(registry)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

class MetricsMiddleware:
    def __init__(self, app: Callable):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        method = scope.get("method", "GET")
        path = scope.get("path", "/")

        start = time()
        status_code_container = {"code": "500"}

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                status_code_container["code"] = str(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time() - start
            norm_path = re.sub(r"/\d+", "/{id}", path)
            # Determine adapter version from scope; default to unknown
            adapter_version = scope.get("adapter_version")
            if not adapter_version:
                # Try to read from headers (x-adapter-version) if present
                headers = dict(scope.get("headers") or [])
                header_val = headers.get(b"x-adapter-version")
                if isinstance(header_val, (bytes, bytearray)):
                    try:
                        adapter_version = header_val.decode()
                    except Exception:
                        adapter_version = "unknown"
                else:
                    adapter_version = "unknown"
            REQUEST_LATENCY.labels(method, norm_path, adapter_version).observe(elapsed)
            REQUEST_COUNT.labels(method, norm_path, status_code_container["code"], adapter_version).inc()