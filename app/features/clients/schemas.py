"""
Pydantic schemas for Client and ClientLocation API requests/responses.
"""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ClientLocationBase(BaseModel):
    """Base schema for client location."""
    name: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str = "US"


class ClientLocationCreate(ClientLocationBase):
    """Schema for creating a client location."""
    pass


class ClientLocationResponse(ClientLocationBase):
    """Schema for client location response."""
    id: str
    client_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClientBase(BaseModel):
    """Base schema for client."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    external_client_id: str | None = None
    timezone: str | None = None


class ClientCreate(ClientBase):
    """Schema for creating a client."""
    organization_id: str


class ClientResponse(ClientBase):
    """Schema for client response."""
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    locations: list[ClientLocationResponse] = []

    model_config = ConfigDict(from_attributes=True)
