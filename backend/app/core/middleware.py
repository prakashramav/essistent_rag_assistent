import logging
import time
import uuid
from typing import Callable
import jwt
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging_config import trace_id_ctx
from app.core.metrics import metrics
from app.core.rate_limiter import rate_limiter

logger = logging.getLogger("enterprise_rag.access")

# Endpoints exempt from rate limits
EXEMPT_PATHS = {
    "/api/v1/health",
    "/api/v1/health/diagnostics",
    "/api/v1/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class ObservabilityAndRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        # 1. Trace ID generation and context propagation
        trace_id = (
            request.headers.get("X-Trace-ID")
            or request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )
        token = trace_id_ctx.set(trace_id)

        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else "unknown"

        # 2. Rate Limiting Check (unless exempt)
        rate_limit_headers = {}
        if path not in EXEMPT_PATHS:
            # Determine rate limit key: tenant org ID, authenticated user, or client IP
            rate_key = None
            org_id = request.headers.get("X-Organization-Id")
            if org_id:
                rate_key = f"org:{org_id}"
            else:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token_str = auth_header[7:].strip()
                    try:
                        payload = jwt.decode(token_str, options={"verify_signature": False})
                        token_org_id = payload.get("org_id")
                        token_user_id = payload.get("sub")
                        if token_org_id:
                            rate_key = f"org:{token_org_id}"
                        elif token_user_id:
                            rate_key = f"user:{token_user_id}"
                    except Exception:
                        pass

            if not rate_key:
                rate_key = f"ip:{client_ip}"

            # Default limit: 600 in dev/test, 60 in prod (overridable via X-Test-Rate-Limit)
            default_limit = 600 if settings.ENVIRONMENT in ("development", "testing") else 60
            limit = int(request.headers.get("X-Test-Rate-Limit", default_limit))
            is_allowed, remaining, reset_secs = await rate_limiter.check_rate_limit(
                identifier=rate_key,
                limit=limit,
                window_seconds=60,
            )

            rate_limit_headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_secs),
            }

            if not is_allowed:
                trace_id_ctx.reset(token)
                logger.warning(
                    f"Rate limit exceeded for {rate_key}",
                    extra={
                        "event": "rate_limit_exceeded",
                        "rate_key": rate_key,
                        "path": path,
                        "method": method,
                    }
                )
                headers = {
                    "X-Trace-ID": trace_id,
                    "X-Request-ID": trace_id,
                    "Retry-After": str(reset_secs),
                    **rate_limit_headers,
                }
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Rate limit exceeded. Try again in {reset_secs} seconds.",
                        "retry_after": reset_secs,
                    },
                    headers=headers,
                )

        # 3. Process Request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"Unhandled exception during {method} {path}: {e}",
                exc_info=True,
                extra={
                    "method": method,
                    "path": path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                }
            )
            trace_id_ctx.reset(token)
            raise e

        duration_sec = time.perf_counter() - start_time
        duration_ms = round(duration_sec * 1000, 2)

        # 4. Attach Observability & Rate Limit Headers
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Request-ID"] = trace_id
        for k, v in rate_limit_headers.items():
            response.headers[k] = v

        # 5. Record Prometheus Metrics
        metrics.inc_counter(
            "http_requests_total",
            method=method,
            endpoint=path,
            status=str(status_code),
        )
        metrics.observe_histogram(
            "http_request_duration_seconds",
            duration_sec,
            method=method,
            endpoint=path,
        )

        # 6. Structured JSON Access Logging
        logger.info(
            f"{method} {path} {status_code} in {duration_ms}ms",
            extra={
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
            }
        )

        trace_id_ctx.reset(token)
        return response
