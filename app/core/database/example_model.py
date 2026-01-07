"""
Example SQLAlchemy model demonstrating the pattern.

This file shows how to create models in feature modules.
Each feature should define its models following this pattern.
"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, TimestampMixin


class ExampleItem(Base, TimestampMixin):
    """
    Example model showing the recommended pattern.
    
    - Inherits from Base (required for all models)
    - Includes TimestampMixin for automatic created_at/updated_at
    - Uses modern SQLAlchemy 2.0 Mapped annotations
    """
    __tablename__ = "example_items"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    def __repr__(self) -> str:
        return f"<ExampleItem(id={self.id}, name={self.name!r})>"
