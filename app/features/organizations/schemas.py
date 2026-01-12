"""
Pydantic schemas for organization-related requests and responses.
"""
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr

from app.features.organizations.models import AccessRequestStatus
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.features.labels.schemas import LabelPublic


# Address Schemas
class AddressBase(BaseModel):
    """Base address schema."""
    address_line1: str = Field(..., min_length=1, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=50)
    postal_code: str = Field(..., min_length=1, max_length=20)
    country: str = Field(default="USA", max_length=50)
    address_type: str = Field(default="main", max_length=50, description="Type of address: main, billing, shipping, etc.")
    is_default: bool = Field(default=False, description="Mark as default address")


class AddressCreate(AddressBase):
    """Schema for creating a new address."""
    pass


class AddressUpdate(BaseModel):
    """Schema for updating address information."""
    address_line1: str | None = Field(None, min_length=1, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, min_length=1, max_length=100)
    state: str | None = Field(None, min_length=1, max_length=50)
    postal_code: str | None = Field(None, min_length=1, max_length=20)
    country: str | None = Field(None, max_length=50)
    address_type: str | None = Field(None, max_length=50)
    is_default: bool | None = None


class AddressResponse(AddressBase):
    """Schema for address responses."""
    id: str
    organization_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    labels: list["LabelPublic"] = Field(default_factory=list, description="Address labels")
    
    model_config = {"from_attributes": True}


# Organization Schemas
class OrganizationBase(BaseModel):
    """Base organization schema."""
    name: str = Field(..., min_length=1, max_length=255)
    npi: str = Field(..., min_length=10, max_length=10, pattern="^[0-9]{10}$", description="10-digit National Provider Identifier")
    tin: str = Field(..., min_length=9, max_length=20, description="Tax Identification Number (TIN/EIN)")
    phone: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    website: str | None = Field(None, max_length=255)


class OrganizationCreate(OrganizationBase):
    """Schema for creating a new organization (admin only)."""
    initial_address: AddressCreate | None = Field(None, description="Optional initial address for the organization")


class OrganizationUpdate(BaseModel):
    """Schema for updating organization information."""
    name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    website: str | None = Field(None, max_length=255)


class OrganizationResponse(OrganizationBase):
    """Schema for organization responses."""
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    member_count: int | None = Field(None, description="Number of users in this organization")
    addresses: list[AddressResponse] = Field(default_factory=list, description="Organization addresses")
    labels: list["LabelPublic"] = Field(default_factory=list, description="Organization labels")
    
    model_config = {"from_attributes": True}


class OrganizationPublic(BaseModel):
    """Public organization information (limited fields)."""
    id: str
    name: str
    npi: str
    
    model_config = {"from_attributes": True}


# Access Request Schemas
class AccessRequestCreate(BaseModel):
    """Schema for creating an access request."""
    tin: str = Field(..., min_length=9, max_length=20, description="TIN/EIN of the organization to request access to")
    message: str | None = Field(None, max_length=1000, description="Optional message to organization admins")


class AccessRequestResponse(BaseModel):
    """Schema for access request responses."""
    id: str
    user_id: str
    organization_id: str
    organization_name: str
    organization_npi: str
    status: AccessRequestStatus
    message: str | None = None
    reviewed_by_id: str | None = None
    reviewed_at: datetime | None = None
    review_message: str | None = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class AccessRequestReview(BaseModel):
    """Schema for reviewing an access request (admin only)."""
    approved: bool = Field(..., description="True to approve, False to reject")
    review_message: str | None = Field(None, max_length=1000, description="Optional message to the requester")


# User-Organization Relationship Schemas
class UserOrganizationRole(BaseModel):
    """Schema for user's role in an organization."""
    organization_id: str
    organization_name: str
    role: str  # member, admin, owner
    joined_at: datetime
    
    model_config = {"from_attributes": True}


class SwitchOrganizationRequest(BaseModel):
    """Schema for switching current organization."""
    organization_id: str = Field(..., description="ID of the organization to switch to")


class AddUserToOrganization(BaseModel):
    """Schema for admin to add a user to an organization."""
    user_id: str = Field(..., description="ID of the user to add")
    role: str = Field(default="member", pattern="^(member|admin|owner)$", description="Role in the organization")


# Import at the end to avoid circular dependency issues
from app.features.labels.schemas import LabelPublic  # noqa: E402
OrganizationResponse.model_rebuild()
AddressResponse.model_rebuild()
