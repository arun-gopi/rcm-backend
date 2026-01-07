"""
User feature routes.
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.engine import get_db
from app.features.users.models import User
from app.features.users.schemas import UserResponse, UserPublic, UserUpdate
from app.features.users.dependencies import get_current_user, get_current_admin_user


router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    user: Annotated[User, Depends(get_current_user)]
):
    """Get current authenticated user's profile."""
    return user


@router.patch("/me", response_model=UserResponse)
async def update_current_user_profile(
    update_data: UserUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update current user's profile."""
    # Update only provided fields
    if update_data.name is not None:
        user.name = update_data.name
    if update_data.avatar_url is not None:
        user.avatar_url = update_data.avatar_url
    if update_data.bio is not None:
        user.bio = update_data.bio
    
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserPublic)
async def get_user_by_id(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get public user profile by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.get("/", response_model=list[UserPublic])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 50
):
    """List all active users (public info only)."""
    result = await db.execute(
        select(User)
        .where(User.is_active == True)
        .offset(skip)
        .limit(limit)
    )
    users = result.scalars().all()
    return users


# Admin-only routes
@router.patch("/{user_id}/admin", response_model=UserResponse)
async def toggle_admin_status(
    user_id: str,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Toggle admin status for a user (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-demotion
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own admin status"
        )
    
    user.is_admin = not user.is_admin
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: str,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Deactivate a user account (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deactivation
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    user.is_active = False
    await db.commit()
    
    return {"message": "User deactivated successfully"}
