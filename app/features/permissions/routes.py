"""
Permission management API routes.

Provides endpoints for managing permissions, roles, groups, and their assignments.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy import select, delete, and_, or_, insert, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.database.engine import get_db
from app.features.users.dependencies import get_current_user, get_current_admin_user
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
from app.features.permissions.schemas import (
    PermissionCreate,
    PermissionUpdate,
    PermissionResponse,
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleWithPermissions,
    GroupCreate,
    GroupUpdate,
    GroupResponse,
    GroupWithRoles,
    AssignRoleToUser,
    AssignPermissionToRole,
    AssignPermissionToUser,
    AssignRoleToGroup,
    AssignUserToGroup,
    PermissionCheckRequest,
    PermissionCheckResponse,
    UserPermissionsResponse,
    AuditLogResponse,
    AuditLogListResponse,
)
from app.features.permissions.dependencies import (
    has_permission,
    require_permission,
    create_audit_log,
    get_user_permissions_in_org,
)
from app.utils import get_logger


log = get_logger(__name__)
router = APIRouter()


# ============================================================================
# Permission Routes
# ============================================================================

@router.post("/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def create_permission(
    permission: PermissionCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)  # Only admins can create permissions
):
    """Create a new permission (admin only)."""
    try:
        db_permission = Permission(**permission.model_dump())
        db.add(db_permission)
        await db.commit()
        await db.refresh(db_permission)
        
        # Log creation in background
        background_tasks.add_task(
            create_audit_log,
            db=db,
            user_id=current_user.id,
            action="create",
            resource_type="permission",
            resource_id=db_permission.id,
            details=permission.model_dump(),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        return db_permission
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Permission with this name already exists"
        )


@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    skip: int = 0,
    limit: int = 100,
    resource: Optional[str] = None,
    action: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all permissions with optional filtering."""
    stmt = select(Permission)
    
    if resource:
        stmt = stmt.where(Permission.resource == resource)
    if action:
        stmt = stmt.where(Permission.action == action)
    
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/permissions/{permission_id}", response_model=PermissionResponse)
async def get_permission(
    permission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific permission by ID."""
    stmt = select(Permission).where(Permission.id == permission_id)
    result = await db.execute(stmt)
    permission = result.scalars().first()
    
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    return permission


@router.put("/permissions/{permission_id}", response_model=PermissionResponse)
async def update_permission(
    permission_id: str,
    permission_update: PermissionUpdate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update a permission (admin only)."""
    stmt = select(Permission).where(Permission.id == permission_id)
    result = await db.execute(stmt)
    db_permission = result.scalars().first()
    
    if not db_permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    update_data = permission_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_permission, key, value)
    
    await db.commit()
    await db.refresh(db_permission)
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="update",
        resource_type="permission",
        resource_id=permission_id,
        details=update_data,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return db_permission


