import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from app.models.enums import UserRole


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: Optional[str] = Field(None, min_length=2, max_length=100)


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime
    role: Optional[UserRole] = None

    model_config = {"from_attributes": True}


class MemberAddRequest(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.MEMBER


class MemberRoleUpdateRequest(BaseModel):
    role: UserRole


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}
