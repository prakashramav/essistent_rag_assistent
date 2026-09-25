import time
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limiter import rate_limiter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Basic liveness and readiness probe for load balancers."""
    db_status = "healthy"
    vector_extension = False
    start_db = time.perf_counter()
    try:
        res = await db.execute(text("SELECT 1;"))
        _ = res.scalar()
        db_latency_ms = round((time.perf_counter() - start_db) * 1000, 2)
        
        # Check pgvector extension
        ext_res = await db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector';"))
        vector_extension = ext_res.scalar() is not None
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        db_latency_ms = -1

    return {
        "status": "healthy" if "unhealthy" not in db_status else "degraded",
        "app": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "database_latency_ms": db_latency_ms,
        "pgvector_enabled": vector_extension,
    }


@router.get("/health/diagnostics")
async def comprehensive_diagnostics(db: AsyncSession = Depends(get_db)):
    """Comprehensive multi-subsystem diagnostic status report."""
    # 1. Database Check
    db_info = {"status": "unknown", "latency_ms": -1, "pgvector": False}
    try:
        t0 = time.perf_counter()
        await db.execute(text("SELECT 1;"))
        ext_res = await db.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector';"))
        version = ext_res.scalar()
        db_info = {
            "status": "healthy",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "pgvector": bool(version),
            "pgvector_version": version or "not_installed",
        }
    except Exception as e:
        db_info = {"status": "unhealthy", "error": str(e)}

    # 2. Redis Check
    redis_info = {"status": "unknown", "latency_ms": -1}
    try:
        t0 = time.perf_counter()
        redis_client = await rate_limiter.get_redis()
        if redis_client:
            pong = await redis_client.ping()
            redis_info = {
                "status": "healthy" if pong else "degraded",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                "mode": "redis_cluster_or_standalone",
            }
        else:
            redis_info = {"status": "in_memory_fallback", "latency_ms": 0.0}
    except Exception as e:
        redis_info = {"status": "unhealthy", "error": str(e)}

    # 3. AI Providers Configuration
    ai_providers = {
        "gemini": {
            "configured": bool(settings.GEMINI_API_KEY),
            "default_chat_model": settings.DEFAULT_CHAT_MODEL,
            "default_embedding_model": settings.DEFAULT_EMBEDDING_MODEL,
        },
        "openai": {
            "configured": bool(settings.OPENAI_API_KEY),
        },
    }

    overall_status = "healthy" if db_info.get("status") == "healthy" else "degraded"

    return {
        "status": overall_status,
        "app": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "subsystems": {
            "database": db_info,
            "redis_cache": redis_info,
            "ai_providers": ai_providers,
        },
    }
