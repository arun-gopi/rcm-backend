"""
Client and ClientLocation SQLAlchemy models for RCM collection management.
"""
from sqlalchemy import String, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
import ulid

from app.core.database.base import Base, TimestampMixin

def generate_ulid() -> str:
    """
    Generate a new ULID string.
    
    Returns:
        ulid_str (str): A new ULID value as a 26-character Crockford Base32 string.
    """
    return ulid.ulid()

class Client(Base, TimestampMixin):
    """
    Client entity representing the person receiving services.
    
    Attributes:
        id: ULID primary key
        external_client_id: External system identifier (unique, nullable for idempotent imports)
        first_name: Client's first name
        last_name: Client's last name
        timezone: Client's timezone (e.g., 'America/New_York')
        organization_id: Reference to the organization that manages this client
        locations: Related ClientLocation records
    """
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(primary_key=True, default=generate_ulid)
    external_client_id: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str | None] = mapped_column(String(50))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)

    # Relationships
    locations = relationship("ClientLocation", back_populates="client", cascade="all, delete-orphan")
    organization = relationship("Organization", backref="clients")

    __table_args__ = (
        Index("ix_clients_name", "last_name", "first_name"),
    )

    def __repr__(self):
        """
        Return a developer-facing string representation of the client including its id and full name.
        
        The representation is formatted for debugging and logging.
        
        Returns:
            str: A string containing the client's `id` and the full name in the form "<Client(id=<id>, name='First Last')>".
        """
        return f"<Client(id={self.id}, name='{self.first_name} {self.last_name}')>"


class ClientLocation(Base, TimestampMixin):
    """
    Physical location associated with a client for service delivery.
    
    Attributes:
        id: ULID primary key
        client_id: Foreign key to Client
        name: Location name/identifier (e.g., 'Home', 'School')
        address_line1: Primary address line
        address_line2: Secondary address line (apt, suite, etc.)
        city: City name
        state: State/province code
        zip: Postal/ZIP code
        country: Country code (defaults to 'US')
        client: Related Client record
    """
    __tablename__ = "client_locations"

    id: Mapped[str] = mapped_column(primary_key=True, default=generate_ulid)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    address_line1: Mapped[str | None] = mapped_column(String(255))
    address_line2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(2))
    zip: Mapped[str | None] = mapped_column(String(10))
    country: Mapped[str] = mapped_column(String(2), default="US", nullable=False)

    # Relationships
    client = relationship("Client", back_populates="locations")

    def __repr__(self):
        """
        Return a concise developer-facing representation of the ClientLocation including its id, client_id, and name.
        
        Returns:
            str: Formatted string like "<ClientLocation(id=<id>, client_id=<client_id>, name='<name>')>"
        """
        return f"<ClientLocation(id={self.id}, client_id={self.client_id}, name='{self.name}')>"