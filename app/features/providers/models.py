"""
Provider SQLAlchemy model for RCM collection management.
"""
from sqlalchemy import String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
import ulid

from app.core.database.base import Base, TimestampMixin

def generate_ulid() -> str:
    """
    Generate a new ULID string.
    
    Returns:
        ulid_str (str): A new ULID string.
    """
    return ulid.ulid()

class Provider(Base, TimestampMixin):
    """
    Healthcare provider who delivers services to clients.
    
    Attributes:
        id: ULID primary key
        external_provider_id: External system identifier (unique, nullable for idempotent imports)
        first_name: Provider's first name
        last_name: Provider's last name
        npi: National Provider Identifier (optional)
        organization_id: Reference to the organization this provider belongs to
    """
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(primary_key=True, default=generate_ulid)
    external_provider_id: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    npi: Mapped[str | None] = mapped_column(String(10), unique=True, index=True)
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    __table_args__ = (
        Index("ix_providers_name", "last_name", "first_name"),
    )

    def __repr__(self):
        """
        Return a developer-friendly string identifying the provider by id and full name.
        
        Returns:
            str: String in the format "<Provider(id=<id>, name='<first_name> <last_name>')>".
        """
        return f"<Provider(id={self.id}, name='{self.first_name} {self.last_name}')>"