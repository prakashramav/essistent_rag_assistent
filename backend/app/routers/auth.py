from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.routers.dependencies import AuthContext, get_auth_context
from app.schemas.auth import LoginRequest, RefreshTokenRequest, SignupRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user and bootstrap their initial organization with Admin role."""
    return await AuthService.register_user(db, request)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email and password and receive JWT access/refresh tokens."""
    return await AuthService.authenticate_user(db, request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token for a new access & refresh token pair."""
    return await AuthService.refresh_tokens(db, request.refresh_token)


@router.get("/me")
async def get_me(
    context: AuthContext = Depends(get_auth_context),
):
    """Retrieve details of the authenticated user in the current organization context."""
    user = context.user
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "active_organization": {
            "id": context.organization.id,
            "name": context.organization.name,
            "slug": context.organization.slug,
            "role": context.role,
        },
        "organizations": [
            {
                "id": m.organization.id,
                "name": m.organization.name,
                "slug": m.organization.slug,
                "role": m.role,
            }
            for m in user.memberships
            if m.organization
        ],
    }
