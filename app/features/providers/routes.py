"""
Provider management API routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.engine import get_db
from app.features.users.dependencies import get_current_user
from app.features.users.models import User
from app.features.providers.models import Provider
from app.features.providers.schemas import ProviderCreate, ProviderResponse

router = APIRouter()


@router.post("", response_model=ProviderResponse, status_code=201)
async def create_provider(
    provider_data: ProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new provider."""
    # Check if external_provider_id already exists
    if provider_data.external_provider_id:
        existing = await db.scalar(
            select(Provider).where(Provider.external_provider_id == provider_data.external_provider_id)
        )
        if existing:
            raise HTTPException(status_code=400, detail="Provider with this external_provider_id already exists")
    
    # Check if NPI already exists
    if provider_data.npi:
        existing = await db.scalar(
            select(Provider).where(Provider.npi == provider_data.npi)
        )
        if existing:
            raise HTTPException(status_code=400, detail="Provider with this NPI already exists")
    
    provider = Provider(**provider_data.model_dump())
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific provider by ID."""
    provider = await db.scalar(
        select(Provider).where(Provider.id == provider_id)
    )
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.get("", response_model=list[ProviderResponse])
async def list_providers(
    organization_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all providers, optionally filtered by organization."""
    query = select(Provider)
    if organization_id:
        query = query.where(Provider.organization_id == organization_id)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()
