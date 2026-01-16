"""
Pydantic schemas for ServiceEntry, ServiceFinancials, ServiceAssignment, and ServiceComment API requests/responses.
"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict


class ServiceFinancialsBase(BaseModel):
    """Base schema for service financials."""
    rate_client: Decimal | None = None
    rate_provider: Decimal | None = None
    drive_minutes: int | None = None
    mileage: Decimal | None = None
    client_charge: Decimal | None = None
    agreed_charge: Decimal | None = None
    copay_amount: Decimal | None = None
    amount_paid: Decimal | None = None
    amount_adjusted: Decimal | None = None
    amount_owed: Decimal | None = None
    invoiced: bool = False
    exported: bool = False


class ServiceFinancialsResponse(ServiceFinancialsBase):
    """Schema for service financials response."""
    service_entry_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceEntryBase(BaseModel):
    """Base schema for service entry."""
    external_id: str = Field(..., description="Unique external identifier")
    organization_id: str
    group_id: str | None = None
    
    client_id: str
    client_location_id: str | None = None
    provider_id: str
    
    date_of_service: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD format")
    time_from: str | None = Field(None, pattern=r"^\d{2}:\d{2}$", description="HH:MM format")
    time_to: str | None = Field(None, pattern=r"^\d{2}:\d{2}$", description="HH:MM format")
    minutes_worked: int | None = None
    units: int | None = None
    
    procedure_code: str = Field(..., max_length=10)
    procedure_description: str | None = None
    
    authorization_id: str | None = None
    
    is_locked: bool = False
    is_void: bool = False
    is_deleted: bool = False
    
    signed_by_provider: bool = False
    signed_by_client: bool = False


class ServiceEntryCreate(ServiceEntryBase):
    """Schema for creating a service entry with optional financials."""
    financials: ServiceFinancialsBase | None = None


class ServiceEntryResponse(ServiceEntryBase):
    """Schema for service entry response."""
    id: str
    created_at: datetime
    updated_at: datetime
    financials: ServiceFinancialsResponse | None = None

    model_config = ConfigDict(from_attributes=True)


# Assignment Schemas

class ServiceAssignmentBase(BaseModel):
    """Base schema for service assignment."""
    assigned_to_user_id: str = Field(..., description="User ID to assign this service entry to")
    followup_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Follow-up date (YYYY-MM-DD)")
    assignment_note: str | None = Field(None, max_length=2000, description="Optional note about the assignment")


class ServiceAssignmentCreate(ServiceAssignmentBase):
    """Schema for creating a new assignment."""
    pass


class ServiceAssignmentResponse(ServiceAssignmentBase):
    """Schema for assignment response."""
    id: str
    service_entry_id: str
    assigned_by_user_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceReassignRequest(BaseModel):
    """Schema for reassigning a service entry to another user."""
    new_assigned_to_user_id: str = Field(..., description="User ID to reassign to")
    followup_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="New follow-up date")
    reason: str = Field(..., min_length=1, max_length=2000, description="Reason for reassignment")


# Comment Schemas

class ServiceCommentBase(BaseModel):
    """Base schema for service comment."""
    comment_text: str = Field(..., min_length=1, max_length=10000, description="Comment content")
    comment_type: str = Field(default="note", max_length=50, description="Type: note, call, email, assignment, etc.")
    is_internal: bool = Field(default=True, description="Whether comment is internal only")


class ServiceCommentCreate(ServiceCommentBase):
    """Schema for creating a new comment."""
    pass


class ServiceCommentResponse(ServiceCommentBase):
    """Schema for comment response."""
    id: str
    service_entry_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Combined response with assignment and comments

class ServiceEntryDetailedResponse(ServiceEntryResponse):
    """Schema for detailed service entry response with assignment and recent comments."""
    current_assignment: ServiceAssignmentResponse | None = None
    recent_comments: list[ServiceCommentResponse] = []

    model_config = ConfigDict(from_attributes=True)
