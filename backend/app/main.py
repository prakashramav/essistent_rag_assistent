from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_engine
from app.core.logging_config import setup_structured_logging
from app.core.middleware import ObservabilityAndRateLimitMiddleware
from app.routers.api import api_router

# Initialize structured JSON logging
setup_structured_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure pgvector extension exists if connected to PostgreSQL
    try:
        async with async_engine.begin() as conn:
            # Check if using PostgreSQL dialect
            if conn.dialect.name == "postgresql":
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    except Exception as e:
        print(f"Database startup warning: {e}")
    yield
    # Shutdown
    await async_engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Multi-Tenant RAG Assistant API with grounded citations and RBAC",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Observability, Tracing, Metrics & Rate Limiting Middleware
app.add_middleware(ObservabilityAndRateLimitMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Trace-ID", "X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "Retry-After"],
)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "status": "online",
        "version": "1.0.0",
        "docs": f"{settings.API_V1_STR}/docs",
        "health": f"{settings.API_V1_STR}/health",
    }


# Include versioned API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred.", "type": type(exc).__name__},
    )
