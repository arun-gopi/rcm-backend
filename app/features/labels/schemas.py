"""
Pydantic schemas for label-related requests and responses.
"""
from datetime import datetime
from pydantic import BaseModel, Field


class LabelBase(BaseModel):
    """Base label schema."""
    name: str = Field(..., min_length=1, max_length=50)
    color: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$", description="Hex color code like #FF5733")
    description: str | None = Field(None, max_length=255)


class LabelCreate(LabelBase):
    """Schema for creating a new label."""
    pass


class LabelUpdate(BaseModel):
    """Schema for updating label information."""
    name: str | None = Field(None, min_length=1, max_length=50)
    color: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    description: str | None = Field(None, max_length=255)


class LabelResponse(LabelBase):
    """Schema for label responses."""
    id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class LabelPublic(BaseModel):
    """Public label information (minimal fields)."""
    id: str
    name: str
    color: str | None = None
    
    model_config = {"from_attributes": True}


class AttachLabelsRequest(BaseModel):
    """Schema for attaching labels to an entity."""
    label_ids: list[str] = Field(..., description="List of label IDs to attach")


class DetachLabelsRequest(BaseModel):
    """Schema for detaching labels from an entity."""
    label_ids: list[str] = Field(..., description="List of label IDs to detach")


class BulkAttachLabelsRequest(BaseModel):
    """Schema for bulk attaching labels to multiple entities."""
    entity_ids: list[str] = Field(..., description="List of entity IDs (users/organizations)")
    label_ids: list[str] = Field(..., description="List of label IDs to attach")


class BulkDetachLabelsRequest(BaseModel):
    """Schema for bulk detaching labels from multiple entities."""
    entity_ids: list[str] = Field(..., description="List of entity IDs (users/organizations)")
    label_ids: list[str] = Field(..., description="List of label IDs to detach")


class BulkOperationResponse(BaseModel):
    """Response for bulk operations."""
    message: str
    successful_count: int
    failed_count: int
    details: list[dict] = Field(default_factory=list)
