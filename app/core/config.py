import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database connection URL (async)
# SQLite (current): "sqlite+aiosqlite:///./data.db"
# PostgreSQL (future): "postgresql+asyncpg://user:pass@localhost/dbname"
SQLALCHEMY_DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./data.db")

# Allow requests from this origin
ALLOW_ORIGIN: Optional[str] = os.environ.get("ALLOW_ORIGIN")

# If true, enable docs and openapi.json endpoints
ENABLE_DOCS: bool = os.environ.get("ENABLE_DOCS") == "1"


APPWRITE_ENDPOINT = os.getenv("APPWRITE_ENDPOINT")
APPWRITE_PROJECT_ID = os.getenv("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.getenv("APPWRITE_API_KEY")
DATABASE_ID = os.getenv("DATABASE_ID")
COLLECTION_ID = os.getenv("COLLECTION_ID")