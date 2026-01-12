# RCM Backend

FastAPI backend application with Appwrite authentication, SQLAlchemy ORM, and feature-based architecture.

## Features

- 🚀 **FastAPI** - Modern, fast web framework for building APIs
- 🔐 **Appwrite Authentication** - JWT-based auth with automatic user sync
- 🗄️ **SQLAlchemy 2.0+** - Async ORM with SQLite (PostgreSQL-ready)
- 📦 **UV Package Manager** - Fast, reliable Python package management
- 🏗️ **Feature-Based Architecture** - Self-contained, scalable modules
- 🔒 **Rate Limiting** - Built-in API rate limiting with slowapi
- ⚡ **ULID Primary Keys** - Better than auto-increment for distributed systems

## Quick Start

### Prerequisites

- Python 3.12+
- UV package manager
- Appwrite account ([cloud.appwrite.io](https://cloud.appwrite.io))

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd rcm-backend

# Activate virtual environment
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate    # Linux/Mac

# Install dependencies
uv sync

# Configure environment
copy .env.example .env
# Edit .env with your Appwrite credentials
```

### Configuration

Create a `.env` file with the following variables:

```env
# Appwrite Configuration
APPWRITE_PROJECT_ID=your_project_id
APPWRITE_API_KEY=your_api_key
APPWRITE_ENDPOINT=https://cloud.appwrite.io/v1

# Database
DATABASE_URL=sqlite+aiosqlite:///./data.db

# Server
ENABLE_DOCS=true
ALLOW_ORIGIN=http://localhost:3000
```

### Running the Server

```bash
# Development mode with auto-reload
uv run server.py

# Or using uvicorn directly
uvicorn app.main:app --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

## Project Structure

```
rcm-backend/
├── app/
│   ├── main.py                 # Application entry point
│   ├── core/                   # Core functionality
│   │   ├── config.py          # Configuration management
│   │   └── database/          # Database setup
│   ├── features/              # Feature modules
│   │   ├── users/            # User management
│   │   ├── organizations/    # Organization management
│   │   └── labels/           # Label management
│   └── utils.py              # Shared utilities
├── .env                       # Environment variables (not committed)
├── .env.example              # Environment template
├── pyproject.toml            # Project dependencies
├── uv.lock                   # Lock file
└── server.py                 # Server entry point
```

## API Endpoints

### Public Endpoints
- `GET /` - API information
- `GET /health` - Health check
- `GET /users` - List all users
- `GET /users/{id}` - Get user by ID
- `GET /organizations` - List organizations
- `GET /organizations/{id}` - Get organization by ID

### Protected Endpoints (Requires Authentication)
- `GET /users/me` - Get current user
- `PUT /users/me` - Update current user
- `POST /organizations` - Create organization
- `PUT /organizations/{id}` - Update organization
- `DELETE /organizations/{id}` - Delete organization

### Admin-Only Endpoints
- `DELETE /users/{id}/admin` - Delete user (admin only)

## Authentication

All protected endpoints require a JWT token from Appwrite:

```bash
curl -H "Authorization: Bearer <appwrite-jwt-token>" \
    http://localhost:8000/users/me
```

Users are automatically created in the local database on first authentication.

## Development

### Adding Dependencies

```bash
# Add a new package
uv add <package-name>

# Add development dependency
uv add --dev <package-name>

# Sync dependencies
uv sync
```

### Creating a New Feature

Create a new feature module in `app/features/<feature_name>/`:

```
app/features/example/
├── __init__.py
├── routes.py          # FastAPI routes
├── models.py          # SQLAlchemy models
├── schemas.py         # Pydantic schemas
├── dependencies.py    # Feature dependencies
└── auth.py           # Authentication (optional)
```

Register the router in `app/main.py`:

```python
from app.features.example.routes import router as example_router
app.include_router(example_router, prefix="/examples", tags=["examples"])
```

### Database Migrations

Currently using SQLite with auto-create on startup. For production with PostgreSQL:

1. Update `DATABASE_URL` in `.env`:
     ```env
     DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname
     ```

2. Install asyncpg:
     ```bash
     uv add asyncpg
     ```

3. Restart the server (models auto-create on startup)

## Documentation

- Full setup instructions: `.github/copilot-instructions.md`
- API documentation: http://localhost:8000/docs (when `ENABLE_DOCS=true`)

## Tech Stack

- **FastAPI** - Web framework
- **SQLAlchemy** - ORM with async support
- **Appwrite** - Authentication provider
- **Pydantic** - Data validation
- **UV** - Package management
- **SQLite/PostgreSQL** - Database
- **slowapi** - Rate limiting
- **uvicorn** - ASGI server

## License

[Add your license here]