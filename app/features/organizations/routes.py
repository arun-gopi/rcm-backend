"""
Organization feature routes.
"""
from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.engine import get_db
from app.features.users.models import User
from app.features.users.dependencies import get_current_user, get_current_admin_user
from app.features.organizations.models import (
    Organization,
    OrganizationAddress,
    OrganizationAccessRequest,
    AccessRequestStatus,
    user_organizations
)
from app.features.labels.models import organization_labels, address_labels
from app.features.organizations.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationPublic,
    AddressCreate,
    AddressUpdate,
    AddressResponse,
    AccessRequestCreate,
    AccessRequestResponse,
    AccessRequestReview,
    SwitchOrganizationRequest,
    AddUserToOrganization
)
from app.features.organizations.dependencies import (
    get_organization_by_id,
    get_user_organization,
    get_current_organization
)


router = APIRouter(tags=["organizations"])


# Organization CRUD endpoints
@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_data: OrganizationCreate,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new organization (admin only)."""
    # Check if NPI or TIN already exists
    result = await db.execute(
        select(Organization).where(
            (Organization.npi == org_data.npi) | (Organization.tin == org_data.tin)
        )
    )
    existing_org = result.scalar_one_or_none()
    
    if existing_org:
        if existing_org.npi == org_data.npi:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization with this NPI already exists"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization with this TIN/EIN already exists"
            )
    
    # Create organization
    org_dict = org_data.model_dump(exclude={"initial_address"})
    new_org = Organization(**org_dict)
    db.add(new_org)
    await db.commit()
    await db.refresh(new_org)
    
    # Add initial address if provided
    if org_data.initial_address:
        initial_address = OrganizationAddress(
            organization_id=new_org.id,
            **org_data.initial_address.model_dump(),
            is_default=True  # First address is always default
        )
        db.add(initial_address)
    
    # Add admin as owner
    stmt = user_organizations.insert().values(
        user_id=admin.id,
        organization_id=new_org.id,
        role="owner",
        joined_at=datetime.now()
    )
    await db.execute(stmt)
    await db.commit()
    
    # Refresh to get updated relationships
    await db.refresh(new_org)
    
    response = OrganizationResponse.model_validate(new_org)
    response.member_count = len(new_org.users)
    return response


@router.get("/", response_model=list[OrganizationPublic])
async def list_organizations(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 50,
    labels: list[str] = Query(default=[], description="Filter by label IDs")
):
    """List all active organizations (public info only). Can filter by labels."""
    query = select(Organization).where(Organization.is_active == True)
    
    # Filter by labels if provided
    if labels:
        query = query.join(organization_labels).where(organization_labels.c.label_id.in_(labels))
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    organizations = result.scalars().all()
    return organizations


@router.get("/my", response_model=list[OrganizationResponse])
async def get_my_organizations(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get all organizations the current user is a member of."""
    # Refresh user to ensure organizations are loaded
    await db.refresh(user)
    
    organizations = []
    for org in user.organizations:
        org_response = OrganizationResponse.model_validate(org)
        org_response.member_count = len(org.users)
        organizations.append(org_response)
    
    return organizations


@router.get("/current", response_model=OrganizationResponse)
async def get_current_organization_endpoint(
    organization: Annotated[Organization, Depends(get_current_organization)]
):
    """Get user's current active organization."""
    response = OrganizationResponse.model_validate(organization)
    response.member_count = len(organization.users)
    return response


