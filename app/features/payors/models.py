"""
Payor SQLAlchemy model for RCM collection management.
"""
from sqlalchemy import String, Index
from sqlalchemy.orm import Mapped, mapped_column
import ulid

from app.core.database.base import Base, TimestampMixin

def generate_ulid() -> str:
    """Generate a new ULID string."""
    return ulid.ulid()


class Payor(Base, TimestampMixin):
    """
    Insurance payor/payer entity representing the organization that pays for services.
    
    Attributes:
        id: ULID primary key
        company_id: Payor company identifier
        plan_id: Specific insurance plan identifier
        name: Full payor name
        nickname: Short/friendly name for the payor
        organization_id: Reference to the organization managing this payor
    """
    __tablename__ = "payors"

    id: Mapped[str] = mapped_column(primary_key=True, default=generate_ulid)
    company_id: Mapped[str | None] = mapped_column(String, index=True)
    plan_id: Mapped[str | None] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(100))
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    __table_args__ = (
        Index("ix_payors_company_plan", "company_id", "plan_id"),
    )

    def __repr__(self):
        """
        Provide a concise developer-friendly representation of the Payor instance.
        
        Returns:
            repr_str (str): String in the form "<Payor(id={id}, name='{name}')>" where `{id}` and `{name}` are the instance's values.
        """
        return f"<Payor(id={self.id}, name='{self.name}')>"