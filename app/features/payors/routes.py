"""
Payor management API routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.engine import get_db
from app.features.users.dependencies import get_current_user
from app.features.users.models import User
from app.features.payors.models import Payor
from app.features.payors.schemas import PayorCreate, PayorResponse

router = APIRouter()


@router.post("", response_model=PayorResponse, status_code=201)
async def create_payor(
    payor_data: PayorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new payor record in the database.
    
    Parameters:
        payor_data (PayorCreate): Input data used to construct the new payor.
    
    Returns:
        Payor: The created Payor instance with database-assigned fields populated (e.g., `id`).
    """
    payor = Payor(**payor_data.model_dump())
    db.add(payor)
    await db.commit()
    await db.refresh(payor)
    return payor


@router.get("/{payor_id}", response_model=PayorResponse)
async def get_payor(
    payor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve a payor by its unique identifier.
    
    Parameters:
        payor_id (str): The payor's unique identifier.
    
    Returns:
        payor (Payor): The Payor ORM instance matching the given ID.
    
    Raises:
        HTTPException: 404 if no payor with the given ID exists.
    """
    payor = await db.scalar(
        select(Payor).where(Payor.id == payor_id)
    )
    if not payor:
        raise HTTPException(status_code=404, detail="Payor not found")
    return payor


@router.get("", response_model=list[PayorResponse])
async def list_payors(
    organization_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve a list of payors, optionally filtered by organization.
    
    Parameters:
        organization_id (str | None): If provided, only payors belonging to this organization are returned.
        skip (int): Number of records to skip for pagination.
        limit (int): Maximum number of records to return.
    
    Returns:
        list[Payor]: List of Payor ORM instances matching the query.
    """
    query = select(Payor)
    if organization_id:
        query = query.where(Payor.organization_id == organization_id)
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()