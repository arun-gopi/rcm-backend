"""
Permission checking utilities and dependencies for RBAC/ABAC.

Implements:
- Permission checking with ABAC conditions
- FastAPI dependencies for route protection
- Audit logging helpers
"""
from datetime import datetime, time
from typing import Dict, Any, Optional, List
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database.engine import get_db
from app.features.users.dependencies import get_current_user
from app.features.users.models import User
from app.features.permissions.models import (
    Permission,
    Role,
    Group,
    AuditLog,
    organization_user_roles,
    role_permissions,
    organization_user_permissions,
    organization_user_groups,
    group_roles,
)
from app.utils import get_logger


log = get_logger(__name__)


# ============================================================================
# ABAC Condition Evaluation
# ============================================================================

def evaluate_conditions(
    conditions: Optional[Dict[str, Any]],
    context: Dict[str, Any]
) -> bool:
    """
    Evaluate ABAC conditions against context.
    
    Args:
        conditions: Permission conditions from database
        context: Runtime context (time, IP, user attributes, etc.)
    
    Returns:
        True if conditions are met or no conditions exist
    
    Example conditions:
        {"time_between": ["09:00", "17:00"]}
        {"ip_range": ["192.168.1.0/24"]}
        {"department": "billing"}
        {"day_of_week": ["monday", "tuesday", "wednesday", "thursday", "friday"]}
    """
    if not conditions:
        return True
    
    for condition_key, condition_value in conditions.items():
        if condition_key == "time_between":
            # Check if current time is within range
            current_time = context.get("current_time")
            if not current_time:
                current_time = datetime.now().time()
            
            try:
                start_time = datetime.strptime(condition_value[0], "%H:%M").time()
                end_time = datetime.strptime(condition_value[1], "%H:%M").time()
                
                if not (start_time <= current_time <= end_time):
                    log.debug(f"Time condition failed: {current_time} not between {start_time} and {end_time}")
                    return False
            except (ValueError, IndexError) as e:
                log.warning(f"Invalid time_between condition: {condition_value}, error: {e}")
                return False
        
        elif condition_key == "ip_range":
            # Check if IP is in allowed ranges (simplified - would need ipaddress module for CIDR)
            ip_address = context.get("ip_address")
            if not ip_address or ip_address not in condition_value:
                log.debug(f"IP condition failed: {ip_address} not in {condition_value}")
                return False
        
        elif condition_key == "day_of_week":
            # Check if current day is allowed
            current_day = context.get("day_of_week")
            if not current_day:
                current_day = datetime.now().strftime("%A").lower()
            
            if current_day not in [day.lower() for day in condition_value]:
                log.debug(f"Day of week condition failed: {current_day} not in {condition_value}")
                return False
        
        elif condition_key == "department":
            # Check user department
            user_department = context.get("department")
            if user_department != condition_value:
                log.debug(f"Department condition failed: {user_department} != {condition_value}")
                return False
        
        # Add more condition types as needed
        else:
            # Unknown condition type - log and allow
            log.warning(f"Unknown condition type: {condition_key}")
    
    return True


# ============================================================================
# Permission Checking Functions
# ============================================================================

async def get_user_permissions_in_org(
    db: AsyncSession,
    user_id: str,
    organization_id: str
) -> List[Permission]:
    """
    Get all permissions a user has in an organization.
    
    Includes:
    1. Direct user permissions
    2. Permissions from roles assigned to user
    3. Permissions from groups user belongs to
    
    Returns:
        List of unique Permission objects
    """
    permissions_map: Dict[str, Permission] = {}
    
    # 1. Get direct user permissions
    stmt = (
        select(Permission)
        .join(organization_user_permissions)
        .where(
            and_(
                organization_user_permissions.c.user_id == user_id,
                organization_user_permissions.c.organization_id == organization_id
            )
        )
    )
    result = await db.execute(stmt)
    direct_permissions = result.scalars().all()
    
    for perm in direct_permissions:
        permissions_map[perm.id] = perm
    
    # 2. Get permissions from user's roles in organization
    stmt = (
        select(Permission)
        .join(role_permissions)
        .join(organization_user_roles, organization_user_roles.c.role_id == role_permissions.c.role_id)
        .where(
            and_(
                organization_user_roles.c.user_id == user_id,
                organization_user_roles.c.organization_id == organization_id
            )
        )
    )
    result = await db.execute(stmt)
    role_permissions_list = result.scalars().all()
    
    for perm in role_permissions_list:
        permissions_map[perm.id] = perm
    
    # 3. Get permissions from user's groups in organization
    stmt = (
        select(Permission)
        .join(role_permissions)
        .join(group_roles, group_roles.c.role_id == role_permissions.c.role_id)
        .join(organization_user_groups, organization_user_groups.c.group_id == group_roles.c.group_id)
        .where(
            and_(
                organization_user_groups.c.user_id == user_id,
                organization_user_groups.c.organization_id == organization_id
            )
        )
    )
    result = await db.execute(stmt)
    group_permissions_list = result.scalars().all()
    
    for perm in group_permissions_list:
        permissions_map[perm.id] = perm
    
    return list(permissions_map.values())