@router.post("/switch", response_model=dict)
async def switch_organization(
    switch_data: SwitchOrganizationRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Switch to a different organization."""
    # Verify user is a member of the target organization
    is_member = any(org.id == switch_data.organization_id for org in user.organizations)
    
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization"
        )
    
    # Update current organization
    user.current_organization_id = switch_data.organization_id
    await db.commit()
    await db.refresh(user)
    
    return {
        "message": "Organization switched successfully",
        "current_organization_id": user.current_organization_id,
        "current_organization_name": user.current_organization.name if user.current_organization else None
    }


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization: Annotated[Organization, Depends(get_organization_by_id)]
):
    """Get organization by ID."""
    response = OrganizationResponse.model_validate(organization)
    response.member_count = len(organization.users)
    return response


@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    update_data: OrganizationUpdate,
    organization: Annotated[Organization, Depends(get_user_organization)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update organization information (members only)."""
    # Update only provided fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(organization, field, value)
    
    await db.commit()
    await db.refresh(organization)
    
    response = OrganizationResponse.model_validate(organization)
    response.member_count = len(organization.users)
    return response


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    organization_id: str,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Delete an organization (admin only)."""
    organization = await get_organization_by_id(organization_id, db)
    await db.delete(organization)
    await db.commit()


# Address Management endpoints
@router.post("/{organization_id}/addresses", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_organization_address(
    organization_id: str,
    address_data: AddressCreate,
    organization: Annotated[Organization, Depends(get_user_organization)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new address for an organization (members only)."""
    # If this is the first address or marked as default, make it default
    if address_data.is_default or len(organization.addresses) == 0:
        # Unset any existing default addresses
        for addr in organization.addresses:
            addr.is_default = False
        address_data.is_default = True
    
    # Create new address
    new_address = OrganizationAddress(
        organization_id=organization_id,
        **address_data.model_dump()
    )
    db.add(new_address)
    await db.commit()
    await db.refresh(new_address)
    
    return new_address


@router.get("/{organization_id}/addresses", response_model=list[AddressResponse])
async def get_organization_addresses(
    organization: Annotated[Organization, Depends(get_organization_by_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    labels: list[str] = Query(default=[], description="Filter by label IDs")
):
    """Get all addresses for an organization. Can filter by labels."""
    if not labels:
        return organization.addresses
    
    # Filter addresses by labels
    query = (
        select(OrganizationAddress)
        .where(OrganizationAddress.organization_id == organization.id)
        .join(address_labels)
        .where(address_labels.c.label_id.in_(labels))
    )
    result = await db.execute(query)
    addresses = result.scalars().all()
    return addresses


@router.get("/{organization_id}/addresses/{address_id}", response_model=AddressResponse)
async def get_organization_address(
    organization_id: str,
    address_id: str,
    organization: Annotated[Organization, Depends(get_organization_by_id)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get a specific address by ID."""
    result = await db.execute(
        select(OrganizationAddress).where(
            and_(
                OrganizationAddress.id == address_id,
                OrganizationAddress.organization_id == organization_id
            )
        )
    )
    address = result.scalar_one_or_none()
    
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    return address


@router.patch("/{organization_id}/addresses/{address_id}", response_model=AddressResponse)
async def update_organization_address(
    organization_id: str,
    address_id: str,
    address_data: AddressUpdate,
    organization: Annotated[Organization, Depends(get_user_organization)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update an organization address (members only)."""
    result = await db.execute(
        select(OrganizationAddress).where(
            and_(
                OrganizationAddress.id == address_id,
                OrganizationAddress.organization_id == organization_id
            )
        )
    )
    address = result.scalar_one_or_none()
    
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    # If setting as default, unset other default addresses
    update_dict = address_data.model_dump(exclude_unset=True)
    if update_dict.get("is_default") is True:
        for addr in organization.addresses:
            if addr.id != address_id:
                addr.is_default = False
    
    # Update address fields
    for field, value in update_dict.items():
        setattr(address, field, value)
    
    await db.commit()
    await db.refresh(address)
    
    return address


@router.delete("/{organization_id}/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization_address(
    organization_id: str,
    address_id: str,
    organization: Annotated[Organization, Depends(get_user_organization)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Delete an organization address (members only)."""
    result = await db.execute(
        select(OrganizationAddress).where(
            and_(
                OrganizationAddress.id == address_id,
                OrganizationAddress.organization_id == organization_id
            )
        )
    )
    address = result.scalar_one_or_none()
    
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    # If deleting the default address and there are other addresses, make the first one default
    was_default = address.is_default
    await db.delete(address)
    await db.commit()
    
    if was_default:
        # Refresh organization to get updated addresses
        await db.refresh(organization)
        if len(organization.addresses) > 0:
            organization.addresses[0].is_default = True
            await db.commit()


@router.post("/{organization_id}/addresses/{address_id}/set-default", response_model=AddressResponse)
async def set_default_address(
    organization_id: str,
    address_id: str,
    organization: Annotated[Organization, Depends(get_user_organization)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Set an address as the default address (members only)."""
    result = await db.execute(
        select(OrganizationAddress).where(
            and_(
                OrganizationAddress.id == address_id,
                OrganizationAddress.organization_id == organization_id
            )
        )
    )
    address = result.scalar_one_or_none()
    
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    # Unset all default addresses
    for addr in organization.addresses:
        addr.is_default = False
    
    # Set this address as default
    address.is_default = True
    await db.commit()
    await db.refresh(address)
    
    return address


# Access Request endpoints
@router.post("/access-requests", response_model=AccessRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_access_request(
    request_data: AccessRequestCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Request access to an organization by TIN/EIN."""
    # Find organization by TIN
    result = await db.execute(
        select(Organization).where(Organization.tin == request_data.tin)
    )
    organization = result.scalar_one_or_none()
    
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization with this TIN/EIN not found"
        )
    
    # Check if user is already a member
    is_member = any(org.id == organization.id for org in user.organizations)
    if is_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a member of this organization"
        )
    
    # Check for existing pending request
    result = await db.execute(
        select(OrganizationAccessRequest).where(
            and_(
                OrganizationAccessRequest.user_id == user.id,
                OrganizationAccessRequest.organization_id == organization.id,
                OrganizationAccessRequest.status == AccessRequestStatus.PENDING
            )
        )
    )
    existing_request = result.scalar_one_or_none()
    
    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a pending request for this organization"
        )
    
    # Create access request
    access_request = OrganizationAccessRequest(
        user_id=user.id,
        organization_id=organization.id,
        message=request_data.message
    )
    db.add(access_request)
    await db.commit()
    await db.refresh(access_request)
    
    return AccessRequestResponse(
        id=access_request.id,
        user_id=access_request.user_id,
        organization_id=access_request.organization_id,
        organization_name=organization.name,
        organization_npi=organization.npi,
        status=access_request.status,
        message=access_request.message,
        reviewed_by_id=access_request.reviewed_by_id,
        reviewed_at=access_request.reviewed_at,
        review_message=access_request.review_message,
        created_at=access_request.created_at,
        updated_at=access_request.updated_at
    )


@router.get("/access-requests/my", response_model=list[AccessRequestResponse])
async def get_my_access_requests(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get all access requests created by current user."""
    result = await db.execute(
        select(OrganizationAccessRequest)
        .where(OrganizationAccessRequest.user_id == user.id)
        .order_by(OrganizationAccessRequest.created_at.desc())
    )
    requests = result.scalars().all()
    
    return [
        AccessRequestResponse(
            id=req.id,
            user_id=req.user_id,
            organization_id=req.organization_id,
            organization_name=req.organization.name,
            organization_npi=req.organization.npi,
            status=req.status,
            message=req.message,
            reviewed_by_id=req.reviewed_by_id,
            reviewed_at=req.reviewed_at,
            review_message=req.review_message,
            created_at=req.created_at,
            updated_at=req.updated_at
        )
        for req in requests
    ]


@router.get("/{organization_id}/access-requests", response_model=list[AccessRequestResponse])
async def get_organization_access_requests(
    organization: Annotated[Organization, Depends(get_user_organization)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: AccessRequestStatus | None = None
):
    """Get all access requests for an organization (members only)."""
    query = select(OrganizationAccessRequest).where(
        OrganizationAccessRequest.organization_id == organization.id
    )
    
    if status_filter:
        query = query.where(OrganizationAccessRequest.status == status_filter)
    
    query = query.order_by(OrganizationAccessRequest.created_at.desc())
    
    result = await db.execute(query)
    requests = result.scalars().all()
    
    return [
        AccessRequestResponse(
            id=req.id,
            user_id=req.user_id,
            organization_id=req.organization_id,
            organization_name=organization.name,
            organization_npi=organization.npi,
            status=req.status,
            message=req.message,
            reviewed_by_id=req.reviewed_by_id,
            reviewed_at=req.reviewed_at,
            review_message=req.review_message,
            created_at=req.created_at,
            updated_at=req.updated_at
        )
        for req in requests
    ]


@router.post("/{organization_id}/access-requests/{request_id}/review", response_model=AccessRequestResponse)
async def review_access_request(
    organization_id: str,
    request_id: str,
    review_data: AccessRequestReview,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Review (approve/reject) an access request (organization members only)."""
    # Verify user is a member of the organization
    organization = await get_user_organization(organization_id, user, db)
    
    # Get access request
    result = await db.execute(
        select(OrganizationAccessRequest).where(
            and_(
                OrganizationAccessRequest.id == request_id,
                OrganizationAccessRequest.organization_id == organization_id
            )
        )
    )
    access_request = result.scalar_one_or_none()
    
    if access_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Access request not found"
        )
    
    if access_request.status != AccessRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This request has already been reviewed"
        )
    
    # Update request status
    access_request.status = AccessRequestStatus.APPROVED if review_data.approved else AccessRequestStatus.REJECTED
    access_request.reviewed_by_id = user.id
    access_request.reviewed_at = datetime.now()
    access_request.review_message = review_data.review_message
    
    # If approved, add user to organization
    if review_data.approved:
        stmt = user_organizations.insert().values(
            user_id=access_request.user_id,
            organization_id=organization_id,
            role="member",
            joined_at=datetime.now()
        )
        await db.execute(stmt)
    
    await db.commit()
    await db.refresh(access_request)
    
    return AccessRequestResponse(
        id=access_request.id,
        user_id=access_request.user_id,
        organization_id=access_request.organization_id,
        organization_name=organization.name,
        organization_npi=organization.npi,
        status=access_request.status,
        message=access_request.message,
        reviewed_by_id=access_request.reviewed_by_id,
        reviewed_at=access_request.reviewed_at,
        review_message=access_request.review_message,
        created_at=access_request.created_at,
        updated_at=access_request.updated_at
    )


# Admin endpoint to add user to organization directly
@router.post("/{organization_id}/members", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_user_to_organization(
    organization_id: str,
    add_data: AddUserToOrganization,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Add a user to an organization directly (admin only)."""
    # Verify organization exists
    organization = await get_organization_by_id(organization_id, db)
    
    # Verify user exists
    result = await db.execute(
        select(User).where(User.id == add_data.user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user is already a member
    is_member = any(org.id == organization_id for org in user.organizations)
    if is_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization"
        )
    
    # Add user to organization
    stmt = user_organizations.insert().values(
        user_id=add_data.user_id,
        organization_id=organization_id,
        role=add_data.role,
        joined_at=datetime.now()
    )
    await db.execute(stmt)
    await db.commit()
    
    return {
        "message": "User added to organization successfully",
        "user_id": add_data.user_id,
        "organization_id": organization_id,
        "role": add_data.role
    }


@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_organization(
    organization_id: str,
    user_id: str,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Remove a user from an organization (admin only)."""
    # Verify organization exists
    await get_organization_by_id(organization_id, db)
    
    # Verify user is a member before removing
    result = await db.execute(
        select(user_organizations).where(
            and_(
                user_organizations.c.user_id == user_id,
                user_organizations.c.organization_id == organization_id
            )
        )
    )
    membership = result.first()
    
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this organization"
        )
    
    # Remove user from organization
    stmt = user_organizations.delete().where(
        and_(
            user_organizations.c.user_id == user_id,
            user_organizations.c.organization_id == organization_id
        )
    )
    await db.execute(stmt)
    await db.commit()
