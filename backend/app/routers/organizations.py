import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.routers.dependencies import (
    AuthContext,
    RequireAdmin,
    RequireViewer,
    get_auth_context,
    get_current_user,
)
from app.schemas.common import MessageResponse
from app.schemas.organization import (
    MemberAddRequest,
    MemberOut,
    MemberRoleUpdateRequest,
    OrganizationCreate,
    OrganizationOut,
)
from app.services.org_service import OrgService

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("", response_model=List[OrganizationOut])
async def list_user_organizations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all organizations that the current user belongs to."""
    return await OrgService.list_user_organizations(db, user.id)


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    data: OrganizationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new organization. The creator is granted Admin role."""
    return await OrgService.create_organization(db, user.id, data)


@router.get("/{org_id}/members", response_model=List[MemberOut])
async def list_org_members(
    org_id: uuid.UUID,
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """List members of an organization. Enforces that context matches requested org_id."""
    if context.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access members of an organization you are not actively scoped to",
        )
    return await OrgService.list_org_members(db, org_id)


@router.post("/{org_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def add_member(
    org_id: uuid.UUID,
    data: MemberAddRequest,
    context: AuthContext = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """Add a registered user to the organization by email. Requires Admin role."""
    if context.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot add members to an organization you are not actively administering",
        )
    return await OrgService.add_member(db, org_id, data)


@router.patch("/{org_id}/members/{target_user_id}", response_model=MemberOut)
async def update_member_role(
    org_id: uuid.UUID,
    target_user_id: uuid.UUID,
    data: MemberRoleUpdateRequest,
    context: AuthContext = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """Update a member's role in the organization. Requires Admin role."""
    if context.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify members in another organization",
        )
    return await OrgService.update_member_role(db, org_id, target_user_id, data.role)


@router.delete("/{org_id}/members/{target_user_id}", response_model=MessageResponse)
async def remove_member(
    org_id: uuid.UUID,
    target_user_id: uuid.UUID,
    context: AuthContext = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from the organization. Requires Admin role."""
    if context.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify members in another organization",
        )
    if context.user.id == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot remove themselves from the organization",
        )
    await OrgService.remove_member(db, org_id, target_user_id)
    return MessageResponse(message="Member removed successfully")
