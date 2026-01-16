"""
Service entry management API routes with assignment and commenting system.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.engine import get_db
from app.features.users.dependencies import get_current_user
from app.features.users.models import User
from app.features.services.models import ServiceEntry, ServiceFinancials, ServiceAssignment, ServiceComment
from app.features.services.schemas import (
    ServiceEntryCreate, ServiceEntryResponse, ServiceEntryDetailedResponse,
    ServiceAssignmentCreate, ServiceAssignmentResponse, ServiceReassignRequest,
    ServiceCommentCreate, ServiceCommentResponse
)

router = APIRouter()


@router.post("", response_model=ServiceEntryResponse, status_code=201)
async def create_service_entry(
    service_data: ServiceEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new service entry with optional financials."""
    # Check if external_id already exists
    existing = await db.scalar(
        select(ServiceEntry).where(ServiceEntry.external_id == service_data.external_id)
    )
    if existing:
        raise HTTPException(status_code=400, detail="Service entry with this external_id already exists")
    
    # Extract financials if provided
    financials_data = service_data.financials
    service_dict = service_data.model_dump(exclude={"financials"})
    
    # Create service entry
    service = ServiceEntry(**service_dict)
    db.add(service)
    await db.flush()  # Flush to get the service ID
    
    # Create financials if provided
    if financials_data:
        financials = ServiceFinancials(
            service_entry_id=service.id,
            **financials_data.model_dump()
        )
        db.add(financials)
    
    await db.commit()
    await db.refresh(service)
    return service


