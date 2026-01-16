"""
Seed script to populate default permissions and roles.

Run this script after database initialization to create:
- Default system permissions
- Default system roles
- Initial role-permission assignments

Usage:
    uv run python -m scripts.seed_permissions
"""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.engine import get_db, init_db
from app.features.permissions.models import Permission, Role
from app.utils import get_logger


log = get_logger(__name__)


DEFAULT_PERMISSIONS = [
    # Claims permissions
    ("claims:create", "claims", "create", "Create new claims"),
    ("claims:read", "claims", "read", "View claims"),
    ("claims:update", "claims", "update", "Update existing claims"),
    ("claims:delete", "claims", "delete", "Delete claims"),
    ("claims:approve", "claims", "approve", "Approve claims"),
    ("claims:submit", "claims", "submit", "Submit claims"),
    ("claims:void", "claims", "void", "Void claims"),
    
    # Reports permissions
    ("reports:read", "reports", "read", "View reports"),
    ("reports:create", "reports", "create", "Create new reports"),
    ("reports:generate", "reports", "generate", "Generate reports"),
    ("reports:export", "reports", "export", "Export reports"),
    
    # User management permissions
    ("users:create", "users", "create", "Create new users"),
    ("users:read", "users", "read", "View user information"),
    ("users:update", "users", "update", "Update user information"),
    ("users:delete", "users", "delete", "Delete users"),
    ("users:manage_roles", "users", "manage_roles", "Manage user roles"),
    
    # Organization permissions
    ("organizations:create", "organizations", "create", "Create organizations"),
    ("organizations:read", "organizations", "read", "View organizations"),
    ("organizations:update", "organizations", "update", "Update organizations"),
    ("organizations:delete", "organizations", "delete", "Delete organizations"),
    
    # Patient permissions
    ("patients:create", "patients", "create", "Create patient records"),
    ("patients:read", "patients", "read", "View patient records"),
    ("patients:update", "patients", "update", "Update patient records"),
    ("patients:delete", "patients", "delete", "Delete patient records"),
    
    # Billing permissions
    ("billing:read", "billing", "read", "View billing information"),
    ("billing:update", "billing", "update", "Update billing information"),
    ("billing:process", "billing", "process", "Process billing transactions"),
    
    # Permission management
    ("permissions:read", "permissions", "read", "View permissions"),
    ("permissions:create", "permissions", "create", "Create permissions"),
    ("permissions:update", "permissions", "update", "Update permissions"),
    ("permissions:delete", "permissions", "delete", "Delete permissions"),
    ("permissions:assign", "permissions", "assign", "Assign permissions to roles/users"),
    
    # Role management
    ("roles:read", "roles", "read", "View roles"),
    ("roles:create", "roles", "create", "Create roles"),
    ("roles:update", "roles", "update", "Update roles"),
    ("roles:delete", "roles", "delete", "Delete roles"),
    
    # Group management
    ("groups:read", "groups", "read", "View groups"),
    ("groups:create", "groups", "create", "Create groups"),
    ("groups:update", "groups", "update", "Update groups"),
    ("groups:delete", "groups", "delete", "Delete groups"),
    
    # Audit logs
    ("audit:read", "audit", "read", "View audit logs"),
]


DEFAULT_ROLES = {
    "system_admin": {
        "description": "System administrator with all permissions",
        "organization_id": None,
        "permissions": "ALL"  # Special case - gets all permissions
    },
    "org_admin": {
        "description": "Organization administrator",
        "organization_id": None,
        "permissions": [
            "users:create", "users:read", "users:update", "users:manage_roles",
            "organizations:read", "organizations:update",
            "groups:create", "groups:read", "groups:update", "groups:delete",
            "roles:read",
            "claims:read", "claims:update", "claims:approve",
            "reports:read", "reports:generate",
            "patients:create", "patients:read", "patients:update",
            "billing:read", "billing:update",
        ]
    },
    "billing_manager": {
        "description": "Billing department manager",
        "organization_id": None,
        "permissions": [
            "claims:create", "claims:read", "claims:update", "claims:approve", "claims:submit",
            "reports:read", "reports:generate", "reports:export",
            "patients:read", "patients:update",
            "billing:read", "billing:update", "billing:process",
        ]
    },
    "claims_processor": {
        "description": "Claims processing specialist",
        "organization_id": None,
        "permissions": [
            "claims:create", "claims:read", "claims:update", "claims:submit",
            "patients:read", "patients:update",
            "billing:read", "billing:update",
        ]
    },
    "rcm_specialist": {
        "description": "Revenue Cycle Management specialist",
        "organization_id": None,
        "permissions": [
            "claims:create", "claims:read", "claims:update", "claims:submit",
            "patients:read", "patients:update",
            "billing:read", "billing:update", "billing:process",
        ]
    },
    "claims_viewer": {
        "description": "Read-only access to claims",
        "organization_id": None,
        "permissions": [
            "claims:read",
            "patients:read",
            "reports:read",
        ]
    },
    "auditor": {
        "description": "Auditor with read-only access to most resources",
        "organization_id": None,
        "permissions": [
            "claims:read",
            "reports:read",
            "patients:read",
            "billing:read",
            "users:read",
            "organizations:read",
            "audit:read",
            "permissions:read",
            "roles:read",
            "groups:read",
        ]
    },
    "patient_coordinator": {
        "description": "Patient services coordinator",
        "organization_id": None,
        "permissions": [
            "patients:create", "patients:read", "patients:update",
            "claims:read",
            "billing:read",
        ]
    },
}


