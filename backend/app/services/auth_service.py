import re
import uuid
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.role import Membership
from app.models.user import User
from app.schemas.auth import LoginRequest, OrgBrief, SignupRequest, TokenResponse, UserOut


def slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug or "org"


class AuthService:
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(
            select(User)
            .options(selectinload(User.memberships).selectinload(Membership.organization))
            .where(User.email == email.lower())
        )
        return result.scalars().first()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        result = await db.execute(
            select(User)
            .options(selectinload(User.memberships).selectinload(Membership.organization))
            .where(User.id == user_id)
        )
        return result.scalars().first()

    @classmethod
    async def register_user(
        cls, db: AsyncSession, request: SignupRequest
    ) -> TokenResponse:
        existing_user = await cls.get_user_by_email(db, request.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists.",
            )

        # 1. Create User
        user = User(
            email=request.email.lower(),
            hashed_password=hash_password(request.password),
            full_name=request.full_name,
            is_active=True,
        )
        db.add(user)
        await db.flush()

        # 2. Create Initial Organization
        org_name = request.organization_name or (
            f"{request.full_name}'s Org" if request.full_name else f"{request.email.split('@')[0]}'s Org"
        )
        base_slug = slugify(org_name)
        slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"

        org = Organization(
            name=org_name,
            slug=slug,
        )
        db.add(org)
        await db.flush()

        # 3. Assign Admin Role in Organization
        membership = Membership(
            user_id=user.id,
            organization_id=org.id,
            role=UserRole.ADMIN,
        )
        db.add(membership)
        await db.commit()

        # Refresh user with memberships
        user_with_orgs = await cls.get_user_by_id(db, user.id)
        return cls.create_token_response(user_with_orgs, org, UserRole.ADMIN)

    @classmethod
    async def authenticate_user(
        cls, db: AsyncSession, request: LoginRequest
    ) -> TokenResponse:
        user = await cls.get_user_by_email(db, request.email)
        if not user or not verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        if not user.memberships:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not belong to any organization",
            )

        # Select target organization
        target_membership = None
        if request.organization_id:
            for m in user.memberships:
                if m.organization_id == request.organization_id:
                    target_membership = m
                    break
            if not target_membership:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User is not a member of the requested organization",
                )
        else:
            # Default to first organization (usually admin or oldest)
            target_membership = user.memberships[0]

        return cls.create_token_response(
            user, target_membership.organization, target_membership.role
        )

    @classmethod
    async def refresh_tokens(
        cls, db: AsyncSession, refresh_token: str
    ) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        user_id_str = payload.get("sub")
        org_id_str = payload.get("org_id")
        if not user_id_str or not org_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token payload",
            )

        user_id = uuid.UUID(user_id_str)
        org_id = uuid.UUID(org_id_str)

        user = await cls.get_user_by_id(db, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        target_membership = next(
            (m for m in user.memberships if m.organization_id == org_id), None
        )
        if not target_membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User no longer belongs to this organization",
            )

        return cls.create_token_response(
            user, target_membership.organization, target_membership.role
        )

    @classmethod
    def create_token_response(
        cls, user: User, org: Organization, role: UserRole
    ) -> TokenResponse:
        token_payload = {
            "sub": str(user.id),
            "email": user.email,
            "org_id": str(org.id),
            "org_slug": org.slug,
            "role": role.value,
        }

        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)

        org_briefs = [
            OrgBrief(
                id=m.organization.id,
                name=m.organization.name,
                slug=m.organization.slug,
                role=m.role,
            )
            for m in (user.memberships or [])
            if m.organization
        ]

        active_org_brief = OrgBrief(
            id=org.id,
            name=org.name,
            slug=org.slug,
            role=role,
        )

        user_out = UserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            organizations=org_briefs,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_out,
            organization=active_org_brief,
        )