@router.get("/{service_id}", response_model=ServiceEntryResponse)
async def get_service_entry(
    service_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific service entry by ID."""
    service = await db.scalar(
        select(ServiceEntry).where(ServiceEntry.id == service_id)
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service entry not found")
    return service


@router.get("", response_model=list[ServiceEntryResponse])
async def list_service_entries(
    organization_id: str | None = None,
    client_id: str | None = None,
    provider_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List service entries with optional filters.
    
    - organization_id: Filter by organization
    - client_id: Filter by client
    - provider_id: Filter by provider
    - date_from: Filter by date_of_service >= this date (YYYY-MM-DD)
    - date_to: Filter by date_of_service <= this date (YYYY-MM-DD)
    """
    query = select(ServiceEntry)
    
    if organization_id:
        query = query.where(ServiceEntry.organization_id == organization_id)
    if client_id:
        query = query.where(ServiceEntry.client_id == client_id)
    if provider_id:
        query = query.where(ServiceEntry.provider_id == provider_id)
    if date_from:
        query = query.where(ServiceEntry.date_of_service >= date_from)
    if date_to:
        query = query.where(ServiceEntry.date_of_service <= date_to)
    
    query = query.offset(skip).limit(limit).order_by(ServiceEntry.date_of_service.desc())
    
    result = await db.execute(query)
    return result.scalars().all()


# Assignment Endpoints

@router.post("/{service_id}/assign", response_model=ServiceAssignmentResponse, status_code=201)
async def assign_service_entry(
    service_id: str,
    assignment_data: ServiceAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign a service entry to a user for follow-up.
    
    - Deactivates any previous active assignments
    - Creates a new assignment record
    - Automatically adds a comment about the assignment
    """
    # Check if service entry exists
    service = await db.scalar(
        select(ServiceEntry).where(ServiceEntry.id == service_id)
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service entry not found")
    
    # Deactivate previous active assignments
    result = await db.execute(
        select(ServiceAssignment).where(
            and_(
                ServiceAssignment.service_entry_id == service_id,
                ServiceAssignment.is_active == True
            )
        )
    )
    for old_assignment in result.scalars():
        old_assignment.is_active = False
    
    # Create new assignment
    assignment = ServiceAssignment(
        service_entry_id=service_id,
        assigned_to_user_id=assignment_data.assigned_to_user_id,
        assigned_by_user_id=current_user.id,
        followup_date=assignment_data.followup_date,
        assignment_note=assignment_data.assignment_note,
        is_active=True
    )
    db.add(assignment)
    
    # Add comment about assignment
    comment_text = f"Assigned to user {assignment_data.assigned_to_user_id}"
    if assignment_data.followup_date:
        comment_text += f" with follow-up date: {assignment_data.followup_date}"
    if assignment_data.assignment_note:
        comment_text += f"\nNote: {assignment_data.assignment_note}"
    
    comment = ServiceComment(
        service_entry_id=service_id,
        user_id=current_user.id,
        comment_text=comment_text,
        comment_type="assignment",
        is_internal=True
    )
    db.add(comment)
    
    await db.commit()
    await db.refresh(assignment)
    return assignment


@router.post("/{service_id}/reassign", response_model=ServiceAssignmentResponse)
async def reassign_service_entry(
    service_id: str,
    reassign_data: ServiceReassignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reassign a service entry to another user.
    
    - Deactivates current assignment
    - Creates new assignment with the new user
    - Adds a comment with the reassignment reason
    """
    # Check if service entry exists
    service = await db.scalar(
        select(ServiceEntry).where(ServiceEntry.id == service_id)
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service entry not found")
    
    # Get current active assignment
    current_assignment = await db.scalar(
        select(ServiceAssignment).where(
            and_(
                ServiceAssignment.service_entry_id == service_id,
                ServiceAssignment.is_active == True
            )
        )
    )
    
    # Deactivate current assignment
    if current_assignment:
        current_assignment.is_active = False
    
    # Create new assignment
    new_assignment = ServiceAssignment(
        service_entry_id=service_id,
        assigned_to_user_id=reassign_data.new_assigned_to_user_id,
        assigned_by_user_id=current_user.id,
        followup_date=reassign_data.followup_date,
        assignment_note=f"Reassigned - Reason: {reassign_data.reason}",
        is_active=True
    )
    db.add(new_assignment)
    
    # Add comment about reassignment
    comment_text = f"Reassigned to user {reassign_data.new_assigned_to_user_id}"
    if current_assignment:
        comment_text = f"Reassigned from user {current_assignment.assigned_to_user_id} to user {reassign_data.new_assigned_to_user_id}"
    if reassign_data.followup_date:
        comment_text += f"\nFollow-up date: {reassign_data.followup_date}"
    comment_text += f"\nReason: {reassign_data.reason}"
    
    comment = ServiceComment(
        service_entry_id=service_id,
        user_id=current_user.id,
        comment_text=comment_text,
        comment_type="reassignment",
        is_internal=True
    )
    db.add(comment)
    
    await db.commit()
    await db.refresh(new_assignment)
    return new_assignment


@router.get("/{service_id}/assignment", response_model=ServiceAssignmentResponse | None)
async def get_current_assignment(
    service_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current active assignment for a service entry."""
    assignment = await db.scalar(
        select(ServiceAssignment).where(
            and_(
                ServiceAssignment.service_entry_id == service_id,
                ServiceAssignment.is_active == True
            )
        )
    )
    return assignment


@router.get("/{service_id}/assignments", response_model=list[ServiceAssignmentResponse])
async def get_assignment_history(
    service_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get full assignment history for a service entry."""
    result = await db.execute(
        select(ServiceAssignment)
        .where(ServiceAssignment.service_entry_id == service_id)
        .order_by(desc(ServiceAssignment.created_at))
    )
    return result.scalars().all()


# Comment Endpoints

@router.post("/{service_id}/comments", response_model=ServiceCommentResponse, status_code=201)
async def add_comment(
    service_id: str,
    comment_data: ServiceCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add a comment/note to a service entry.
    
    Comment types: note, call, email, payment, adjustment, etc.
    """
    # Check if service entry exists
    service = await db.scalar(
        select(ServiceEntry).where(ServiceEntry.id == service_id)
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service entry not found")
    
    comment = ServiceComment(
        service_entry_id=service_id,
        user_id=current_user.id,
        comment_text=comment_data.comment_text,
        comment_type=comment_data.comment_type,
        is_internal=comment_data.is_internal
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.get("/{service_id}/comments", response_model=list[ServiceCommentResponse])
async def get_comments(
    service_id: str,
    comment_type: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comments for a service entry.
    
    - comment_type: Filter by type (note, call, email, etc.)
    - limit: Maximum number of comments to return (default 50)
    """
    query = select(ServiceComment).where(ServiceComment.service_entry_id == service_id)
    
    if comment_type:
        query = query.where(ServiceComment.comment_type == comment_type)
    
    query = query.order_by(desc(ServiceComment.created_at)).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{service_id}/detailed", response_model=ServiceEntryDetailedResponse)
async def get_service_entry_detailed(
    service_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed service entry with current assignment and recent comments.
    
    Returns:
        - Service entry with financials
        - Current active assignment
        - Last 10 comments
    """
    # Get service entry
    service = await db.scalar(
        select(ServiceEntry).where(ServiceEntry.id == service_id)
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service entry not found")
    
    # Get current assignment
    current_assignment = await db.scalar(
        select(ServiceAssignment).where(
            and_(
                ServiceAssignment.service_entry_id == service_id,
                ServiceAssignment.is_active == True
            )
        )
    )
    
    # Get recent comments
    result = await db.execute(
        select(ServiceComment)
        .where(ServiceComment.service_entry_id == service_id)
        .order_by(desc(ServiceComment.created_at))
        .limit(10)
    )
    recent_comments = result.scalars().all()
    
    # Build response
    response_dict = ServiceEntryResponse.model_validate(service).model_dump()
    response_dict["current_assignment"] = current_assignment
    response_dict["recent_comments"] = recent_comments
    
    return ServiceEntryDetailedResponse(**response_dict)


# My Assignments - List all service entries assigned to current user

@router.get("/my/assignments", response_model=list[ServiceEntryDetailedResponse])
async def get_my_assignments(
    followup_overdue: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all service entries assigned to the current user.
    
    - followup_overdue: If true, only returns entries with overdue follow-up dates
    """
    from datetime import date
    
    query = select(ServiceEntry).join(
        ServiceAssignment,
        and_(
            ServiceAssignment.service_entry_id == ServiceEntry.id,
            ServiceAssignment.is_active == True,
            ServiceAssignment.assigned_to_user_id == current_user.id
        )
    )
    
    if followup_overdue:
        today = date.today().isoformat()
        query = query.where(
            and_(
                ServiceAssignment.followup_date.isnot(None),
                ServiceAssignment.followup_date < today
            )
        )
    
    query = query.offset(skip).limit(limit).order_by(desc(ServiceEntry.date_of_service))
    
    result = await db.execute(query)
    services = result.scalars().all()
    
    # Build detailed responses
    detailed_responses = []
    for service in services:
        response_dict = ServiceEntryResponse.model_validate(service).model_dump()
        
        # Get current assignment
        current_assignment = await db.scalar(
            select(ServiceAssignment).where(
                and_(
                    ServiceAssignment.service_entry_id == service.id,
                    ServiceAssignment.is_active == True
                )
            )
        )
        
        # Get recent comments
        comments_result = await db.execute(
            select(ServiceComment)
            .where(ServiceComment.service_entry_id == service.id)
            .order_by(desc(ServiceComment.created_at))
            .limit(5)
        )
        recent_comments = comments_result.scalars().all()
        
        response_dict["current_assignment"] = current_assignment
        response_dict["recent_comments"] = recent_comments
        
        detailed_responses.append(ServiceEntryDetailedResponse(**response_dict))
    
    return detailed_responses
