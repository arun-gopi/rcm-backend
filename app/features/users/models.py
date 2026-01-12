"""
User model with ULID primary keys.
"""
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import ulid

from app.core.database.base import Base, TimestampMixin


def generate_ulid() -> str:
    """Generate a new ULID string."""
    return ulid.ulid()


class User(Base, TimestampMixin):
    """
    User model representing authenticated users.
    
    Uses ULID instead of auto-incrementing integers for better distributed systems support.
    """
    __tablename__ = "users"
    
    # Primary key using ULID (Universally Unique Lexicographically Sortable Identifier)
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    
    # Appwrite user ID (for linking with Appwrite authentication)
    appwrite_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    # User information
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Optional fields
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    
    # Status flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Current active organization
    current_organization_id: Mapped[str | None] = mapped_column(
        String(26), 
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Track last login
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Relationships
    organizations: Mapped[list["Organization"]] = relationship(  # type: ignore
        "Organization",
        secondary="user_organizations",
        back_populates="users",
        lazy="selectin"
    )
    
    current_organization: Mapped["Organization"] = relationship(  # type: ignore
        "Organization",
        foreign_keys=[current_organization_id],
        lazy="selectin"
    )
    
    labels: Mapped[list["Label"]] = relationship(  # type: ignore
        "Label",
        secondary="user_labels",
        back_populates="users",
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email!r})>"
