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
    """
    Create a new Client record from the provided data.
    
    Parameters:
        client_data (ClientCreate): Data used to construct the new client.
    
    Returns:
        Client: The created Client instance with populated fields (e.g., generated IDs).
    
    Raises:
        HTTPException: 400 if a client with the same `external_client_id` already exists.
    """
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
    """
    Retrieve a client by its identifier.
    
    Parameters:
        client_id (str): The ID of the client to retrieve.
    
    Returns:
        Client: The Client instance matching `client_id`.
    
    Raises:
        HTTPException: 404 if no client with `client_id` exists.
    """
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
    """
    Retrieve a paginated list of clients, optionally filtered by organization.
    
    Parameters:
        organization_id (str | None): If provided, only clients belonging to this organization are returned.
        skip (int): Number of records to skip (offset) for pagination.
        limit (int): Maximum number of records to return.
    
    Returns:
        list[Client]: A list of Client instances matching the query and pagination parameters.
    """
    query = select(Client)
    if organization_id:
        query = query.where(Client.organization_id == organization_id)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()