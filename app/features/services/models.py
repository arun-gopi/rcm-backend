"""
ServiceEntry, ServiceFinancials, ServiceAssignment, and ServiceComment models for RCM collection management.
"""
from sqlalchemy import String, Boolean, Integer, Numeric, ForeignKey, Index, Date, Time, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ulid import ulid
from decimal import Decimal

from app.core.database.base import Base, TimestampMixin


class ServiceEntry(Base, TimestampMixin):
    """
    Individual service entry representing a billable service provided to a client.
    
    This is the core entity in the RCM system, linking clients, providers, and billing.
    
    Attributes:
        id: ULID primary key
        external_id: External system identifier (unique, for idempotent imports)
        organization_id: Organization that owns this service entry
        group_id: Optional grouping identifier (practice group, department, etc.)
        
        client_id: Foreign key to Client receiving the service
        client_location_id: Optional location where service was provided
        provider_id: Foreign key to Provider delivering the service
        
        date_of_service: Date the service was provided (stored as string YYYY-MM-DD)
        time_from: Service start time (stored as string HH:MM)
        time_to: Service end time (stored as string HH:MM)
        minutes_worked: Total minutes of service delivery
        units: Billing units (often minutes/15 or other unit conversion)
        
        procedure_code: CPT/HCPCS code
        procedure_description: Human-readable description of the procedure
        
        authorization_id: Insurance authorization number
        
        is_locked: Service entry is finalized and cannot be edited
        is_void: Service entry has been voided
        is_deleted: Soft delete flag
        
        signed_by_provider: Provider has signed off on this entry
        signed_by_client: Client has signed off on this entry
    """
    __tablename__ = "service_entries"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(ulid()))
    external_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    group_id: Mapped[str | None] = mapped_column(String, index=True)

    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    client_location_id: Mapped[str | None] = mapped_column(ForeignKey("client_locations.id"), index=True)

    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), nullable=False, index=True)

    date_of_service: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    time_from: Mapped[str | None] = mapped_column(String(5))
    time_to: Mapped[str | None] = mapped_column(String(5))
    minutes_worked: Mapped[int | None] = mapped_column(Integer)
    units: Mapped[int | None] = mapped_column(Integer)

    procedure_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    procedure_description: Mapped[str | None] = mapped_column(String(255))

    authorization_id: Mapped[str | None] = mapped_column(String(50))

    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_void: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    signed_by_provider: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    signed_by_client: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    client = relationship("Client", backref="service_entries")
    client_location = relationship("ClientLocation", backref="service_entries")
    provider = relationship("Provider", backref="service_entries")
    financials = relationship("ServiceFinancials", back_populates="service_entry", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_service_entries_org_date", "organization_id", "date_of_service"),
        Index("ix_service_entries_client_date", "client_id", "date_of_service"),
        Index("ix_service_entries_provider_date", "provider_id", "date_of_service"),
    )

    def __repr__(self):
        return f"<ServiceEntry(id={self.id}, external_id='{self.external_id}', date={self.date_of_service})>"


class ServiceFinancials(Base, TimestampMixin):
    """
    Financial tracking for a service entry.
    
    One-to-one relationship with ServiceEntry to separate transactional data
    from frequently updated financial information.
    
    Attributes:
        service_entry_id: Foreign key to ServiceEntry (also primary key)
        
        rate_client: Billable rate to client/insurance
        rate_provider: Rate paid to provider
        
        drive_minutes: Minutes spent driving to/from service location
        mileage: Miles driven (for reimbursement)
        
        client_charge: Amount charged to client/insurance
        agreed_charge: Negotiated/contracted amount
        copay_amount: Patient responsibility (copay/coinsurance)
        
        amount_paid: Total amount received
        amount_adjusted: Adjustments (write-offs, discounts)
        amount_owed: Outstanding balance
        
        invoiced: Has been included in an invoice
        exported: Has been exported to billing system
    """
    __tablename__ = "service_financials"

    service_entry_id: Mapped[str] = mapped_column(
        ForeignKey("service_entries.id", ondelete="CASCADE"),
        primary_key=True
    )

    rate_client: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    rate_provider: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    drive_minutes: Mapped[int | None] = mapped_column(Integer)
    mileage: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    client_charge: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    agreed_charge: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    copay_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    amount_paid: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    amount_adjusted: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    amount_owed: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    invoiced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    exported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    service_entry = relationship("ServiceEntry", back_populates="financials")

    def __repr__(self):
        return f"<ServiceFinancials(service_entry_id={self.service_entry_id}, client_charge={self.client_charge})>"


class ServiceAssignment(Base, TimestampMixin):
    """
    Assignment tracking for service entries - who is responsible for follow-up.
    
    Supports assignment history and reassignment workflow for collection follow-up.
    
    Attributes:
        id: ULID primary key
        service_entry_id: Foreign key to ServiceEntry
        assigned_to_user_id: User ID responsible for this entry
        assigned_by_user_id: User ID who made the assignment
        followup_date: Date when follow-up is needed (YYYY-MM-DD)
        is_active: Whether this is the current active assignment
        assignment_note: Optional note about why this assignment was made
    """
    __tablename__ = "service_assignments"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(ulid()))
    service_entry_id: Mapped[str] = mapped_column(ForeignKey("service_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_to_user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    assigned_by_user_id: Mapped[str] = mapped_column(String, nullable=False)
    followup_date: Mapped[str | None] = mapped_column(String(10))  # YYYY-MM-DD format
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    assignment_note: Mapped[str | None] = mapped_column(Text)

    # Relationships
    service_entry = relationship("ServiceEntry", backref="assignments")

    __table_args__ = (
        Index("ix_service_assignments_active_user", "assigned_to_user_id", "is_active"),
        Index("ix_service_assignments_followup", "followup_date", "is_active"),
    )

    def __repr__(self):
        return f"<ServiceAssignment(id={self.id}, service_entry_id={self.service_entry_id}, assigned_to={self.assigned_to_user_id})>"


class ServiceComment(Base, TimestampMixin):
    """
    Comments/notes on service entries for tracking collection activities.
    
    Supports full audit trail of all communications and actions taken.
    
    Attributes:
        id: ULID primary key
        service_entry_id: Foreign key to ServiceEntry
        user_id: User who created the comment
        comment_text: The comment content
        comment_type: Type of comment (note, call, email, assignment, etc.)
        is_internal: Whether comment is internal only (not visible to client)
    """
    __tablename__ = "service_comments"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(ulid()))
    service_entry_id: Mapped[str] = mapped_column(ForeignKey("service_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    comment_type: Mapped[str] = mapped_column(String(50), default="note", nullable=False, index=True)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    service_entry = relationship("ServiceEntry", backref="comments")

    __table_args__ = (
        Index("ix_service_comments_entry_created", "service_entry_id", "created_at"),
    )

    def __repr__(self):
        return f"<ServiceComment(id={self.id}, service_entry_id={self.service_entry_id}, type={self.comment_type})>"
