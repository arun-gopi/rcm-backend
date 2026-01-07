"""
Pydantic schemas for user-related requests and responses.
"""
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)


class UserCreate(UserBase):
    """Schema for creating a new user."""
    appwrite_id: str = Field(..., description="Appwrite user ID from authentication")


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    name: str | None = Field(None, min_length=1, max_length=255)
    avatar_url: str | None = Field(None, max_length=500)
    bio: str | None = Field(None, max_length=1000)


class UserResponse(UserBase):
    """Schema for user responses."""
    id: str
    appwrite_id: str
    avatar_url: str | None = None
    bio: str | None = None
    is_active: bool
    is_admin: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class UserPublic(BaseModel):
    """Public user information (limited fields)."""
    id: str
    name: str
    avatar_url: str | None = None
    bio: str | None = None
    
    model_config = {"from_attributes": True}
