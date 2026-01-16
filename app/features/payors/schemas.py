"""
Pydantic schemas for Payor API requests/responses.
"""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class PayorBase(BaseModel):
    """Base schema for payor."""
    name: str = Field(..., min_length=1, max_length=255)
    nickname: str | None = None
    company_id: str | None = None
    plan_id: str | None = None


class PayorCreate(PayorBase):
    """Schema for creating a payor."""
    organization_id: str


class PayorResponse(PayorBase):
    """Schema for payor response."""
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
