"""
Permission, Role, and Group models for organization-scoped RBAC/ABAC.

This module implements a comprehensive permission system with:
- Organization-scoped roles and permissions
- User roles within organizations
- Direct user permissions
- Groups with roles
- Attribute-based access control via JSON conditions
"""
from datetime import datetime
from typing import Any, Dict
from sqlalchemy import String, ForeignKey, Table, Column, JSON, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
import ulid

from app.core.database.base import Base, TimestampMixin


def generate_ulid() -> str:
    """Generate a new ULID string."""
    return ulid.ulid()


# ============================================================================
# Association Tables for Many-to-Many Relationships
# ============================================================================

# Organization-User-Role relationship (users have roles within specific organizations)
organization_user_roles = Table(
    "organization_user_roles",
    Base.metadata,
    Column("organization_id", String(26), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", String(26), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(26), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("assigned_at", DateTime(timezone=True), nullable=False, default=datetime.now),
    Column("assigned_by_id", String(26), ForeignKey("users.id"), nullable=True),
)

# Role-Permission relationship
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(26), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(26), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

# User direct permissions within an organization (override/supplement role permissions)
organization_user_permissions = Table(
    "organization_user_permissions",
    Base.metadata,
    Column("organization_id", String(26), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", String(26), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(26), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    Column("assigned_at", DateTime(timezone=True), nullable=False, default=datetime.now),
    Column("assigned_by_id", String(26), ForeignKey("users.id"), nullable=True),
)

# User-Group relationship within an organization
organization_user_groups = Table(
    "organization_user_groups",
    Base.metadata,
    Column("organization_id", String(26), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", String(26), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", String(26), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column("joined_at", DateTime(timezone=True), nullable=False, default=datetime.now),
)

# Group-Role relationship
group_roles = Table(
    "group_roles",
    Base.metadata,
    Column("group_id", String(26), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(26), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


# ============================================================================
# Core Models
# ============================================================================

class Permission(Base, TimestampMixin):
    """
    Permission model defining specific actions on resources.
    
    Supports Attribute-Based Access Control (ABAC) through JSON conditions.
    Examples:
    - resource="claims", action="create"
    - resource="reports", action="read", conditions={"time_between": ["09:00", "17:00"]}
    - resource="patients", action="update", conditions={"department": "billing"}
    """
    __tablename__ = "permissions"
    
    # Primary key using ULID
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    
    # Permission definition
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # ABAC conditions stored as JSON
    # Example: {"time_between": ["09:00", "17:00"], "ip_range": ["192.168.1.0/24"]}
    conditions: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    
    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, name={self.name!r}, resource={self.resource}, action={self.action})>"


class Role(Base, TimestampMixin):
    """
    Role model for grouping permissions.
    
    Roles are organization-specific or global (system roles).
    Examples: admin, billing_manager, claims_viewer, auditor
    """
    __tablename__ = "roles"
    
    # Primary key using ULID
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    
    # Role definition
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Optional: Link to specific organization (null = system-wide role)
    organization_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    
    # Relationships
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin"
    )
    
    groups: Mapped[list["Group"]] = relationship(
        "Group",
        secondary=group_roles,
        back_populates="roles",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name!r}, org_id={self.organization_id})>"


class Group(Base, TimestampMixin):
    """
    Group model for organizing users with common roles.
    
    Groups simplify permission management by assigning roles to groups
    instead of individual users. Examples: billing_team, claims_processors, auditors
    """
    __tablename__ = "groups"
    
    # Primary key using ULID
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    
    # Group definition
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Organization-specific group
    organization_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=group_roles,
        back_populates="groups",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<Group(id={self.id}, name={self.name!r}, org_id={self.organization_id})>"


class AuditLog(Base, TimestampMixin):
    """
    Audit log for tracking permission-related actions.
    
    Tracks who did what, when, and from where.
    """
    __tablename__ = "audit_logs"
    
    # Primary key using ULID
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    
    # Actor
    user_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Action details
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    
    # Context
    organization_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    details: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Relationships removed to avoid circular dependencies
    # Access via user_id and organization_id foreign keys when needed
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action={self.action}, resource={self.resource_type})>"