@router.delete("/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(
    permission_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete a permission (admin only)."""
    stmt = select(Permission).where(Permission.id == permission_id)
    result = await db.execute(stmt)
    db_permission = result.scalars().first()
    
    if not db_permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    permission_name = db_permission.name
    await db.delete(db_permission)
    await db.commit()
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="delete",
        resource_type="permission",
        resource_id=permission_id,
        details={"name": permission_name},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return None


# ============================================================================
# Role Routes
# ============================================================================

@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role: RoleCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new role."""
    # If organization_id is provided, verify user has access
    if role.organization_id:
        if not current_user.is_admin:
            # Check if user is in the organization
            from app.features.organizations.models import user_organizations
            stmt = select(user_organizations).where(
                and_(
                    user_organizations.c.user_id == current_user.id,
                    user_organizations.c.organization_id == role.organization_id
                )
            )
            result = await db.execute(stmt)
            if not result.first():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to create roles in this organization"
                )
    
    try:
        db_role = Role(**role.model_dump())
        db.add(db_role)
        await db.commit()
        await db.refresh(db_role)
        
        background_tasks.add_task(
            create_audit_log,
            db=db,
            user_id=current_user.id,
            action="create",
            resource_type="role",
            resource_id=db_role.id,
            organization_id=role.organization_id,
            details=role.model_dump(),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        return db_role
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role with this name already exists"
        )


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    skip: int = 0,
    limit: int = 100,
    organization_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List roles with optional organization filtering."""
    stmt = select(Role)
    
    # Filter by organization if specified
    if organization_id:
        stmt = stmt.where(
            or_(
                Role.organization_id == organization_id,
                Role.organization_id.is_(None)  # Include system-wide roles
            )
        )
    elif current_user.current_organization_id and not current_user.is_admin:
        # Non-admins see only their current organization's roles + system roles
        stmt = stmt.where(
            or_(
                Role.organization_id == current_user.current_organization_id,
                Role.organization_id.is_(None)
            )
        )
    
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/roles/{role_id}", response_model=RoleWithPermissions)
async def get_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific role with its permissions."""
    stmt = select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
    result = await db.execute(stmt)
    role = result.scalars().first()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    return role


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    role_update: RoleUpdate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a role."""
    stmt = select(Role).where(Role.id == role_id)
    result = await db.execute(stmt)
    db_role = result.scalars().first()
    
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    update_data = role_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_role, key, value)
    
    await db.commit()
    await db.refresh(db_role)
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="update",
        resource_type="role",
        resource_id=role_id,
        organization_id=db_role.organization_id,
        details=update_data,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return db_role


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a role."""
    stmt = select(Role).where(Role.id == role_id)
    result = await db.execute(stmt)
    db_role = result.scalars().first()
    
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    role_name = db_role.name
    org_id = db_role.organization_id
    
    await db.delete(db_role)
    await db.commit()
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="delete",
        resource_type="role",
        resource_id=role_id,
        organization_id=org_id,
        details={"name": role_name},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return None


