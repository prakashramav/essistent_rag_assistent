from fastapi import APIRouter
from app.routers import auth, chat, documents, evaluation, health, metrics, organizations, retrieval

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(metrics.router)
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(documents.router)
api_router.include_router(retrieval.router)
api_router.include_router(chat.router)
api_router.include_router(evaluation.router)
