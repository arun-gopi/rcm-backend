"""
Organization-related dependency injection functions.
"""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.engine import get_db
from app.features.users.models import User
from app.features.users.dependencies import get_current_user
from app.features.organizations.models import Organization


async def get_organization_by_id(
    organization_id: str,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Organization:
    """
    Get organization by ID or raise 404.
    
    Args:
        organization_id: Organization ULID
        db: Database session
        
    Returns:
        Organization model
        
    Raises:
        HTTPException: 404 if organization not found
    """
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    return organization


async def get_user_organization(
    organization_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> Organization:
    """
    Get organization and verify user is a member.
    
    Args:
        organization_id: Organization ULID
        user: Current authenticated user
        db: Database session
        
    Returns:
        Organization model
        
    Raises:
        HTTPException: 404 if org not found or 403 if user not a member
    """
    organization = await get_organization_by_id(organization_id, db)
    
    # Check if user is a member of this organization
    is_member = any(org.id == organization_id for org in user.organizations)
    
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization"
        )
    
    return organization


async def get_current_organization(
    user: Annotated[User, Depends(get_current_user)]
) -> Organization:
    """
    Get user's current active organization.
    
    Args:
        user: Current authenticated user
        
    Returns:
        Current organization
        
    Raises:
        HTTPException: 400 if no current organization is set
    """
    if user.current_organization_id is None or user.current_organization is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No current organization set. Please switch to an organization first."
        )
    
    return user.current_organization
