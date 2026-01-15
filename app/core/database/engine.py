"""
Database engine configuration and session management.

Current: SQLite (async with aiosqlite)
Future: PostgreSQL (switch to asyncpg)

To switch to PostgreSQL:
1. Install asyncpg: `uv add asyncpg`
2. Update DATABASE_URL in .env to: postgresql+asyncpg://user:pass@host/db
3. No code changes needed in this file
"""
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core import config

# Create async engine
# SQLite: sqlite+aiosqlite:///./data.db
# PostgreSQL: postgresql+asyncpg://user:pass@localhost/dbname
engine = create_async_engine(
    config.SQLALCHEMY_DATABASE_URL,
    # NullPool for SQLite to avoid connection pool issues
    # For PostgreSQL, remove poolclass or use QueuePool
    poolclass=NullPool if config.SQLALCHEMY_DATABASE_URL.startswith("sqlite") else None,
    echo=False,  # Set to True for SQL query logging during development
    future=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database sessions.
    
    Usage in FastAPI routes:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Initialize database tables.
    Call this on application startup to create all tables.
    
    Usage in main.py:
        @app.on_event("startup")
        async def startup():
            await init_db()
    """
    from app.core.database.base import Base
    
    # Import all models to ensure they're registered with SQLAlchemy
    from app.features.users.models import User  # noqa: F401
    from app.features.organizations.models import (  # noqa: F401
        Organization, OrganizationAddress, OrganizationAccessRequest
    )
    from app.features.labels.models import Label  # noqa: F401
    from app.features.permissions.models import (  # noqa: F401
        Permission, Role, Group, AuditLog
    )
    
    async with engine.begin() as conn:
        # For development: drop and recreate all tables
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
