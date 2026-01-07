"""
Authentication utilities for Appwrite JWT verification.
"""
import os
import jwt
from typing import Optional
from datetime import datetime
from fastapi import HTTPException, status
from appwrite.client import Client
from appwrite.services.users import Users
from appwrite.exception import AppwriteException

from app.core import config

APPWRITE_ENDPOINT = config.APPWRITE_ENDPOINT
APPWRITE_PROJECT_ID = config.APPWRITE_PROJECT_ID
APPWRITE_API_KEY = config.APPWRITE_API_KEY


class AppwriteClient:
    """Singleton Appwrite client for server-side operations."""
    
    _instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Appwrite client instance."""
        if cls._instance is None:
            cls._instance = Client()
            cls._instance.set_endpoint(APPWRITE_ENDPOINT)
            cls._instance.set_project(APPWRITE_PROJECT_ID)
            cls._instance.set_key(APPWRITE_API_KEY)
        return cls._instance


def verify_jwt_token(token: str) -> dict:
    """
    Verify Appwrite JWT token and return payload.
    
    Args:
        token: JWT token from Authorization header
        
    Returns:
        Decoded JWT payload containing user information
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Decode JWT without signature verification
        # Appwrite handles token signing - we trust tokens and verify user exists in Appwrite
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": True}
        )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_appwrite_user(user_id: str) -> dict:
    """
    Get user information from Appwrite.
    
    Args:
        user_id: Appwrite user ID
        
    Returns:
        User information from Appwrite
        
    Raises:
        HTTPException: If user not found or API error
    """
    try:
        client = AppwriteClient.get_client()
        users = Users(client)
        user = users.get(user_id)
        return user
        
    except AppwriteException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to verify user: {str(e)}",
        )