@router.post("/roles/{role_id}/permissions", status_code=status.HTTP_200_OK)
async def assign_permission_to_role(
    role_id: str,
    assignment: AssignPermissionToRole,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Assign a permission to a role."""
    # Check if role exists
    role_stmt = select(Role).where(Role.id == role_id)
    role_result = await db.execute(role_stmt)
    role = role_result.scalars().first()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check if permission exists
    perm_stmt = select(Permission).where(Permission.id == assignment.permission_id)
    perm_result = await db.execute(perm_stmt)
    permission = perm_result.scalars().first()
    
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    # Check if already assigned
    check_stmt = select(role_permissions).where(
        and_(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == assignment.permission_id
        )
    )
    check_result = await db.execute(check_stmt)
    if check_result.first():
        return {"message": f"Permission '{permission.name}' already assigned to role '{role.name}'"}
    
    # Assign permission
    stmt = insert(role_permissions).values(role_id=role_id, permission_id=assignment.permission_id)
    await db.execute(stmt)
    await db.commit()
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="assign_permission",
        resource_type="role",
        resource_id=role_id,
        organization_id=role.organization_id,
        details={"permission_id": assignment.permission_id, "permission_name": permission.name},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return {"message": f"Permission '{permission.name}' assigned to role '{role.name}'"}


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_permission_from_role(
    role_id: str,
    permission_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a permission from a role."""
    # Check if assignment exists first
    check_stmt = select(role_permissions).where(
        and_(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == permission_id
        )
    )
    check_result = await db.execute(check_stmt)
    if not check_result.first():
        raise HTTPException(status_code=404, detail="Permission assignment not found")
    
    # Delete the assignment
    stmt = delete(role_permissions).where(
        and_(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == permission_id
        )
    )
    await db.execute(stmt)
    await db.commit()
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="remove_permission",
        resource_type="role",
        resource_id=role_id,
        details={"permission_id": permission_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return None


# ============================================================================
# Group Routes
# ============================================================================

@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    group: GroupCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new group in an organization."""
    # Verify user has access to organization
    if not current_user.is_admin:
        from app.features.organizations.models import user_organizations
        stmt = select(user_organizations).where(
            and_(
                user_organizations.c.user_id == current_user.id,
                user_organizations.c.organization_id == group.organization_id
            )
        )
        result = await db.execute(stmt)
        if not result.first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to create groups in this organization"
            )
    
    db_group = Group(**group.model_dump())
    db.add(db_group)
    await db.commit()
    await db.refresh(db_group)
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="create",
        resource_type="group",
        resource_id=db_group.id,
        organization_id=group.organization_id,
        details=group.model_dump(),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return db_group


@router.get("/groups", response_model=List[GroupResponse])
async def list_groups(
    skip: int = 0,
    limit: int = 100,
    organization_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List groups, optionally filtered by organization."""
    stmt = select(Group)
    
    if organization_id:
        stmt = stmt.where(Group.organization_id == organization_id)
    elif current_user.current_organization_id and not current_user.is_admin:
        stmt = stmt.where(Group.organization_id == current_user.current_organization_id)
    
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/groups/{group_id}", response_model=GroupWithRoles)
async def get_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific group with its roles."""
    stmt = select(Group).where(Group.id == group_id).options(selectinload(Group.roles))
    result = await db.execute(stmt)
    group = result.scalars().first()
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    return group


@router.put("/groups/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: str,
    group_update: GroupUpdate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a group."""
    stmt = select(Group).where(Group.id == group_id)
    result = await db.execute(stmt)
    db_group = result.scalars().first()
    
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    update_data = group_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_group, key, value)
    
    await db.commit()
    await db.refresh(db_group)
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="update",
        resource_type="group",
        resource_id=group_id,
        organization_id=db_group.organization_id,
        details=update_data,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return db_group


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a group."""
    stmt = select(Group).where(Group.id == group_id)
    result = await db.execute(stmt)
    db_group = result.scalars().first()
    
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group_name = db_group.name
    org_id = db_group.organization_id
    
    await db.delete(db_group)
    await db.commit()
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="delete",
        resource_type="group",
        resource_id=group_id,
        organization_id=org_id,
        details={"name": group_name},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return None


# ============================================================================
# Assignment Routes
# ============================================================================

@router.post("/assignments/user-role", status_code=status.HTTP_200_OK)
async def assign_role_to_user(
    assignment: AssignRoleToUser,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Assign a role to a user in an organization."""
    # Check if already assigned
    check_stmt = select(organization_user_roles).where(
        and_(
            organization_user_roles.c.organization_id == assignment.organization_id,
            organization_user_roles.c.user_id == assignment.user_id,
            organization_user_roles.c.role_id == assignment.role_id
        )
    )
    check_result = await db.execute(check_stmt)
    if check_result.first():
        return {"message": "Role already assigned to user in this organization"}
    
    # Assign role
    stmt = insert(organization_user_roles).values(
        organization_id=assignment.organization_id,
        user_id=assignment.user_id,
        role_id=assignment.role_id,
        assigned_by_id=current_user.id
    )
    await db.execute(stmt)
    await db.commit()
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="assign_role",
        resource_type="user",
        resource_id=assignment.user_id,
        organization_id=assignment.organization_id,
        details={"role_id": assignment.role_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return {"message": "Role assigned to user successfully"}


@router.post("/assignments/user-permission", status_code=status.HTTP_200_OK)
async def assign_permission_to_user(
    assignment: AssignPermissionToUser,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Assign a direct permission to a user in an organization."""
    # Check if already assigned
    check_stmt = select(organization_user_permissions).where(
        and_(
            organization_user_permissions.c.organization_id == assignment.organization_id,
            organization_user_permissions.c.user_id == assignment.user_id,
            organization_user_permissions.c.permission_id == assignment.permission_id
        )
    )
    check_result = await db.execute(check_stmt)
    if check_result.first():
        return {"message": "Permission already assigned to user in this organization"}
    
    # Assign permission
    stmt = insert(organization_user_permissions).values(
        organization_id=assignment.organization_id,
        user_id=assignment.user_id,
        permission_id=assignment.permission_id,
        assigned_by_id=current_user.id
    )
    await db.execute(stmt)
    await db.commit()
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="assign_permission",
        resource_type="user",
        resource_id=assignment.user_id,
        organization_id=assignment.organization_id,
        details={"permission_id": assignment.permission_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return {"message": "Permission assigned to user successfully"}


@router.post("/groups/{group_id}/users", status_code=status.HTTP_200_OK)
async def add_user_to_group(
    group_id: str,
    assignment: AssignUserToGroup,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a user to a group in an organization."""
    # Check if already in group
    check_stmt = select(organization_user_groups).where(
        and_(
            organization_user_groups.c.organization_id == assignment.organization_id,
            organization_user_groups.c.user_id == assignment.user_id,
            organization_user_groups.c.group_id == group_id
        )
    )
    check_result = await db.execute(check_stmt)
    if check_result.first():
        return {"message": "User already in group"}
    
    # Add to group
    stmt = insert(organization_user_groups).values(
        organization_id=assignment.organization_id,
        user_id=assignment.user_id,
        group_id=group_id
    )
    await db.execute(stmt)
    await db.commit()
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="add_to_group",
        resource_type="user",
        resource_id=assignment.user_id,
        organization_id=assignment.organization_id,
        details={"group_id": group_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return {"message": "User added to group successfully"}


@router.post("/groups/{group_id}/roles", status_code=status.HTTP_200_OK)
async def assign_role_to_group(
    group_id: str,
    assignment: AssignRoleToGroup,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Assign a role to a group."""
    # Check if already assigned
    check_stmt = select(group_roles).where(
        and_(
            group_roles.c.group_id == group_id,
            group_roles.c.role_id == assignment.role_id
        )
    )
    check_result = await db.execute(check_stmt)
    if check_result.first():
        return {"message": "Role already assigned to group"}
    
    # Assign role
    stmt = insert(group_roles).values(group_id=group_id, role_id=assignment.role_id)
    await db.execute(stmt)
    await db.commit()
    
    # Get group info for audit
    group_stmt = select(Group).where(Group.id == group_id)
    group_result = await db.execute(group_stmt)
    group = group_result.scalars().first()
    
    background_tasks.add_task(
        create_audit_log,
        db=db,
        user_id=current_user.id,
        action="assign_role",
        resource_type="group",
        resource_id=group_id,
        organization_id=group.organization_id if group else None,
        details={"role_id": assignment.role_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    return {"message": "Role assigned to group successfully"}


# ============================================================================
# Permission Check Routes
# ============================================================================

@router.post("/check", response_model=PermissionCheckResponse)
async def check_permission(
    check_request: PermissionCheckRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check if the current user has a specific permission."""
    context = check_request.context or {}
    context.setdefault("ip_address", request.client.host if request.client else None)
    
    org_id = check_request.organization_id or current_user.current_organization_id
    
    has_perm = await has_permission(
        db=db,
        user=current_user,
        resource=check_request.resource,
        action=check_request.action,
        organization_id=org_id,
        context=context
    )
    
    return PermissionCheckResponse(
        has_permission=has_perm,
        reason=None if has_perm else "Permission denied"
    )


@router.get("/users/{user_id}/permissions", response_model=UserPermissionsResponse)
async def get_user_permissions(
    user_id: str,
    organization_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all permissions for a user in an organization."""
    # Can only view own permissions unless admin
    if user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view other users' permissions"
        )
    
    org_id = organization_id or current_user.current_organization_id
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization ID required"
        )
    
    # Get all permissions
    all_perms = await get_user_permissions_in_org(db, user_id, org_id)
    
    # TODO: Break down by source (roles, direct, groups) for detailed response
    # For now, return simplified version
    
    return UserPermissionsResponse(
        user_id=user_id,
        organization_id=org_id,
        roles=[],
        direct_permissions=[],
        group_permissions=[],
        all_permissions=[PermissionResponse.model_validate(p) for p in all_perms]
    )


# ============================================================================
# Audit Log Routes
# ============================================================================

@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    skip: int = 0,
    limit: int = 50,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)  # Admin only
):
    """List audit logs with optional filtering."""
    stmt = select(AuditLog)
    
    if organization_id:
        stmt = stmt.where(AuditLog.organization_id == organization_id)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    
    # Get total count
    count_stmt = select(func.count()).select_from(stmt.alias())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    
    # Get paginated results
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    
    pages = (total + limit - 1) // limit if limit > 0 else 0
    page = (skip // limit) + 1 if limit > 0 else 1
    
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=limit,
        pages=pages
    )
