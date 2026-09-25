import uuid
import pytest
from httpx import AsyncClient
from app.core.rate_limiter import rate_limiter


@pytest.mark.asyncio
async def test_trace_id_generation_and_propagation(client: AsyncClient):
    # 1. Request without trace ID should receive an auto-generated UUID
    res1 = await client.get("/api/v1/health")
    assert res1.status_code == 200
    trace_id_1 = res1.headers.get("X-Trace-ID")
    assert trace_id_1 is not None
    assert len(trace_id_1) == 36  # UUID format
    assert res1.headers.get("X-Request-ID") == trace_id_1

    # 2. Request with explicit incoming X-Trace-ID should be preserved and propagated
    custom_trace = f"client-trace-{uuid.uuid4().hex[:8]}"
    res2 = await client.get(
        "/api/v1/health",
        headers={"X-Trace-ID": custom_trace},
    )
    assert res2.status_code == 200
    assert res2.headers.get("X-Trace-ID") == custom_trace
    assert res2.headers.get("X-Request-ID") == custom_trace


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint(client: AsyncClient):
    # Make a few requests to increment metrics counters
    await client.get("/api/v1/health")
    await client.get("/api/v1/health")

    # Fetch Prometheus metrics
    metrics_res = await client.get("/api/v1/metrics")
    assert metrics_res.status_code == 200
    assert "text/plain" in metrics_res.headers.get("content-type", "")

    body = metrics_res.text
    assert "# HELP http_requests_total" in body
    assert "# TYPE http_requests_total counter" in body
    assert "http_requests_total" in body
    assert "system_uptime_seconds" in body
    assert "# HELP http_request_duration_seconds" in body


@pytest.mark.asyncio
async def test_rate_limiter_enforcement_and_headers(client: AsyncClient):
    rate_limiter.reset_memory()
    test_client_id = f"test-client-{uuid.uuid4().hex[:8]}"
    headers = {
        "X-Organization-Id": test_client_id,
        "X-Test-Rate-Limit": "3",
    }

    # Request 1: Allowed (Remaining = 2)
    r1 = await client.get("/api/v1/documents", headers=headers)
    # Even if 401 Unauthorized (since no auth token), middleware runs and rate limit headers apply!
    assert r1.headers.get("X-RateLimit-Limit") == "3"
    assert r1.headers.get("X-RateLimit-Remaining") == "2"

    # Request 2: Allowed (Remaining = 1)
    r2 = await client.get("/api/v1/documents", headers=headers)
    assert r2.headers.get("X-RateLimit-Remaining") == "1"

    # Request 3: Allowed (Remaining = 0)
    r3 = await client.get("/api/v1/documents", headers=headers)
    assert r3.headers.get("X-RateLimit-Remaining") == "0"

    # Request 4: Blocked by Rate Limiter -> Expect 429
    r4 = await client.get("/api/v1/documents", headers=headers)
    assert r4.status_code == 429
    assert r4.headers.get("X-RateLimit-Remaining") == "0"
    assert "Retry-After" in r4.headers
    data = r4.json()
    assert "Rate limit exceeded" in data["detail"]
    assert data["retry_after"] > 0


@pytest.mark.asyncio
async def test_comprehensive_diagnostics_endpoint(client: AsyncClient):
    diag_res = await client.get("/api/v1/health/diagnostics")
    assert diag_res.status_code == 200
    data = diag_res.json()

    assert data["status"] in ("healthy", "degraded")
    assert "subsystems" in data
    
    subsystems = data["subsystems"]
    assert "database" in subsystems
    assert subsystems["database"]["status"] == "healthy"
    assert subsystems["database"]["pgvector"] is True
    assert subsystems["database"]["latency_ms"] >= 0

    assert "redis_cache" in subsystems
    assert subsystems["redis_cache"]["status"] in ("healthy", "in_memory_fallback", "unhealthy")

    assert "ai_providers" in subsystems
    assert "gemini" in subsystems["ai_providers"]
    assert "openai" in subsystems["ai_providers"]
