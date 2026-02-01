"""
FastAPI application entry point.

Run with: uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app._version import VERSION
from app.database import init_db

# Import models to ensure they're registered with SQLAlchemy
from app.models import Account, Company, Holding, Order, Trade  # noqa: F401
from app.routers import admin_router, portfolio_router, public_router, trader_router
from app import telemetry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Startup: Create database tables if they don't exist, initialize telemetry.
    Shutdown: (nothing to clean up for now)
    """
    # Startup
    await init_db()
    print("Database initialized")

    if telemetry.setup_telemetry():
        # Attach OTLP handler to root logger for log export
        handler = telemetry.get_log_handler()
        if handler:
            logging.getLogger().addHandler(handler)
            logging.getLogger().setLevel(logging.INFO)
        print("Telemetry initialized (OTLP metrics + logs enabled)")
    else:
        print("Telemetry disabled")

    yield

    # Shutdown
    print("Application shutting down")


# Create FastAPI application
app = FastAPI(
    title="Stock Exchange API",
    description="A simple stock exchange simulation",
    version=VERSION,
    lifespan=lifespan,
)


# Register routers
# Admin routes stay at /admin (no API versioning for admin)
app.include_router(admin_router, prefix="/admin", tags=["admin"])
# Public and trader routes under /api/v1
app.include_router(public_router, prefix="/api/v1", tags=["public"])
app.include_router(trader_router, prefix="/api/v1", tags=["trader"])
app.include_router(portfolio_router, prefix="/api/v1", tags=["portfolio"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/version")
async def get_version():
    """Get API version information."""
    return {
        "version": VERSION,
        "api_version": "v1",
        "min_client_version": "0.2.0",
    }
