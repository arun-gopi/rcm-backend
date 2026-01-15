"""
Pydantic schemas for permission management.

Request and response models for permissions, roles, groups, and audit logs.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ============================================================================
# Permission Schemas
# ============================================================================

class PermissionBase(BaseModel):
    """Base permission schema."""
    name: str = Field(..., min_length=1, max_length=100, description="Unique permission name")
    resource: str = Field(..., min_length=1, max_length=100, description="Resource type (e.g., 'claims', 'reports')")
    action: str = Field(..., min_length=1, max_length=50, description="Action (e.g., 'read', 'create', 'update', 'delete')")
    description: Optional[str] = Field(None, max_length=1000, description="Permission description")
    conditions: Optional[Dict[str, Any]] = Field(None, description="ABAC conditions as JSON")


class PermissionCreate(PermissionBase):
    """Schema for creating a new permission."""
    
    @field_validator('name')
    @classmethod
    def name_alphanumeric_underscore(cls, v: str) -> str:
        """Validate permission name format."""
        if not v.replace('_', '').replace('.', '').replace(':', '').isalnum():
            raise ValueError('Permission name must contain only alphanumeric characters, underscores, dots, and colons')
        return v
    
    @field_validator('action')
    @classmethod
    def action_lowercase(cls, v: str) -> str:
        """Ensure action is lowercase."""
        return v.lower()


class PermissionUpdate(BaseModel):
    """Schema for updating a permission."""
    description: Optional[str] = Field(None, max_length=1000)
    conditions: Optional[Dict[str, Any]] = None


class PermissionResponse(PermissionBase):
    """Schema for permission response."""
    id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Role Schemas
# ============================================================================

class RoleBase(BaseModel):
    """Base role schema."""
    name: str = Field(..., min_length=1, max_length=50, description="Unique role name")
    description: Optional[str] = Field(None, max_length=1000, description="Role description")


class RoleCreate(RoleBase):
    """Schema for creating a new role."""
    organization_id: Optional[str] = Field(None, description="Organization ID (null for system-wide role)")
    
    @field_validator('name')
    @classmethod
    def name_alphanumeric_underscore(cls, v: str) -> str:
        """Validate role name format."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Role name must contain only alphanumeric characters, underscores, and hyphens')
        return v


class RoleUpdate(BaseModel):
    """Schema for updating a role."""
    description: Optional[str] = Field(None, max_length=1000)


class RoleResponse(RoleBase):
    """Schema for role response."""
    id: str
    organization_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class RoleWithPermissions(RoleResponse):
    """Schema for role with permissions."""
    permissions: List[PermissionResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Group Schemas
# ============================================================================

class GroupBase(BaseModel):
    """Base group schema."""
    name: str = Field(..., min_length=1, max_length=100, description="Group name")
    description: Optional[str] = Field(None, max_length=1000, description="Group description")


class GroupCreate(GroupBase):
    """Schema for creating a new group."""
    organization_id: str = Field(..., description="Organization ID")


class GroupUpdate(BaseModel):
    """Schema for updating a group."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)


class GroupResponse(GroupBase):
    """Schema for group response."""
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class GroupWithRoles(GroupResponse):
    """Schema for group with roles."""
    roles: List[RoleResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Assignment Schemas
# ============================================================================

class AssignRoleToUser(BaseModel):
    """Schema for assigning a role to a user in an organization."""
    user_id: str = Field(..., description="User ID")
    role_id: str = Field(..., description="Role ID")
    organization_id: str = Field(..., description="Organization ID")


class AssignPermissionToRole(BaseModel):
    """Schema for assigning a permission to a role."""
    permission_id: str = Field(..., description="Permission ID")


class AssignPermissionToUser(BaseModel):
    """Schema for assigning a direct permission to a user in an organization."""
    user_id: str = Field(..., description="User ID")
    permission_id: str = Field(..., description="Permission ID")
    organization_id: str = Field(..., description="Organization ID")


class AssignRoleToGroup(BaseModel):
    """Schema for assigning a role to a group."""
    role_id: str = Field(..., description="Role ID")


class AssignUserToGroup(BaseModel):
    """Schema for adding a user to a group in an organization."""
    user_id: str = Field(..., description="User ID")
    organization_id: str = Field(..., description="Organization ID")


# ============================================================================
# Permission Check Schemas
# ============================================================================

class PermissionCheckRequest(BaseModel):
    """Schema for checking if a user has a permission."""
    resource: str = Field(..., description="Resource type")
    action: str = Field(..., description="Action")
    organization_id: Optional[str] = Field(None, description="Organization ID (uses current if not provided)")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for ABAC")


class PermissionCheckResponse(BaseModel):
    """Schema for permission check response."""
    has_permission: bool
    reason: Optional[str] = None


# ============================================================================
# User Permissions Response
# ============================================================================

class UserPermissionsResponse(BaseModel):
    """Schema for getting all permissions a user has in an organization."""
    user_id: str
    organization_id: str
    roles: List[RoleWithPermissions] = []
    direct_permissions: List[PermissionResponse] = []
    group_permissions: List[RoleWithPermissions] = []  # Permissions from groups
    all_permissions: List[PermissionResponse] = []  # Deduplicated list of all permissions


# ============================================================================
# Audit Log Schemas
# ============================================================================

class AuditLogResponse(BaseModel):
    """Schema for audit log response."""
    id: str
    user_id: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    organization_id: Optional[str]
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    """Schema for paginated audit log list."""
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    pages: int
