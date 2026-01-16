"""
Client management API routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.engine import get_db
from app.features.users.dependencies import get_current_user
from app.features.users.models import User
from app.features.clients.models import Client, ClientLocation
from app.features.clients.schemas import ClientCreate, ClientResponse

router = APIRouter()


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    client_data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new client."""
    # Check if external_client_id already exists
    if client_data.external_client_id:
        existing = await db.scalar(
            select(Client).where(Client.external_client_id == client_data.external_client_id)
        )
        if existing:
            raise HTTPException(status_code=400, detail="Client with this external_client_id already exists")
    
    client = Client(**client_data.model_dump())
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific client by ID."""
    client = await db.scalar(
        select(Client).where(Client.id == client_id)
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("", response_model=list[ClientResponse])
async def list_clients(
    organization_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all clients, optionally filtered by organization."""
    query = select(Client)
    if organization_id:
        query = query.where(Client.organization_id == organization_id)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()
