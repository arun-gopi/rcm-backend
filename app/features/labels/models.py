"""
Label model for tagging users, organizations, and addresses.
"""
from sqlalchemy import String, ForeignKey, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
import ulid

from app.core.database.base import Base, TimestampMixin


def generate_ulid() -> str:
    """Generate a new ULID string."""
    return ulid.ulid()


class Label(Base, TimestampMixin):
    """
    Label model for tagging entities.
    
    Labels can be attached to users, organizations, and addresses.
    Examples: "VIP", "New Client", "Primary", "Inactive", "High Priority", etc.
    """
    __tablename__ = "labels"
    
    # Primary key using ULID
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    
    # Label properties
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # Hex color code like #FF5733
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Relationships
    users: Mapped[list["User"]] = relationship(  # type: ignore
        "User",
        secondary="user_labels",
        back_populates="labels",
        lazy="selectin"
    )
    
    organizations: Mapped[list["Organization"]] = relationship(  # type: ignore
        "Organization",
        secondary="organization_labels",
        back_populates="labels",
        lazy="selectin"
    )
    
    addresses: Mapped[list["OrganizationAddress"]] = relationship(  # type: ignore
        "OrganizationAddress",
        secondary="address_labels",
        back_populates="labels",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<Label(id={self.id}, name={self.name!r})>"


# Association tables for many-to-many relationships
user_labels = Table(
    "user_labels",
    Base.metadata,
    Column("user_id", String(26), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("label_id", String(26), ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True),
)

organization_labels = Table(
    "organization_labels",
    Base.metadata,
    Column("organization_id", String(26), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
    Column("label_id", String(26), ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True),
)

address_labels = Table(
    "address_labels",
    Base.metadata,
    Column("address_id", String(26), ForeignKey("organization_addresses.id", ondelete="CASCADE"), primary_key=True),
    Column("label_id", String(26), ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True),
)

