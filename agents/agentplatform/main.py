"""Agent Platform - FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from agentplatform.database import init_db
from agentplatform.routers.agents import router as agents_router
from agentplatform.strategies.builtin import register_builtin_strategies


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    register_builtin_strategies()
    print("Agent Platform started")

    yield

    # Shutdown
    print("Agent Platform shutting down")


app = FastAPI(
    title="Agent Platform",
    description="Autonomous trading agent management platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(agents_router, tags=["agents"])


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
