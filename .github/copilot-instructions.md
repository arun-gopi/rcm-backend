# RCM Backend - AI Agent Instructions

## Project Overview
FastAPI backend application using Python 3.12+ with UV package manager. Early-stage project following a feature-based architecture.

## Architecture

### Directory Structure
```
app/
  main.py          # Application entry point
  core/            # Core functionality (config, database, auth, middleware)
  features/        # Feature modules (each feature is self-contained)
```

**Feature Module Pattern**: Each feature should be self-contained in `app/features/<feature_name>/` with:
- `routes.py` - FastAPI route definitions
- `models.py` - SQLAlchemy models
- `schemas.py` - Pydantic schemas (request/response)
- `dependencies.py` - Feature-specific dependencies
- `auth.py` - Authentication utilities (if needed)

### Core Components
Place shared infrastructure in `app/core/`:
- `config.py` - Settings using Pydantic BaseSettings with python-dotenv
- `database/` - SQLAlchemy engine, base, and session management
- Feature modules in `app/features/` contain their own dependencies and auth logic

## Development Workflows

### Environment Setup
```bash
# Activate virtual environment (already exists at .venv/)
.venv\Scripts\Activate.ps1  # Windows

# Install dependencies
uv sync

# Copy environment template and configure
copy .env.example .env
# Edit .env with your configuration

# Run development server
uvicorn app.main:app --reload
```

### Package Management
- Use `uv add <package>` to add dependencies (updates pyproject.toml and uv.lock)
- Use `uv sync` to install from lock file
- Do NOT manually edit pyproject.toml dependencies

## Coding Conventions

### FastAPI Application Setup
- Create FastAPI app instance in `app/main.py`
- Use `APIRouter` for feature modules, include them in main app
- Rate limiting configured with slowapi using authorization headers
- Example router registration:
  ```python
  from app.features.users.routes import router as users_router
  app.include_router(users_router, prefix="/users", tags=["users"])
  ```
Authentication with Appwrite
- Uses Appwrite server SDK for JWT verification
- JWT tokens passed via `Authorization: Bearer <token>` header
- Users automatically created in local DB on first authentication
- Use ULID for primary keys (better than auto-increment for distributed systems)

**Authentication Dependencies**:
```python
from app.features.users.dependencies import get_current_user, get_current_admin_user

@router.get("/protected")
async def protected_route(user: User = Depends(get_current_user)):
    return {"user_id": user.id, "email": user.email}

@router.delete("/admin-only")
async def admin_route(admin: User = Depends(get_current_admin_user)):
    # Only accessible by admins
    pass
```

**Appwrite Setup**:
1. Create project at https://cloud.appwrite.io
2. Add `APPWRITE_PROJECT_ID` and `APPWRITE_API_KEY` to `.env`
3. JWT tokens issued by Appwrite client SDK automatically work

### Database Patterns
- **Current**: SQLite with aiosqlite (file: `data.db`)
- **Future**: PostgreSQL with asyncpg (update `DATABASE_URL` in `.env`)
- Use SQLAlchemy 2.0+ async style throughout
- All models inherit from `Base` in [app/core/database/base.py](../app/core/database/base.py)
- Use `TimestampMixin` for created_at/updated_at fields
- Use ULID for primary keys instead of auto-increment integers
- Get database sessions via dependency injection:
  ```python
  from app.core.database.engine import get_db
  from app.features.users.dependencies import get_current_user
  
  @router.get("/items")
  async def get_items(
      db: AsyncSession = Depends(get_db),
      user: User = Depends(get_current_user)
  
  async def get_items(db: AsyncSession = Depends(get_db)):
      result = await db.execute(select(Item))
      return result.scalars().all()
  ```

**Switching to PostgreSQL**:
1. Install: `uv add asyncpg`
2. Update `.env`: `DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname`
3. Restart server (no code changes needed)

### Configuration Management
- Store environment-specific config in `.env` file (not committed)
- Access via Pydantic Settings class in `app/core/config.py`
- Never hardcode secrets or environment-specific values

### API Response Patterns
- Use Pydantic schemas for request/response validation
- Return consistent response structures
- Handle exceptions with FastAPI exception handlers

## Key Files
- [pyproject.toml](../pyproject.toml) - Dependencies and project metadata
- [app/main.py](../app/main.py) - Application entry point
- `server.py` - Currently unused (empty file)

## Testing
- Add pytest to dependencies when implementing tests
- Follow pytest-asyncio for async test cases
- Structure: `tests/` directory mirroring `app/` structure
