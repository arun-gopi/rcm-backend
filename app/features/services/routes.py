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
    """
    Create a new service entry and optionally attach financials.
    
    Parameters:
        service_data (ServiceEntryCreate): Data for the new service entry; may include `financials` to create associated ServiceFinancials.
    
    Returns:
        ServiceEntry: The created service entry populated with any generated fields (e.g., `id`) and refreshed relations.
    
    Raises:
        HTTPException: 400 if a service entry with the same `external_id` already exists.
    """
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
    List service entries matching optional filters.
    
    Parameters:
    	organization_id (str | None): Filter by organization ID.
    	client_id (str | None): Filter by client ID.
    	provider_id (str | None): Filter by provider ID.
    	date_from (str | None): Include entries with date_of_service on or after this date (YYYY-MM-DD).
    	date_to (str | None): Include entries with date_of_service on or before this date (YYYY-MM-DD).
    	skip (int): Number of records to skip for pagination.
    	limit (int): Maximum number of records to return.
    
    Returns:
    	service_entries (list[ServiceEntry]): List of ServiceEntry records matching the provided filters, ordered by date_of_service descending.
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
    Create an active assignment for a service entry and record an internal assignment comment.
    
    Creates a new active ServiceAssignment for the given service entry, deactivates any previous active assignments for that entry, and adds an internal ServiceComment describing the assignment (including follow-up date and optional note).
    
    Parameters:
        service_id (str): ID of the service entry to assign.
        assignment_data (ServiceAssignmentCreate): Assignment details (assignee, follow-up date, optional note).
    
    Returns:
        ServiceAssignment: The newly created and persisted assignment.
    
    Raises:
        HTTPException: 404 if the specified service entry does not exist.
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
    Reassigns a service entry to a different user and records the reassignment as an internal comment.
    
    Parameters:
        reassign_data (ServiceReassignRequest): Data for the reassignment, including:
            - `new_assigned_to_user_id`: ID of the user to assign the service entry to.
            - `followup_date` (optional): Follow-up date for the new assignment.
            - `reason`: Text explaining why the reassignment is performed.
    
    Raises:
        HTTPException: If the service entry with the given `service_id` does not exist.
    
    Returns:
        ServiceAssignment: The newly created active assignment for the service entry.
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
    """
    Return the current active assignment for the given service entry.
    
    Returns:
        ServiceAssignment | None: The active ServiceAssignment for the service entry identified by `service_id`, or `None` if no active assignment exists.
    """
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
    """
    Return the full assignment history for a service entry ordered by creation time descending.
    
    Returns:
        list[ServiceAssignment]: Assignments for the specified service entry, newest first.
    """
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
    Attach a comment to the specified service entry.
    
    Creates a ServiceComment using the provided comment data and returns the persisted comment.
    
    Parameters:
        service_id (str): ID of the service entry to comment on.
        comment_data (ServiceCommentCreate): Payload containing `comment_text`, `comment_type`, and `is_internal`.
    
    Returns:
        ServiceComment: The newly created and refreshed comment record.
    
    Raises:
        HTTPException: 404 if the service entry with the given `service_id` does not exist.
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
    Retrieve comments for a service entry.
    
    Parameters:
        comment_type (str | None): Optional comment type filter (e.g., "note", "call", "email").
        limit (int): Maximum number of comments to return (default 50).
    
    Returns:
        list[ServiceComment]: Comments for the specified service entry ordered by newest first, limited to `limit`.
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
    Return a detailed view of a service entry including its financials, current assignment, and recent comments.
    
    Parameters:
        service_id (str): ID of the service entry to retrieve.
    
    Returns:
        ServiceEntryDetailedResponse: The service entry with embedded `current_assignment` (the active assignment or `None`) and `recent_comments` (up to 10 most recent comments).
    
    Raises:
        HTTPException: 404 if the service entry with the given ID does not exist.
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
    List service entries assigned to the current user with their current active assignment and recent comments.
    
    Parameters:
        followup_overdue (bool): If true, include only entries whose active assignment has a follow-up date earlier than today.
        skip (int): Number of entries to skip for pagination.
        limit (int): Maximum number of entries to return.
    
    Returns:
        list[ServiceEntryDetailedResponse]: Service entries assigned to the current user; each item includes the current active assignment (or None) and up to five most recent comments.
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