"""Admin service - business logic for admin operations."""

import hashlib
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, Company, Holding, Order, OrderSide, OrderStatus, OrderType
from app.schemas.admin import AccountCreate, CompanyCreate


async def create_company(session: AsyncSession, data: CompanyCreate) -> Company:
    """Create a new company with treasury account and IPO sell order.

    This performs an IPO-like operation:
    1. Creates the company
    2. Creates a treasury account for the company
    3. Gives the treasury account the float shares
    4. Places a sell order for all float shares at the IPO price

    Args:
        session: Database session
        data: Company creation data

    Returns:
        The created company

    Raises:
        IntegrityError: If ticker already exists
    """
    ticker = data.ticker.upper()

    # 1. Create the company
    company = Company(
        ticker=ticker,
        name=data.name,
        total_shares=data.total_shares,
        float_shares=data.float_shares,
        ipo_price=data.ipo_price,
    )
    session.add(company)
    await session.flush()  # Get company in DB before creating related entities

    # 2. Create treasury account for the company
    treasury_id = f"{ticker}_TREASURY"
    api_key = generate_api_key()
    treasury_account = Account(
        id=treasury_id,
        api_key_hash=hash_api_key(api_key),
        cash_balance=0,  # Treasury starts with no cash
    )
    session.add(treasury_account)
    await session.flush()

    # 3. Give treasury account the float shares
    if data.float_shares > 0:
        holding = Holding(
            account_id=treasury_id,
            ticker=ticker,
            quantity=data.float_shares,
        )
        session.add(holding)

        # 4. Place IPO sell order for all float shares
        ipo_order = Order(
            id=str(uuid.uuid4()),
            account_id=treasury_id,
            ticker=ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=data.ipo_price,
            quantity=data.float_shares,
            remaining_quantity=data.float_shares,
            status=OrderStatus.OPEN,
        )
        session.add(ipo_order)

    await session.commit()
    await session.refresh(company)
    return company


async def list_companies(session: AsyncSession) -> list[Company]:
    """Get all companies.

    Args:
        session: Database session

    Returns:
        List of all companies
    """
    result = await session.execute(select(Company).order_by(Company.ticker))
    return list(result.scalars().all())


def generate_api_key() -> str:
    """Generate a secure API key for a trader account.

    Returns:
        A URL-safe random string (sk_ prefix + 43 characters)
    """
    return f"sk_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage.

    Args:
        api_key: The plain API key

    Returns:
        SHA-256 hash of the API key (64 hex characters)
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


async def create_account(session: AsyncSession, data: AccountCreate) -> tuple[Account, str]:
    """Create a new trader account.

    Args:
        session: Database session
        data: Account creation data

    Returns:
        Tuple of (created account, API key)

    Raises:
        IntegrityError: If account_id already exists
    """
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)

    account = Account(
        id=data.account_id,
        api_key_hash=api_key_hash,
        cash_balance=data.initial_cash,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)

    return account, api_key


async def list_accounts(session: AsyncSession) -> list[Account]:
    """Get all accounts.

    Args:
        session: Database session

    Returns:
        List of all accounts
    """
    result = await session.execute(select(Account).order_by(Account.created_at))
    return list(result.scalars().all())
