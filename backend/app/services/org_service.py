import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.role import Membership
from app.models.user import User
from app.schemas.organization import (
    MemberAddRequest,
    MemberOut,
    OrganizationCreate,
    OrganizationOut,
)
from app.services.auth_service import slugify


class OrgService:
    @staticmethod
    async def create_organization(
        db: AsyncSession, user_id: uuid.UUID, data: OrganizationCreate
    ) -> OrganizationOut:
        base_slug = data.slug or slugify(data.name)
        slug = f"{base_slug}-{str(uuid.uuid4())[:6]}"

        org = Organization(name=data.name, slug=slug)
        db.add(org)
        await db.flush()

        # Creator becomes ADMIN
        membership = Membership(
            user_id=user_id,
            organization_id=org.id,
            role=UserRole.ADMIN,
        )
        db.add(membership)
        await db.commit()
        await db.refresh(org)

        return OrganizationOut(
            id=org.id,
            name=org.name,
            slug=org.slug,
            created_at=org.created_at,
            role=UserRole.ADMIN,
        )

    @staticmethod
    async def list_user_organizations(
        db: AsyncSession, user_id: uuid.UUID
    ) -> List[OrganizationOut]:
        result = await db.execute(
            select(Membership)
            .options(selectinload(Membership.organization))
            .where(Membership.user_id == user_id)
        )
        memberships = result.scalars().all()
        return [
            OrganizationOut(
                id=m.organization.id,
                name=m.organization.name,
                slug=m.organization.slug,
                created_at=m.organization.created_at,
                role=m.role,
            )
            for m in memberships
            if m.organization
        ]

    @staticmethod
    async def list_org_members(
        db: AsyncSession, org_id: uuid.UUID
    ) -> List[MemberOut]:
        result = await db.execute(
            select(Membership)
            .options(selectinload(Membership.user))
            .where(Membership.organization_id == org_id)
        )
        memberships = result.scalars().all()
        return [
            MemberOut(
                id=m.id,
                user_id=m.user.id,
                email=m.user.email,
                full_name=m.user.full_name,
                role=m.role,
                created_at=m.created_at,
            )
            for m in memberships
            if m.user
        ]

    @staticmethod
    async def add_member(
        db: AsyncSession, org_id: uuid.UUID, data: MemberAddRequest
    ) -> MemberOut:
        # Find user by email
        result = await db.execute(select(User).where(User.email == data.email.lower()))
        user = result.scalars().first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with email '{data.email}' not found. They must register first.",
            )

        # Check existing membership
        existing = await db.execute(
            select(Membership).where(
                Membership.organization_id == org_id,
                Membership.user_id == user.id,
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this organization",
            )

        membership = Membership(
            organization_id=org_id,
            user_id=user.id,
            role=data.role,
        )
        db.add(membership)
        await db.commit()
        await db.refresh(membership)

        return MemberOut(
            id=membership.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=membership.role,
            created_at=membership.created_at,
        )

    @staticmethod
    async def update_member_role(
        db: AsyncSession, org_id: uuid.UUID, target_user_id: uuid.UUID, new_role: UserRole
    ) -> MemberOut:
        result = await db.execute(
            select(Membership)
            .options(selectinload(Membership.user))
            .where(
                Membership.organization_id == org_id,
                Membership.user_id == target_user_id,
            )
        )
        membership = result.scalars().first()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in organization",
            )

        membership.role = new_role
        await db.commit()
        await db.refresh(membership)

        return MemberOut(
            id=membership.id,
            user_id=membership.user.id,
            email=membership.user.email,
            full_name=membership.user.full_name,
            role=membership.role,
            created_at=membership.created_at,
        )

    @staticmethod
    async def remove_member(
        db: AsyncSession, org_id: uuid.UUID, target_user_id: uuid.UUID
    ) -> None:
        result = await db.execute(
            select(Membership).where(
                Membership.organization_id == org_id,
                Membership.user_id == target_user_id,
            )
        )
        membership = result.scalars().first()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in organization",
            )

        await db.delete(membership)
        await db.commit()
