"""
Organization models for RCM backend.

Organizations represent healthcare entities with NPI and TIN/EIN.
Users can belong to multiple organizations and have a current active organization.
"""
from datetime import datetime
from sqlalchemy import String, ForeignKey, Table, Column, Boolean, Enum as SQLEnum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
import ulid

from app.core.database.base import Base, TimestampMixin


def generate_ulid() -> str:
    """Generate a new ULID string."""
    return ulid.ulid()


# Association table for many-to-many relationship between users and organizations
user_organizations = Table(
    "user_organizations",
    Base.metadata,
    Column("user_id", String(26), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("organization_id", String(26), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
    Column("joined_at", DateTime(timezone=True), nullable=False, default=datetime.now),
    Column("role", String(50), nullable=False, default="member"),  # member, admin, owner
)


class Organization(Base, TimestampMixin):
    """
    Organization model representing healthcare entities.
    
    Organizations have NPI (National Provider Identifier) and TIN/EIN (Tax Identification Number).
    Users can belong to multiple organizations.
    """
    __tablename__ = "organizations"
    
    # Primary key using ULID
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    
    # Organization identifiers (required for healthcare RCM)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    npi: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)  # 10-digit NPI
    tin: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)  # TIN/EIN
    
    # Optional organization details
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Organization settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    users: Mapped[list["User"]] = relationship(  # type: ignore
        "User",
        secondary=user_organizations,
        back_populates="organizations",
        lazy="selectin"
    )
    
    addresses: Mapped[list["OrganizationAddress"]] = relationship(
        "OrganizationAddress",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="desc(OrganizationAddress.is_default)"
    )
    
    access_requests: Mapped[list["OrganizationAccessRequest"]] = relationship(
        "OrganizationAccessRequest",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    labels: Mapped[list["Label"]] = relationship(  # type: ignore
        "Label",
        secondary="organization_labels",
        back_populates="organizations",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name!r}, npi={self.npi})>"


class OrganizationAddress(Base, TimestampMixin):
    """
    Address model for organizations.
    
    Organizations can have multiple addresses (billing, shipping, main office, etc.).
    One address can be marked as default.
    """
    __tablename__ = "organization_addresses"
    
    # Primary key using ULID
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    
    # Foreign key
    organization_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Address fields
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(50), nullable=False, default="USA")
    
    # Address type and settings
    address_type: Mapped[str] = mapped_column(String(50), nullable=False, default="main")  # main, billing, shipping, etc.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationship
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="addresses",
        lazy="selectin"
    )
    
    labels: Mapped[list["Label"]] = relationship(  # type: ignore
        "Label",
        secondary="address_labels",
        back_populates="addresses",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<OrganizationAddress(id={self.id}, org_id={self.organization_id}, type={self.address_type}, default={self.is_default})>"


class AccessRequestStatus(str, enum.Enum):
    """Status of organization access requests."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OrganizationAccessRequest(Base, TimestampMixin):
    """
    Access request for users to join organizations.
    
    Users can request access to an organization by providing TIN/EIN.
    Admins can approve or reject these requests.
    """
    __tablename__ = "organization_access_requests"
    
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    
    # Foreign keys
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(26), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Request details
    status: Mapped[AccessRequestStatus] = mapped_column(
        SQLEnum(AccessRequestStatus),
        default=AccessRequestStatus.PENDING,
        nullable=False,
        index=True
    )
    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # Optional message from user
    
    # Admin response
    reviewed_by_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    review_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # Admin's response
    
    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="selectin")  # type: ignore
    organization: Mapped["Organization"] = relationship("Organization", back_populates="access_requests", lazy="selectin")
    reviewed_by: Mapped["User"] = relationship("User", foreign_keys=[reviewed_by_id], lazy="selectin")  # type: ignore
    
    def __repr__(self) -> str:
        return f"<OrganizationAccessRequest(id={self.id}, user_id={self.user_id}, org_id={self.organization_id}, status={self.status})>"
