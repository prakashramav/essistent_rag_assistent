import uuid
from typing import Callable, List, Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_token
from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.role import Membership
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


class AuthContext:
    """Holds authenticated user, active organization, and the user's role in that organization."""
    def __init__(
        self,
        user: User,
        organization: Organization,
        role: UserRole,
    ):
        self.user = user
        self.organization = organization
        self.organization_id = organization.id
        self.role = role

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_member_or_above(self) -> bool:
        return self.role in (UserRole.ADMIN, UserRole.MEMBER)


async def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.credentials
    try:
        payload = decode_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type, access token required",
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token: missing subject",
        )

    user_id = uuid.UUID(user_id_str)
    result = await db.execute(
        select(User)
        .options(selectinload(User.memberships).selectinload(Membership.organization))
        .where(User.id == user_id)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


async def get_auth_context(
    user: User = Depends(get_current_user),
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    x_org_id: Optional[str] = Header(None, alias="X-Organization-Id"),
) -> AuthContext:
    """
    Resolves the organization context and enforces tenant membership and role.
    Target org can come from X-Organization-Id header or the token's org_id payload.
    """
    token = auth_header.credentials
    payload = decode_token(token)

    # Determine target org id
    target_org_id = None
    if x_org_id:
        try:
            target_org_id = uuid.UUID(x_org_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Organization-Id header format",
            )
    elif payload.get("org_id"):
        target_org_id = uuid.UUID(payload.get("org_id"))

    if not target_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No organization context specified in token or header",
        )

    # Verify membership and resolve role in target organization
    membership = next(
        (m for m in user.memberships if m.organization_id == target_org_id),
        None,
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized for this organization",
        )

    return AuthContext(
        user=user,
        organization=membership.organization,
        role=membership.role,
    )


def require_role(allowed_roles: List[UserRole]) -> Callable:
    """Dependency factory that enforces RBAC roles within the active organization."""
    async def role_checker(
        context: AuthContext = Depends(get_auth_context),
    ) -> AuthContext:
        if context.role not in allowed_roles:
            role_names = ", ".join(r.value for r in allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires one of [{role_names}] role(s) in this organization.",
            )
        return context

    return role_checker


# Convenient role dependencies
RequireAdmin = require_role([UserRole.ADMIN])
RequireMember = require_role([UserRole.ADMIN, UserRole.MEMBER])
RequireViewer = require_role([UserRole.ADMIN, UserRole.MEMBER, UserRole.VIEWER])
