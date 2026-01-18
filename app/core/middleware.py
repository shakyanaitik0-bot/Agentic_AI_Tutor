"""
Middleware for Agentic AI Tutor.

Provides:
- Rate limiting with slowapi
- Prometheus metrics collection
- Request logging
- Security headers
"""

import time
import logging

from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Rate Limiting
# ============================================================================


def get_student_or_ip(request: Request) -> str:
    """
    Get rate limit key from student ID or IP address.

    Uses student_id if authenticated, otherwise falls back to IP.
    """
    # Check for student_id in request state (set by auth middleware)
    if hasattr(request.state, "student_id"):
        return f"student:{request.state.student_id}"

    # Fall back to IP address
    return get_remote_address(request)


# Initialize rate limiter
limiter = Limiter(
    key_func=get_student_or_ip,
    default_limits=[settings.get("rate_limiting.default_limit", "100/minute")],
    storage_uri=settings.get("rate_limiting.storage_uri", "memory://"),
    strategy="fixed-window",
)


def setup_rate_limiting(app: FastAPI):
    """
    Configure rate limiting for the application.

    Args:
        app: FastAPI application instance
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Rate limiting configured")


# Rate limit decorators for different endpoint types
RATE_LIMITS = {
    "auth": settings.get("rate_limiting.auth_limit", "10/minute"),
    "chat": settings.get("rate_limiting.chat_limit", "30/minute"),
    "quiz": settings.get("rate_limiting.quiz_limit", "20/minute"),
    "upload": settings.get("rate_limiting.upload_limit", "5/minute"),
    "default": settings.get("rate_limiting.default_limit", "100/minute"),
}


# ============================================================================
# Prometheus Metrics
# ============================================================================

# Request metrics
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

ACTIVE_REQUESTS = Gauge("http_requests_active", "Number of active HTTP requests")

# Business metrics
QUIZ_GENERATED = Counter("quiz_generated_total", "Total quizzes generated", ["difficulty", "topic"])

QUIZ_SUBMITTED = Counter(
    "quiz_submitted_total",
    "Total quizzes submitted",
    ["result"],  # pass/fail
)

DOCUMENTS_UPLOADED = Counter("documents_uploaded_total", "Total documents uploaded", ["file_type"])

ACTIVE_SESSIONS = Gauge("active_sessions", "Number of active learning sessions")

LLM_CALLS = Counter("llm_calls_total", "Total LLM API calls", ["provider", "model", "status"])

LLM_LATENCY = Histogram(
    "llm_call_duration_seconds",
    "LLM call latency",
    ["provider"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

RAG_SEARCHES = Counter(
    "rag_searches_total",
    "Total RAG searches",
    ["method"],  # dense, sparse, hybrid
)

EMBEDDING_GENERATED = Counter(
    "embeddings_generated_total", "Total embeddings generated", ["provider"]
)


class PrometheusMiddleware:
    """Middleware to collect Prometheus metrics for all requests."""

    def __init__(self, app: FastAPI):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        method = request.method
        path = request.url.path

        # Skip metrics endpoint to avoid recursion
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        # Normalize path for metrics (replace IDs with placeholders)
        endpoint = self._normalize_path(path)

        ACTIVE_REQUESTS.inc()
        start_time = time.time()

        # Track response status
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start_time
            ACTIVE_REQUESTS.dec()

            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status_code).inc()

            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing UUIDs and IDs with placeholders."""
        import re

        # Replace UUIDs
        path = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "{id}", path)
        # Replace numeric IDs
        path = re.sub(r"/\d+", "/{id}", path)
        return path


def setup_metrics(app: FastAPI):
    """
    Configure Prometheus metrics for the application.

    Args:
        app: FastAPI application instance
    """
    # Add metrics middleware
    app.add_middleware(PrometheusMiddleware)

    # Add metrics endpoint
    @app.get("/metrics", tags=["Monitoring"], include_in_schema=False)
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    logger.info("Prometheus metrics configured")


# ============================================================================
# Request Logging Middleware
# ============================================================================


class RequestLoggingMiddleware:
    """Middleware to log all requests with timing information."""

    def __init__(self, app: FastAPI):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        start_time = time.time()

        # Log request
        logger.info(f"Request: {request.method} {request.url.path}")

        # Track response status
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start_time
            logger.info(
                f"Response: {request.method} {request.url.path} "
                f"status={status_code} duration={duration:.3f}s"
            )


def setup_request_logging(app: FastAPI):
    """Configure request logging middleware."""
    if settings.get("logging.log_requests", True):
        app.add_middleware(RequestLoggingMiddleware)
        logger.info("Request logging configured")


# ============================================================================
# Security Headers Middleware
# ============================================================================


class SecurityHeadersMiddleware:
    """Middleware to add security headers to all responses."""

    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }

    def __init__(self, app: FastAPI):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                for key, value in self.SECURITY_HEADERS.items():
                    headers[key.lower().encode()] = value.encode()
                message["headers"] = list(headers.items())
            await send(message)

        await self.app(scope, receive, send_wrapper)


def setup_security_headers(app: FastAPI):
    """Configure security headers middleware."""
    if settings.get("security.add_security_headers", True):
        app.add_middleware(SecurityHeadersMiddleware)
        logger.info("Security headers configured")


# ============================================================================
# Setup All Middleware
# ============================================================================


def setup_middleware(app: FastAPI):
    """
    Configure all middleware for the application.

    Args:
        app: FastAPI application instance
    """
    # Order matters! Add in reverse order of execution
    setup_security_headers(app)
    setup_request_logging(app)
    setup_metrics(app)
    setup_rate_limiting(app)

    logger.info("All middleware configured")


# ============================================================================
# Metric Recording Utilities
# ============================================================================


def record_quiz_generated(difficulty: str, topic: str):
    """Record quiz generation metric."""
    QUIZ_GENERATED.labels(difficulty=difficulty, topic=topic).inc()


def record_quiz_submitted(passed: bool):
    """Record quiz submission metric."""
    QUIZ_SUBMITTED.labels(result="pass" if passed else "fail").inc()


def record_document_uploaded(file_type: str):
    """Record document upload metric."""
    DOCUMENTS_UPLOADED.labels(file_type=file_type).inc()


def record_llm_call(provider: str, model: str, success: bool, duration: float):
    """Record LLM call metric."""
    LLM_CALLS.labels(provider=provider, model=model, status="success" if success else "error").inc()
    LLM_LATENCY.labels(provider=provider).observe(duration)


def record_rag_search(method: str):
    """Record RAG search metric."""
    RAG_SEARCHES.labels(method=method).inc()


def record_embedding_generated(provider: str, count: int = 1):
    """Record embedding generation metric."""
    EMBEDDING_GENERATED.labels(provider=provider).inc(count)


def update_active_sessions(count: int):
    """Update active sessions gauge."""
    ACTIVE_SESSIONS.set(count)
