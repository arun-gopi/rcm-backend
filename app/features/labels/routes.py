"""
Label feature routes.
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.engine import get_db
from app.features.users.models import User
from app.features.users.dependencies import get_current_user, get_current_admin_user
from app.features.labels.models import Label, user_labels, organization_labels, address_labels
from app.features.labels.schemas import (
    LabelCreate,
    LabelUpdate,
    LabelResponse,
    AttachLabelsRequest,
    DetachLabelsRequest,
    BulkAttachLabelsRequest,
    BulkDetachLabelsRequest,
    BulkOperationResponse
)
from app.features.organizations.models import Organization, OrganizationAddress


router = APIRouter(tags=["labels"])


# Label CRUD endpoints
@router.post("/", response_model=LabelResponse, status_code=status.HTTP_201_CREATED)
async def create_label(
    label_data: LabelCreate,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new label (admin only)."""
    # Check if label name already exists
    result = await db.execute(
        select(Label).where(Label.name == label_data.name)
    )
    existing_label = result.scalar_one_or_none()
    
    if existing_label:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label with this name already exists"
        )
    
    # Create label
    new_label = Label(**label_data.model_dump())
    db.add(new_label)
    await db.commit()
    await db.refresh(new_label)
    
    return new_label


@router.get("/", response_model=list[LabelResponse])
async def list_labels(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100
):
    """List all labels."""
    result = await db.execute(
        select(Label)
        .offset(skip)
        .limit(limit)
    )
    labels = result.scalars().all()
    return labels


@router.get("/{label_id}", response_model=LabelResponse)
async def get_label(
    label_id: str,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get label by ID."""
    result = await db.execute(
        select(Label).where(Label.id == label_id)
    )
    label = result.scalar_one_or_none()
    
    if label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Label not found"
        )
    
    return label


@router.patch("/{label_id}", response_model=LabelResponse)
async def update_label(
    label_id: str,
    label_data: LabelUpdate,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update label information (admin only)."""
    result = await db.execute(
        select(Label).where(Label.id == label_id)
    )
    label = result.scalar_one_or_none()
    
    if label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Label not found"
        )
    
    # Check if name is being changed and already exists
    update_dict = label_data.model_dump(exclude_unset=True)
    if "name" in update_dict and update_dict["name"] != label.name:
        result = await db.execute(
            select(Label).where(Label.name == update_dict["name"])
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Label with this name already exists"
            )
    
    # Update label fields
    for field, value in update_dict.items():
        setattr(label, field, value)
    
    await db.commit()
    await db.refresh(label)
    
    return label


