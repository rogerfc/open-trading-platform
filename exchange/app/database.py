"""
Database configuration for the stock exchange.

Uses async SQLAlchemy with SQLite (local) or PostgreSQL (production).
Supports graceful degradation when database is unavailable.
"""

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Database URL from environment, defaults to SQLite for local development
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./stock_exchange.db")

# Create async engine
# echo=False by default, set SQLALCHEMY_ECHO=1 to enable SQL logging
engine = create_async_engine(DATABASE_URL, echo=os.getenv("SQLALCHEMY_ECHO") == "1")

# Session factory - creates new database sessions
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def init_db() -> None:
    """Create all database tables.

    Called on application startup to ensure tables exist.
    In production, you'd use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Dependency that provides a database session.

    Usage in FastAPI:
        @app.get("/example")
        async def example(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