async def has_permission(
    db: AsyncSession,
    user: User,
    resource: str,
    action: str,
    organization_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Check if user has permission to perform an action on a resource.
    
    Implements Attribute-Based Access Control (ABAC) by considering:
    - Direct user permissions
    - Role-based permissions
    - Group-based permissions
    - Contextual conditions (time, IP, etc.)
    
    Args:
        db: Database session
        user: User object
        resource: Resource type (e.g., "claims", "reports")
        action: Action (e.g., "read", "create", "update", "delete")
        organization_id: Organization context (uses user's current org if not provided)
        context: Additional context for ABAC evaluation
    
    Returns:
        True if user has permission, False otherwise
    """
    # System admins have all permissions
    if user.is_admin:
        log.debug(f"User {user.id} is admin - granted permission {action} on {resource}")
        return True
    
    # Determine organization context
    if not organization_id:
        organization_id = user.current_organization_id
    
    if not organization_id:
        log.debug(f"No organization context for user {user.id}")
        return False
    
    # Build context for ABAC
    if context is None:
        context = {}
    
    context.setdefault("current_time", datetime.now().time())
    context.setdefault("day_of_week", datetime.now().strftime("%A").lower())
    
    # Get all permissions user has in this organization
    permissions = await get_user_permissions_in_org(db, user.id, organization_id)
    
    # Check if any permission matches and conditions are met
    for permission in permissions:
        if permission.resource == resource and permission.action == action:
            if evaluate_conditions(permission.conditions, context):
                log.debug(
                    f"User {user.id} granted permission {action} on {resource} "
                    f"via permission {permission.id} in org {organization_id}"
                )
                return True
    
    log.debug(f"User {user.id} denied permission {action} on {resource} in org {organization_id}")
    return False


# ============================================================================
# FastAPI Dependencies
# ============================================================================

def require_permission(resource: str, action: str, organization_id: Optional[str] = None):
    """
    FastAPI dependency to require a specific permission.
    
    Usage:
        @router.post("/claims")
        async def create_claim(
            db: AsyncSession = Depends(get_db),
            user: User = Depends(require_permission("claims", "create"))
        ):
            # User has permission to create claims
            pass
    
    Args:
        resource: Resource type
        action: Action
        organization_id: Optional organization ID (uses user's current org if not provided)
    
    Returns:
        Dependency function that returns the current user if they have permission
    
    Raises:
        HTTPException: 403 if user doesn't have permission
    """
    async def permission_dependency(
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ) -> User:
        # Build context for ABAC
        context = {
            "current_time": datetime.now().time(),
            "ip_address": request.client.host if request.client else None,
            "day_of_week": datetime.now().strftime("%A").lower(),
        }
        
        # Determine organization
        org_id = organization_id or current_user.current_organization_id
        
        # Check permission
        if not await has_permission(db, current_user, resource, action, org_id, context):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {action} on {resource}"
            )
        
        return current_user
    
    return permission_dependency


def require_any_permission(permissions: List[tuple[str, str]], organization_id: Optional[str] = None):
    """
    FastAPI dependency to require ANY of the specified permissions.
    
    Usage:
        @router.get("/reports")
        async def get_reports(
            user: User = Depends(require_any_permission([("reports", "read"), ("reports", "admin")]))
        ):
            pass
    
    Args:
        permissions: List of (resource, action) tuples
        organization_id: Optional organization ID
    
    Returns:
        Dependency function that returns the current user if they have any permission
    """
    async def permission_dependency(
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ) -> User:
        context = {
            "current_time": datetime.now().time(),
            "ip_address": request.client.host if request.client else None,
            "day_of_week": datetime.now().strftime("%A").lower(),
        }
        
        org_id = organization_id or current_user.current_organization_id
        
        # Check if user has ANY of the permissions
        for resource, action in permissions:
            if await has_permission(db, current_user, resource, action, org_id, context):
                return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: requires one of {permissions}"
        )
    
    return permission_dependency


# ============================================================================
# Audit Logging
# ============================================================================

async def create_audit_log(
    db: AsyncSession,
    user_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """
    Create an audit log entry.
    
    Args:
        db: Database session
        user_id: User performing the action
        action: Action performed (e.g., "create", "update", "delete", "assign")
        resource_type: Type of resource (e.g., "role", "permission", "user")
        resource_id: ID of the resource
        organization_id: Organization context
        details: Additional details
        ip_address: Client IP address
        user_agent: Client user agent
    
    Returns:
        Created AuditLog object
    """
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        organization_id=organization_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    db.add(audit_log)
    await db.commit()
    await db.refresh(audit_log)
    
    log.info(
        f"Audit: user={user_id} action={action} resource={resource_type}:{resource_id} org={organization_id}"
    )
    
    return audit_log
