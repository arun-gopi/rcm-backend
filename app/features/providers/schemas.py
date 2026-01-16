"""
Pydantic schemas for Provider API requests/responses.
"""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ProviderBase(BaseModel):
    """Base schema for provider."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    external_provider_id: str | None = None
    npi: str | None = Field(None, pattern=r"^\d{10}$", description="10-digit National Provider Identifier")


class ProviderCreate(ProviderBase):
    """Schema for creating a provider."""
    organization_id: str


class ProviderResponse(ProviderBase):
    """Schema for provider response."""
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
