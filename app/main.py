"""
FastAPI application entry point.

Run with: uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db

# Import models to ensure they're registered with SQLAlchemy
from app.models import Account, Company, Holding, Order, Trade  # noqa: F401
from app.routers import admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Startup: Create database tables if they don't exist.
    Shutdown: (nothing to clean up for now)
    """
    # Startup
    await init_db()
    print("Database initialized")

    yield

    # Shutdown
    print("Application shutting down")


# Create FastAPI application
app = FastAPI(
    title="Stock Exchange API",
    description="A simple stock exchange simulation",
    version="0.1.0",
    lifespan=lifespan,
)


# Register routers
app.include_router(admin_router, prefix="/admin", tags=["admin"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
