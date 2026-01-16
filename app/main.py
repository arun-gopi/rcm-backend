from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from timing_asgi import TimingMiddleware, TimingClient  # type: ignore
from timing_asgi.integrations import StarletteScopeToName  # type: ignore

from app.core import config
from app.core.database.engine import init_db
from app.features.users.routes import router as user_router
from app.features.organizations.routes import router as organization_router
from app.features.labels.routes import router as label_router
from app.features.permissions.routes import router as permission_router
from app.features.clients.routes import router as client_router
from app.features.providers.routes import router as provider_router
from app.features.payors.routes import router as payor_router
from app.features.services.routes import router as service_router
from app.features.csv_import.routes import router as csv_import_router
from app.features.users.dependencies import get_authorization_header
from app.utils import get_logger


log = get_logger(__name__)
log.info("Initializing server")
app = FastAPI(
    title="RCM Backend",
    description="FastAPI backend with Appwrite authentication",
    version="0.1.0",
    docs_url="/docs" if config.ENABLE_DOCS else None,
    redoc_url="/redoc" if config.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if config.ENABLE_DOCS else None
)
limiter = Limiter(key_func=get_authorization_header)
app.state.limiter = limiter


class PrintTimings(TimingClient):
    def timing(self, metric_name, timing, tags):
        log.debug(dict(route=metric_name.removeprefix("main.app.features."), timing=timing, tags=tags))


app.add_middleware(TimingMiddleware, client=PrintTimings(), metric_namer=StarletteScopeToName("main", app))

if config.ENABLE_DOCS:
    log.warning("Docs enabled")
if config.ALLOW_ORIGIN:
    log.warning("Setting allow origin to %s", config.ALLOW_ORIGIN)
    origins = [config.ALLOW_ORIGIN]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    errors = dict()
    for error in exc.errors():
        if "loc" not in error or "msg" not in error:
            continue
        key = error["loc"][-1]
        if key == "__root__":
            key = "root"
        errors[key] = error["msg"]
    log.info("Request validation error %s", errors)
    return JSONResponse(status_code=400, content=jsonable_encoder(errors))


@app.exception_handler(RateLimitExceeded)
def rate_limit_exceeded_handler(_request: Request, _exc: RateLimitExceeded) -> Response:
    return JSONResponse({"error": "You are going too fast"}, status_code=429)


@app.on_event("startup")
async def startup():
    """Initialize database on application startup."""
    log.info("Initializing database...")
    await init_db()
    log.info("Database initialized successfully")


@app.get("/")
async def root():
    """Root endpoint - API health check."""
    return {
        "message": "RCM Backend API",
        "version": "0.1.0",
        "status": "online",
        "docs": "/docs" if config.ENABLE_DOCS else None,
        "authentication": {
            "info": "Protected endpoints require Bearer token in Authorization header",
            "protected_endpoints": [
                "/users/me", "/users/{id}/admin",
                "/organizations/*", "/permissions/*",
                "/clients/*", "/providers/*", "/payors/*", "/services/*", "/csv-import/*"
            ],
            "public_endpoints": ["/users", "/users/{id}", "/organizations", "/organizations/{id}"]
        },
        "features": {
            "permissions": "Organization-scoped RBAC/ABAC with roles, groups, and dynamic conditions",
            "organizations": "Multi-tenant organization management with NPI/TIN",
            "users": "User management with Appwrite authentication",
            "labels": "Flexible labeling system for organizations and users",
            "clients": "Client management with location tracking",
            "providers": "Healthcare provider management with NPI",
            "payors": "Insurance payor/payer management",
            "services": "Service entry and financial tracking for RCM",
            "csv_import": "Bulk CSV import for service entries with validation"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# Include routers
app.include_router(user_router, prefix="/users", tags=["users"])
# Alias for singular form (if frontend uses /user/me)
app.include_router(user_router, prefix="/user", tags=["users"], include_in_schema=False)

# Organization routes
app.include_router(organization_router, prefix="/organizations", tags=["organizations"])
# Alias for singular form
app.include_router(organization_router, prefix="/organization", tags=["organizations"], include_in_schema=False)

# Label routes
app.include_router(label_router, prefix="/labels", tags=["labels"])

# Permission routes (RBAC/ABAC)
app.include_router(permission_router, prefix="/permissions", tags=["permissions"])

# Client routes
app.include_router(client_router, prefix="/clients", tags=["clients"])

# Provider routes
app.include_router(provider_router, prefix="/providers", tags=["providers"])

# Payor routes
app.include_router(payor_router, prefix="/payors", tags=["payors"])

# Service entry routes
app.include_router(service_router, prefix="/services", tags=["services"])

# CSV import routes
app.include_router(csv_import_router, prefix="/csv-import", tags=["csv-import"])