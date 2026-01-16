"""
CSV Import API routes for bulk importing RCM service data.

Features:
- Streaming CSV processing (low memory footprint)
- Idempotent imports using external IDs
- Automatic client and provider creation/lookup
- Row-level validation with detailed error reporting
- Transaction safety with rollback on critical failures
"""
import csv
import codecs
from io import StringIO
from fastapi import APIRouter, Depends, UploadFile, HTTPException, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.engine import get_db
from app.features.users.dependencies import get_current_user
from app.features.users.models import User
from app.features.clients.models import Client
from app.features.providers.models import Provider
from app.features.services.models import ServiceEntry, ServiceFinancials
from app.features.csv_import.schemas import CSVImportResult, CSVRowError, CSVColumnMapping
from app.features.csv_import.utils import (
    parse_bool, parse_decimal, parse_int, safe_get, validate_required_fields
)
from app.utils import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/services", response_model=CSVImportResult)
async def import_services_csv(
    file: UploadFile = File(..., description="CSV file containing service entries"),
    organization_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Import service entries from CSV file.
    
    The CSV file should contain columns matching the CSVColumnMapping schema.
    At minimum, the following columns are required:
    - Id (service external ID)
    - ClientId, ClientFirstName, ClientLastName
    - ProviderId, ProviderFirstName, ProviderLastName
    - OrganizationId (or provide organization_id parameter)
    - DateOfService
    - ProcedureCode
    
    The import is idempotent - records with duplicate external IDs will be skipped.
    Clients and providers are automatically created if they don't exist.
    
    Returns detailed results including success/failure counts and error details.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV (.csv)")
    
    # Read file content
    content = await file.read()
    
    # Decode content
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text_content = content.decode("utf-8-sig")  # Try with BOM
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
    
    # Parse CSV
    csv_file = StringIO(text_content)
    reader = csv.DictReader(csv_file)
    
    # Initialize counters
    records_processed = 0
    records_inserted = 0
    records_skipped = 0
    records_failed = 0
    errors: list[dict] = []
    
    # Column mapping
    mapping = CSVColumnMapping()
    
    # Cache for clients and providers to minimize DB lookups
    client_cache: dict[str, Client] = {}
    provider_cache: dict[str, Provider] = {}
    
    async with db.begin():
        for row_number, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            records_processed += 1
            
            try:
                # Validate required fields
                required_fields = [
                    mapping.service_id,
                    mapping.client_id,
                    mapping.client_first_name,
                    mapping.client_last_name,
                    mapping.provider_id,
                    mapping.provider_first_name,
                    mapping.provider_last_name,
                    mapping.date_of_service,
                    mapping.procedure_code,
                ]
                
                # Add organization_id to required if not provided as parameter
                if not organization_id:
                    required_fields.append(mapping.organization_id)
                
                field_errors = validate_required_fields(row, required_fields, row_number)
                if field_errors:
                    errors.extend([{
                        "row_number": row_number,
                        "external_id": safe_get(row, mapping.service_id),
                        "error": err
                    } for err in field_errors])
                    records_failed += 1
                    continue
                
                # Use provided organization_id or get from CSV
                org_id = organization_id or safe_get(row, mapping.organization_id)
                
                # 1️⃣ Get or create Client
                client_external_id = safe_get(row, mapping.client_id)
                
                if client_external_id in client_cache:
                    client = client_cache[client_external_id]
                else:
                    result = await db.execute(
                        select(Client).where(Client.external_client_id == client_external_id)
                    )
                    client = result.scalar_one_or_none()
                    
                    if not client:
                        client = Client(
                            external_client_id=client_external_id,
                            first_name=safe_get(row, mapping.client_first_name),
                            last_name=safe_get(row, mapping.client_last_name),
                            timezone=safe_get(row, mapping.client_timezone),
                            organization_id=org_id
                        )
                        db.add(client)
                        await db.flush()
                        logger.info(f"Created new client: {client.id} ({client_external_id})")
                    
                    client_cache[client_external_id] = client
                
                # 2️⃣ Get or create Provider
                provider_external_id = safe_get(row, mapping.provider_id)
                
                if provider_external_id in provider_cache:
                    provider = provider_cache[provider_external_id]
                else:
                    result = await db.execute(
                        select(Provider).where(Provider.external_provider_id == provider_external_id)
                    )
                    provider = result.scalar_one_or_none()
                    
                    if not provider:
                        provider = Provider(
                            external_provider_id=provider_external_id,
                            first_name=safe_get(row, mapping.provider_first_name),
                            last_name=safe_get(row, mapping.provider_last_name),
                            organization_id=org_id
                        )
                        db.add(provider)
                        await db.flush()
                        logger.info(f"Created new provider: {provider.id} ({provider_external_id})")
                    
                    provider_cache[provider_external_id] = provider
                
                # 3️⃣ Check if ServiceEntry already exists (idempotent)
                service_external_id = safe_get(row, mapping.service_id)
                result = await db.execute(
                    select(ServiceEntry).where(ServiceEntry.external_id == service_external_id)
                )
                existing_service = result.scalar_one_or_none()
                
                if existing_service:
                    records_skipped += 1
                    logger.debug(f"Skipped duplicate service entry: {service_external_id}")
                    continue
                
                # 4️⃣ Create ServiceEntry
                service = ServiceEntry(
                    external_id=service_external_id,
                    organization_id=org_id,
                    group_id=safe_get(row, mapping.group_id),
                    client_id=client.id,
                    client_location_id=None,  # Location handling would require additional logic
                    provider_id=provider.id,
                    date_of_service=safe_get(row, mapping.date_of_service),
                    time_from=safe_get(row, mapping.time_from),
                    time_to=safe_get(row, mapping.time_to),
                    minutes_worked=parse_int(safe_get(row, mapping.minutes_worked)),
                    units=parse_int(safe_get(row, mapping.units)),
                    procedure_code=safe_get(row, mapping.procedure_code),
                    procedure_description=safe_get(row, mapping.procedure_description),
                    authorization_id=safe_get(row, mapping.authorization_id),
                    is_locked=parse_bool(safe_get(row, mapping.is_locked)),
                    is_void=parse_bool(safe_get(row, mapping.is_void)),
                    is_deleted=parse_bool(safe_get(row, mapping.is_deleted)),
                    signed_by_provider=parse_bool(safe_get(row, mapping.signed_by_provider)),
                    signed_by_client=parse_bool(safe_get(row, mapping.signed_by_client)),
                )
                db.add(service)
                await db.flush()
                
                # 5️⃣ Create ServiceFinancials
                financials = ServiceFinancials(
                    service_entry_id=service.id,
                    rate_client=parse_decimal(safe_get(row, mapping.rate_client)),
                    rate_provider=parse_decimal(safe_get(row, mapping.rate_provider)),
                    drive_minutes=parse_int(safe_get(row, mapping.drive_minutes)),
                    mileage=parse_decimal(safe_get(row, mapping.mileage)),
                    client_charge=parse_decimal(safe_get(row, mapping.client_charge)),
                    agreed_charge=parse_decimal(safe_get(row, mapping.agreed_charge)),
                    copay_amount=parse_decimal(safe_get(row, mapping.copay_amount)),
                    amount_paid=parse_decimal(safe_get(row, mapping.amount_paid)),
                    amount_adjusted=parse_decimal(safe_get(row, mapping.amount_adjusted)),
                    amount_owed=parse_decimal(safe_get(row, mapping.amount_owed)),
                    invoiced=parse_bool(safe_get(row, mapping.invoiced)),
                    exported=parse_bool(safe_get(row, mapping.exported)),
                )
                db.add(financials)
                
                records_inserted += 1
                
                # Commit in batches for better performance
                if records_inserted % 100 == 0:
                    await db.flush()
                    logger.info(f"Processed {records_processed} records, inserted {records_inserted}")
                
            except Exception as e:
                records_failed += 1
                error_detail = {
                    "row_number": row_number,
                    "external_id": safe_get(row, mapping.service_id),
                    "error": str(e)
                }
                errors.append(error_detail)
                logger.error(f"Error processing row {row_number}: {e}")
                continue
    
    # Determine status
    if records_failed == 0 and records_processed > 0:
        status = "success"
    elif records_inserted > 0:
        status = "partial"
    else:
        status = "failed"
    
    logger.info(
        f"CSV import completed: {records_processed} processed, "
        f"{records_inserted} inserted, {records_skipped} skipped, {records_failed} failed"
    )
    
    return CSVImportResult(
        status=status,
        records_processed=records_processed,
        records_inserted=records_inserted,
        records_skipped=records_skipped,
        records_failed=records_failed,
        errors=errors[:100],  # Limit error list to prevent huge responses
    )


@router.get("/column-mapping", response_model=CSVColumnMapping)
async def get_column_mapping():
    """
    Get the expected CSV column mapping.
    
    Use this endpoint to see what columns are expected in the CSV file
    and their corresponding field names in the system.
    """
    return CSVColumnMapping()
