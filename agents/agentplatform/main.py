"""Agent Platform - FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agentplatform.database import init_db
from agentplatform.routers.agents import router as agents_router
from agentplatform.strategies.builtin import register_builtin_strategies
from agentplatform.telemetry import setup_telemetry, get_log_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    register_builtin_strategies()
    if setup_telemetry():
        print("Telemetry enabled")
        # Add OTLP log handler to root logger
        handler = get_log_handler()
        if handler:
            logging.getLogger().addHandler(handler)
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