@router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_label(
    label_id: str,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Delete a label (admin only)."""
    result = await db.execute(
        select(Label).where(Label.id == label_id)
    )
    label = result.scalar_one_or_none()
    
    if label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Label not found"
        )
    
    await db.delete(label)
    await db.commit()


# User Label Management
@router.post("/users/{user_id}/attach", response_model=dict)
async def attach_labels_to_user(
    user_id: str,
    labels_data: AttachLabelsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Attach labels to a user."""
    # Verify user exists
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify labels exist
    for label_id in labels_data.label_ids:
        result = await db.execute(
            select(Label).where(Label.id == label_id)
        )
        label = result.scalar_one_or_none()
        if label and label not in user.labels:
            user.labels.append(label)
    
    await db.commit()
    await db.refresh(user)
    
    return {
        "message": "Labels attached successfully",
        "user_id": user_id,
        "label_count": len(user.labels)
    }


@router.post("/users/{user_id}/detach", response_model=dict)
async def detach_labels_from_user(
    user_id: str,
    labels_data: DetachLabelsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Detach labels from a user."""
    # Verify user exists
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Remove labels
    for label_id in labels_data.label_ids:
        result = await db.execute(
            select(Label).where(Label.id == label_id)
        )
        label = result.scalar_one_or_none()
        if label and label in user.labels:
            user.labels.remove(label)
    
    await db.commit()
    await db.refresh(user)
    
    return {
        "message": "Labels detached successfully",
        "user_id": user_id,
        "label_count": len(user.labels)
    }


# Organization Label Management
@router.post("/organizations/{organization_id}/attach", response_model=dict)
async def attach_labels_to_organization(
    organization_id: str,
    labels_data: AttachLabelsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Attach labels to an organization."""
    # Verify organization exists
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Verify labels exist and attach
    for label_id in labels_data.label_ids:
        result = await db.execute(
            select(Label).where(Label.id == label_id)
        )
        label = result.scalar_one_or_none()
        if label and label not in organization.labels:
            organization.labels.append(label)
    
    await db.commit()
    await db.refresh(organization)
    
    return {
        "message": "Labels attached successfully",
        "organization_id": organization_id,
        "label_count": len(organization.labels)
    }


@router.post("/organizations/{organization_id}/detach", response_model=dict)
async def detach_labels_from_organization(
    organization_id: str,
    labels_data: DetachLabelsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Detach labels from an organization."""
    # Verify organization exists
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Remove labels
    for label_id in labels_data.label_ids:
        result = await db.execute(
            select(Label).where(Label.id == label_id)
        )
        label = result.scalar_one_or_none()
        if label and label in organization.labels:
            organization.labels.remove(label)
    
    await db.commit()
    await db.refresh(organization)
    
    return {
        "message": "Labels detached successfully",
        "organization_id": organization_id,
        "label_count": len(organization.labels)
    }


# Address Label Management
@router.post("/addresses/{address_id}/attach", response_model=dict)
async def attach_labels_to_address(
    address_id: str,
    labels_data: AttachLabelsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Attach labels to an address."""
    # Verify address exists
    result = await db.execute(
        select(OrganizationAddress).where(OrganizationAddress.id == address_id)
    )
    address = result.scalar_one_or_none()
    
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    # Verify labels exist and attach
    for label_id in labels_data.label_ids:
        result = await db.execute(
            select(Label).where(Label.id == label_id)
        )
        label = result.scalar_one_or_none()
        if label and label not in address.labels:
            address.labels.append(label)
    
    await db.commit()
    await db.refresh(address)
    
    return {
        "message": "Labels attached successfully",
        "address_id": address_id,
        "label_count": len(address.labels)
    }


@router.post("/addresses/{address_id}/detach", response_model=dict)
async def detach_labels_from_address(
    address_id: str,
    labels_data: DetachLabelsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Detach labels from an address."""
    # Verify address exists
    result = await db.execute(
        select(OrganizationAddress).where(OrganizationAddress.id == address_id)
    )
    address = result.scalar_one_or_none()
    
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    # Remove labels
    for label_id in labels_data.label_ids:
        result = await db.execute(
            select(Label).where(Label.id == label_id)
        )
        label = result.scalar_one_or_none()
        if label and label in address.labels:
            address.labels.remove(label)
    
    await db.commit()
    await db.refresh(address)
    
    return {
        "message": "Labels detached successfully",
        "address_id": address_id,
        "label_count": len(address.labels)
    }


# Bulk Operations
@router.post("/bulk/users/attach", response_model=BulkOperationResponse)
async def bulk_attach_labels_to_users(
    bulk_data: BulkAttachLabelsRequest,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Bulk attach labels to multiple users (admin only)."""
    successful_count = 0
    failed_count = 0
    details = []
    
    # Verify all labels exist first
    valid_labels = []
    for label_id in bulk_data.label_ids:
        result = await db.execute(
            select(Label).where(Label.id == label_id)
        )
        label = result.scalar_one_or_none()
        if label:
            valid_labels.append(label)
        else:
            details.append({
                "entity_type": "label",
                "entity_id": label_id,
                "status": "failed",
                "reason": "Label not found"
            })
    
    if not valid_labels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid labels found"
        )
    
    # Process each user
    for user_id in bulk_data.entity_ids:
        try:
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                failed_count += 1
                details.append({
                    "entity_type": "user",
                    "entity_id": user_id,
                    "status": "failed",
                    "reason": "User not found"
                })
                continue
            
            # Attach labels
            labels_attached = 0
            for label in valid_labels:
                if label not in user.labels:
                    user.labels.append(label)
                    labels_attached += 1
            
            await db.commit()
            await db.refresh(user)
            
            successful_count += 1
            details.append({
                "entity_type": "user",
                "entity_id": user_id,
                "status": "success",
                "labels_attached": labels_attached,
                "total_labels": len(user.labels)
            })
            
        except Exception as e:
            failed_count += 1
            details.append({
                "entity_type": "user",
                "entity_id": user_id,
                "status": "failed",
                "reason": str(e)
            })
    
    return BulkOperationResponse(
        message=f"Bulk operation completed: {successful_count} succeeded, {failed_count} failed",
        successful_count=successful_count,
        failed_count=failed_count,
        details=details
    )


@router.post("/bulk/users/detach", response_model=BulkOperationResponse)
async def bulk_detach_labels_from_users(
    bulk_data: BulkDetachLabelsRequest,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Bulk detach labels from multiple users (admin only)."""
    successful_count = 0
    failed_count = 0
    details = []
    
    # Verify all labels exist first
    valid_labels = []
    for label_id in bulk_data.label_ids:
        result = await db.execute(
            select(Label).where(Label.id == label_id)
        )
        label = result.scalar_one_or_none()
        if label:
            valid_labels.append(label)
    
    if not valid_labels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid labels found"
        )
    
    # Process each user
    for user_id in bulk_data.entity_ids:
        try:
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                failed_count += 1
                details.append({
                    "entity_type": "user",
                    "entity_id": user_id,
                    "status": "failed",
                    "reason": "User not found"
                })
                continue
            
            # Detach labels
            labels_detached = 0
            for label in valid_labels:
                if label in user.labels:
                    user.labels.remove(label)
                    labels_detached += 1
            
            await db.commit()
            await db.refresh(user)
            
            successful_count += 1
            details.append({
                "entity_type": "user",
                "entity_id": user_id,
                "status": "success",
                "labels_detached": labels_detached,
                "total_labels": len(user.labels)
            })
            
        except Exception as e:
            failed_count += 1
            details.append({
                "entity_type": "user",
                "entity_id": user_id,
                "status": "failed",
                "reason": str(e)
            })
    
    return BulkOperationResponse(
        message=f"Bulk operation completed: {successful_count} succeeded, {failed_count} failed",
        successful_count=successful_count,
        failed_count=failed_count,
        details=details
    )


@router.post("/bulk/organizations/attach", response_model=BulkOperationResponse)
async def bulk_attach_labels_to_organizations(
    bulk_data: BulkAttachLabelsRequest,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Bulk attach labels to multiple organizations (admin only)."""
    successful_count = 0
    failed_count = 0
    details = []
    
    # Verify all labels exist first
    valid_labels = []
    for label_id in bulk_data.label_ids:
        result = await db.execute(
            select(Label).where(Label.id == label_id)
        )
        label = result.scalar_one_or_none()
        if label:
            valid_labels.append(label)
        else:
            details.append({
                "entity_type": "label",
                "entity_id": label_id,
                "status": "failed",
                "reason": "Label not found"
            })
    
    if not valid_labels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid labels found"
        )
    
    # Process each organization
    for org_id in bulk_data.entity_ids:
        try:
            result = await db.execute(
                select(Organization).where(Organization.id == org_id)
            )
            org = result.scalar_one_or_none()
            
            if org is None:
                failed_count += 1
                details.append({
                    "entity_type": "organization",
                    "entity_id": org_id,
                    "status": "failed",
                    "reason": "Organization not found"
                })
                continue
            
            # Attach labels
            labels_attached = 0
            for label in valid_labels:
                if label not in org.labels:
                    org.labels.append(label)
                    labels_attached += 1
            
            await db.commit()
            await db.refresh(org)
            
            successful_count += 1
            details.append({
                "entity_type": "organization",
                "entity_id": org_id,
                "status": "success",
                "labels_attached": labels_attached,
                "total_labels": len(org.labels)
            })
            
        except Exception as e:
            failed_count += 1
            details.append({
                "entity_type": "organization",
                "entity_id": org_id,
                "status": "failed",
                "reason": str(e)
            })
    
    return BulkOperationResponse(
        message=f"Bulk operation completed: {successful_count} succeeded, {failed_count} failed",
        successful_count=successful_count,
        failed_count=failed_count,
        details=details
    )


@router.post("/bulk/organizations/detach", response_model=BulkOperationResponse)
async def bulk_detach_labels_from_organizations(
    bulk_data: BulkDetachLabelsRequest,
    admin: Annotated[User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Bulk detach labels from multiple organizations (admin only)."""
    successful_count = 0
    failed_count = 0
    details = []
    
    # Verify all labels exist first
    valid_labels = []
    for label_id in bulk_data.label_ids:
        result = await db.execute(
            select(Label).where(Label.id == label_id)
        )
        label = result.scalar_one_or_none()
        if label:
            valid_labels.append(label)
    
    if not valid_labels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid labels found"
        )
    
    # Process each organization
    for org_id in bulk_data.entity_ids:
        try:
            result = await db.execute(
                select(Organization).where(Organization.id == org_id)
            )
            org = result.scalar_one_or_none()
            
            if org is None:
                failed_count += 1
                details.append({
                    "entity_type": "organization",
                    "entity_id": org_id,
                    "status": "failed",
                    "reason": "Organization not found"
                })
                continue
            
            # Detach labels
            labels_detached = 0
            for label in valid_labels:
                if label in org.labels:
                    org.labels.remove(label)
                    labels_detached += 1
            
            await db.commit()
            await db.refresh(org)
            
            successful_count += 1
            details.append({
                "entity_type": "organization",
                "entity_id": org_id,
                "status": "success",
                "labels_detached": labels_detached,
                "total_labels": len(org.labels)
            })
            
        except Exception as e:
            failed_count += 1
            details.append({
                "entity_type": "organization",
                "entity_id": org_id,
                "status": "failed",
                "reason": str(e)
            })
    
    return BulkOperationResponse(
        message=f"Bulk operation completed: {successful_count} succeeded, {failed_count} failed",
        successful_count=successful_count,
        failed_count=failed_count,
        details=details
    )
