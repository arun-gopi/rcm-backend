"""
FastAPI dependencies for authentication and authorization.
"""
from typing import Annotated
from datetime import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.engine import get_db
from app.features.users.models import User
from app.features.users.auth import verify_jwt_token, get_appwrite_user


security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    This dependency:
    1. Extracts JWT from Authorization header
    2. Verifies JWT with Appwrite
    3. Looks up or creates user in local database
    4. Updates last_login_at timestamp
    
    Usage:
        @router.get("/me")
        async def get_me(user: User = Depends(get_current_user)):
            return user
    """
    token = credentials.credentials
    
    # Verify JWT and get payload
    payload = verify_jwt_token(token)
    appwrite_user_id = payload.get("userId")
    
    if not appwrite_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    # Get user from database
    result = await db.execute(
        select(User).where(User.appwrite_id == appwrite_user_id)
    )
    user = result.scalar_one_or_none()
    
    # If user doesn't exist locally, fetch from Appwrite and create
    if user is None:
        appwrite_user = await get_appwrite_user(appwrite_user_id)
        
        user = User(
            appwrite_id=appwrite_user_id,
            email=appwrite_user.get("email", ""),
            name=appwrite_user.get("name", "Unknown"),
            last_login_at=datetime.utcnow(),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Update last login time
        user.last_login_at = datetime.utcnow()
        await db.commit()
        await db.refresh(user)
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    
    return user


async def get_current_active_user(
    user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Ensure user is active.
    Alias for get_current_user since it already checks is_active.
    """
    return user


async def get_current_admin_user(
    user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Require admin privileges.
    
    Usage:
        @router.delete("/users/{user_id}")
        async def delete_user(
            user_id: str,
            admin: User = Depends(get_current_admin_user)
        ):
            # Only admins can access this endpoint
            ...
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


def get_authorization_header(request) -> str:
    """
    Extract authorization header for rate limiting.
    Used with slowapi Limiter.
    """
    auth = request.headers.get("Authorization", "")
    return auth or "anonymous"
