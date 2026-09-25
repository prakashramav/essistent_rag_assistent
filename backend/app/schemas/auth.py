import uuid
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from app.models.enums import UserRole


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: Optional[str] = None
    organization_name: Optional[str] = Field(None, min_length=2, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    organization_id: Optional[uuid.UUID] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserOut"
    organization: Optional["OrgBrief"] = None


class OrgBrief(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: UserRole

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: Optional[str]
    is_active: bool
    organizations: List[OrgBrief] = []

    model_config = {"from_attributes": True}


TokenResponse.model_rebuild()
