"""Public service - query functions for public market data."""

from datetime import datetime, timedelta, UTC
from decimal import Decimal

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Order, OrderSide, OrderStatus, Trade


async def get_companies(session: AsyncSession) -> list[Company]:
    """Get all companies.

    Args:
        session: Database session

    Returns:
        List of all companies
    """
    result = await session.execute(select(Company).order_by(Company.ticker))
    return list(result.scalars().all())


async def get_company(session: AsyncSession, ticker: str) -> Company | None:
    """Get a single company by ticker.

    Args:
        session: Database session
        ticker: Company ticker symbol

    Returns:
        Company or None if not found
    """
    result = await session.execute(
        select(Company).where(Company.ticker == ticker.upper())
    )
    return result.scalar_one_or_none()


async def get_last_price(session: AsyncSession, ticker: str) -> Decimal | None:
    """Get the last trade price for a ticker.

    Args:
        session: Database session
        ticker: Company ticker symbol

    Returns:
        Last trade price or None if no trades
    """
    result = await session.execute(
        select(Trade.price)
        .where(Trade.ticker == ticker.upper())
        .order_by(desc(Trade.timestamp))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_trades_24h(
    session: AsyncSession, ticker: str
) -> list[Trade]:
    """Get all trades in the last 24 hours for a ticker.

    Args:
        session: Database session
        ticker: Company ticker symbol

    Returns:
        List of trades in the last 24 hours
    """
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
    result = await session.execute(
        select(Trade)
        .where(and_(Trade.ticker == ticker.upper(), Trade.timestamp >= cutoff))
        .order_by(desc(Trade.timestamp))
    )
    return list(result.scalars().all())


async def get_volume_24h(session: AsyncSession, ticker: str) -> int:
    """Get total trade volume in the last 24 hours.

    Args:
        session: Database session
        ticker: Company ticker symbol

    Returns:
        Sum of trade quantities in last 24 hours
    """
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
    result = await session.execute(
        select(func.coalesce(func.sum(Trade.quantity), 0))
        .where(and_(Trade.ticker == ticker.upper(), Trade.timestamp >= cutoff))
    )
    return int(result.scalar_one())


async def get_price_stats_24h(
    session: AsyncSession, ticker: str
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Get 24h price statistics: opening price, high, low.

    Args:
        session: Database session
        ticker: Company ticker symbol

    Returns:
        Tuple of (opening_price, high_24h, low_24h)
    """
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)

    # Get high and low
    result = await session.execute(
        select(func.max(Trade.price), func.min(Trade.price))
        .where(and_(Trade.ticker == ticker.upper(), Trade.timestamp >= cutoff))
    )
    row = result.one()
    high_24h = row[0]
    low_24h = row[1]

    # Get opening price (oldest trade in 24h window)
    result = await session.execute(
        select(Trade.price)
        .where(and_(Trade.ticker == ticker.upper(), Trade.timestamp >= cutoff))
        .order_by(Trade.timestamp)
        .limit(1)
    )
    opening_price = result.scalar_one_or_none()

    return opening_price, high_24h, low_24h


async def get_order_book(
    session: AsyncSession, ticker: str, depth: int = 10
) -> tuple[list[tuple[Decimal, int]], list[tuple[Decimal, int]]]:
    """Get aggregated order book for a ticker.

    Args:
        session: Database session
        ticker: Company ticker symbol
        depth: Maximum number of price levels to return

    Returns:
        Tuple of (bids, asks) where each is a list of (price, total_quantity)
        Bids sorted by price descending (best bid first)
        Asks sorted by price ascending (best ask first)
    """
    ticker = ticker.upper()

    # Get aggregated bids (BUY orders) - highest price first
    bids_result = await session.execute(
        select(Order.price, func.sum(Order.remaining_quantity).label("total_qty"))
        .where(
            and_(
                Order.ticker == ticker,
                Order.side == OrderSide.BUY,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
                Order.price.isnot(None),  # Exclude market orders
            )
        )
        .group_by(Order.price)
        .order_by(desc(Order.price))
        .limit(depth)
    )
    bids = [(row.price, int(row.total_qty)) for row in bids_result.all()]

    # Get aggregated asks (SELL orders) - lowest price first
    asks_result = await session.execute(
        select(Order.price, func.sum(Order.remaining_quantity).label("total_qty"))
        .where(
            and_(
                Order.ticker == ticker,
                Order.side == OrderSide.SELL,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
                Order.price.isnot(None),  # Exclude market orders
            )
        )
        .group_by(Order.price)
        .order_by(Order.price)
        .limit(depth)
    )
    asks = [(row.price, int(row.total_qty)) for row in asks_result.all()]

    return bids, asks


async def get_recent_trades(
    session: AsyncSession,
    ticker: str,
    limit: int = 50,
    since: datetime | None = None,
) -> list[Trade]:
    """Get recent trades for a ticker.

    Args:
        session: Database session
        ticker: Company ticker symbol
        limit: Maximum number of trades to return
        since: Only return trades after this timestamp

    Returns:
        List of trades, most recent first
    """
    query = select(Trade).where(Trade.ticker == ticker.upper())

    if since:
        query = query.where(Trade.timestamp > since)

    query = query.order_by(desc(Trade.timestamp)).limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())
