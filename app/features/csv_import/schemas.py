"""
Pydantic schemas for CSV import validation and responses.
"""
from pydantic import BaseModel, Field


class CSVImportResult(BaseModel):
    """Response schema for CSV import operations."""
    status: str = Field(..., description="Import status: success, partial, or failed")
    records_processed: int = Field(..., description="Total number of records processed")
    records_inserted: int = Field(..., description="Number of records successfully inserted")
    records_skipped: int = Field(..., description="Number of records skipped (duplicates)")
    records_failed: int = Field(..., description="Number of records that failed validation")
    errors: list[dict] = Field(default_factory=list, description="List of errors encountered")


class CSVRowError(BaseModel):
    """Error details for a failed CSV row."""
    row_number: int
    external_id: str | None = None
    error: str
    details: dict | None = None


class CSVColumnMapping(BaseModel):
    """Column mapping configuration for CSV import."""
    # Client fields
    client_id: str = "ClientId"
    client_first_name: str = "ClientFirstName"
    client_last_name: str = "ClientLastName"
    client_timezone: str = "Timezone"
    
    # Provider fields
    provider_id: str = "ProviderId"
    provider_first_name: str = "ProviderFirstName"
    provider_last_name: str = "ProviderLastName"
    
    # Service entry fields
    service_id: str = "Id"
    organization_id: str = "OrganizationId"
    group_id: str = "GroupId"
    date_of_service: str = "DateOfService"
    time_from: str = "TimeWorkedFrom"
    time_to: str = "TimeWorkedTo"
    minutes_worked: str = "TimeWorkedInMins"
    units: str = "UnitsOfService"
    procedure_code: str = "ProcedureCode"
    procedure_description: str = "ProcedureCodeDescription"
    authorization_id: str = "AuthorizationId"
    is_locked: str = "IsLocked"
    is_void: str = "IsVoid"
    is_deleted: str = "IsDeleted"
    signed_by_provider: str = "SignedByProvider"
    signed_by_client: str = "SignedByClient"
    
    # Financial fields
    rate_client: str = "RateClient"
    rate_provider: str = "RateProvider"
    drive_minutes: str = "DriveMinutes"
    mileage: str = "Mileage"
    client_charge: str = "ClientCharges"
    agreed_charge: str = "ClientAgreedCharges"
    copay_amount: str = "CopayAmount"
    amount_paid: str = "AmountPaid"
    amount_adjusted: str = "AmountAdjustment"
    amount_owed: str = "AmountOwed"
    invoiced: str = "Invoiced"
    exported: str = "Exported"