async def seed_permissions(db: AsyncSession) -> dict[str, Permission]:
    """
    Create default permissions.
    
    Returns:
        Dictionary mapping permission names to Permission objects
    """
    log.info("Creating default permissions...")
    permissions_map = {}
    
    for name, resource, action, description in DEFAULT_PERMISSIONS:
        # Check if permission already exists
        stmt = select(Permission).where(Permission.name == name)
        result = await db.execute(stmt)
        existing = result.scalars().first()
        
        if existing:
            log.debug(f"Permission '{name}' already exists, skipping")
            permissions_map[name] = existing
            continue
        
        # Create new permission
        permission = Permission(
            name=name,
            resource=resource,
            action=action,
            description=description
        )
        db.add(permission)
        permissions_map[name] = permission
        log.info(f"Created permission: {name}")
    
    await db.commit()
    
    # Refresh all permissions to get IDs
    for perm in permissions_map.values():
        await db.refresh(perm)
    
    log.info(f"Created {len(permissions_map)} permissions")
    return permissions_map


async def seed_roles(db: AsyncSession, permissions_map: dict[str, Permission]):
    """
    Create default roles and assign permissions.
    
    Args:
        db: Database session
        permissions_map: Dictionary of permission name -> Permission object
    """
    log.info("Creating default roles...")
    
    for role_name, role_config in DEFAULT_ROLES.items():
        # Check if role already exists
        stmt = select(Role).where(Role.name == role_name)
        result = await db.execute(stmt)
        existing = result.scalars().first()
        
        if existing:
            log.debug(f"Role '{role_name}' already exists, skipping")
            continue
        
        # Create role
        role = Role(
            name=role_name,
            description=role_config["description"],
            organization_id=role_config["organization_id"]
        )
        
        # Assign permissions
        if role_config["permissions"] == "ALL":
            # System admin gets all permissions
            role.permissions = list(permissions_map.values())
            log.info(f"Created role '{role_name}' with ALL permissions")
        else:
            # Assign specific permissions
            role_permissions = []
            for perm_name in role_config["permissions"]:
                if perm_name in permissions_map:
                    role_permissions.append(permissions_map[perm_name])
                else:
                    log.warning(f"Permission '{perm_name}' not found for role '{role_name}'")
            
            role.permissions = role_permissions
            log.info(f"Created role '{role_name}' with {len(role_permissions)} permissions")
        
        db.add(role)
    
    await db.commit()
    log.info("Default roles created successfully")


async def main():
    """Main function to seed permissions and roles."""
    log.info("Starting permission seeding...")
    
    # Initialize database tables first
    log.info("Initializing database tables...")
    await init_db()
    
    # Get database session
    async for db in get_db():
        try:
            # Seed permissions first
            permissions_map = await seed_permissions(db)
            
            # Then seed roles with permission assignments
            await seed_roles(db, permissions_map)
            
            log.info("Permission seeding completed successfully!")
            log.info("")
            log.info("Default roles created:")
            for role_name, role_config in DEFAULT_ROLES.items():
                log.info(f"  - {role_name}: {role_config['description']}")
            
        except Exception as e:
            log.error(f"Error seeding permissions: {e}", exc_info=True)
            await db.rollback()
            raise
        
        break  # Only use first session


if __name__ == "__main__":
    asyncio.run(main())
