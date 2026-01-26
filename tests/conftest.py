"""
Shared pytest fixtures for testing the stock exchange.

Uses an in-memory SQLite database for fast, isolated tests.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_session
from app.main import app
from app.models import Account, Company, Holding, Order, OrderSide, OrderStatus, OrderType, Trade


# Use in-memory SQLite for tests (fast, isolated)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    """Use asyncio backend for pytest-asyncio."""
    return "asyncio"


@pytest_asyncio.fixture
async def test_engine():
    """Create a test database engine.

    Creates tables at the start, drops them at the end.
    Each test gets a fresh database.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Provide a database session for a test.

    Rolls back the session after each test for isolation.
    """
    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_client(test_engine):
    """Provide a FastAPI test client with test database.

    Overrides the get_session dependency to use our test database.
    """
    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_session():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


# --- Helper fixtures for creating test data ---

@pytest_asyncio.fixture
async def sample_company(test_session):
    """Create a sample company for testing."""
    company = Company(
        ticker="TEST",
        name="Test Company",
        total_shares=1000000,
        float_shares=500000,
    )
    test_session.add(company)
    await test_session.commit()
    await test_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def sample_account(test_session):
    """Create a sample account for testing."""
    from decimal import Decimal

    account = Account(
        id="trader1",
        cash_balance=Decimal("10000.00"),
    )
    test_session.add(account)
    await test_session.commit()
    await test_session.refresh(account)
    return account


@pytest_asyncio.fixture
async def sample_account_2(test_session, sample_account):
    """Create a second sample account for testing trades."""
    from decimal import Decimal

    account = Account(
        id="trader2",
        cash_balance=Decimal("5000.00"),
    )
    test_session.add(account)
    await test_session.commit()
    await test_session.refresh(account)
    return account
