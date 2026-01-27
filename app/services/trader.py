"""Trader service - business logic for trader operations."""

import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, Company, Holding, Order, OrderSide, OrderStatus, OrderType
from app.schemas.trader import OrderCreate
from app import telemetry


def generate_order_id() -> str:
    """Generate a unique order ID."""
    return str(uuid.uuid4())


async def get_account_holdings(session: AsyncSession, account_id: str) -> list[Holding]:
    """Get all holdings for an account.

    Args:
        session: Database session
        account_id: Account ID

    Returns:
        List of holdings
    """
    result = await session.execute(
        select(Holding)
        .where(Holding.account_id == account_id)
        .order_by(Holding.ticker)
    )
    return list(result.scalars().all())


async def get_holding(
    session: AsyncSession, account_id: str, ticker: str
) -> Holding | None:
    """Get a specific holding for an account.

    Args:
        session: Database session
        account_id: Account ID
        ticker: Stock ticker

    Returns:
        Holding or None if not found
    """
    result = await session.execute(
        select(Holding).where(
            and_(Holding.account_id == account_id, Holding.ticker == ticker.upper())
        )
    )
    return result.scalar_one_or_none()


async def get_account_orders(
    session: AsyncSession,
    account_id: str,
    status: OrderStatus | None = None,
    ticker: str | None = None,
) -> list[Order]:
    """Get orders for an account.

    Args:
        session: Database session
        account_id: Account ID
        status: Filter by order status (optional)
        ticker: Filter by ticker (optional)

    Returns:
        List of orders
    """
    query = select(Order).where(Order.account_id == account_id)

    if status:
        query = query.where(Order.status == status)
    if ticker:
        query = query.where(Order.ticker == ticker.upper())

    query = query.order_by(Order.timestamp.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_order(
    session: AsyncSession, order_id: str, account_id: str
) -> Order | None:
    """Get a specific order.

    Args:
        session: Database session
        order_id: Order ID
        account_id: Account ID (for ownership verification)

    Returns:
        Order or None if not found or not owned by account
    """
    result = await session.execute(
        select(Order).where(and_(Order.id == order_id, Order.account_id == account_id))
    )
    return result.scalar_one_or_none()


async def get_company(session: AsyncSession, ticker: str) -> Company | None:
    """Get a company by ticker.

    Args:
        session: Database session
        ticker: Stock ticker

    Returns:
        Company or None if not found
    """
    result = await session.execute(
        select(Company).where(Company.ticker == ticker.upper())
    )
    return result.scalar_one_or_none()


async def place_order(
    session: AsyncSession, account: Account, data: OrderCreate
) -> Order:
    """Place a new order.

    Args:
        session: Database session
        account: The trader's account
        data: Order creation data

    Returns:
        The created order

    Raises:
        ValueError: If order validation fails
    """
    ticker = data.ticker.upper()

    # Validate ticker exists
    company = await get_company(session, ticker)
    if not company:
        raise ValueError(f"Unknown ticker: {ticker}")

    # Validate LIMIT orders have a price
    if data.order_type.value == "LIMIT" and data.price is None:
        raise ValueError("LIMIT orders require a price")

    # Validate MARKET orders don't have a price
    price = data.price
    if data.order_type.value == "MARKET":
        price = None  # Market orders don't store a price

    # For sell orders, verify the account has enough shares
    if data.side.value == "SELL":
        holding = await get_holding(session, account.id, ticker)
        available_shares = holding.quantity if holding else 0

        # Calculate shares already committed to other open sell orders
        open_sell_orders = await session.execute(
            select(Order).where(
                and_(
                    Order.account_id == account.id,
                    Order.ticker == ticker,
                    Order.side == OrderSide.SELL,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
                )
            )
        )
        committed_shares = sum(o.remaining_quantity for o in open_sell_orders.scalars())
        available_shares -= committed_shares

        if data.quantity > available_shares:
            raise ValueError(
                f"Insufficient shares: have {available_shares} available, "
                f"need {data.quantity}"
            )

    # For buy orders, verify the account has enough cash (for limit orders)
    if data.side.value == "BUY" and data.order_type.value == "LIMIT":
        required_cash = data.price * data.quantity

        # Calculate cash already committed to other open buy orders
        open_buy_orders = await session.execute(
            select(Order).where(
                and_(
                    Order.account_id == account.id,
                    Order.side == OrderSide.BUY,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
                    Order.price.isnot(None),
                )
            )
        )
        committed_cash = sum(
            o.price * o.remaining_quantity for o in open_buy_orders.scalars()
        )
        available_cash = account.cash_balance - committed_cash

        if required_cash > available_cash:
            raise ValueError(
                f"Insufficient funds: have {available_cash:.2f} available, "
                f"need {required_cash:.2f}"
            )

    # Create the order
    order = Order(
        id=generate_order_id(),
        account_id=account.id,
        ticker=ticker,
        side=OrderSide[data.side.value],
        order_type=OrderType[data.order_type.value],
        price=price,
        quantity=data.quantity,
        remaining_quantity=data.quantity,
        status=OrderStatus.OPEN,
    )
    session.add(order)
    await session.flush()  # Get order in DB before matching

    # Record telemetry for order placement
    telemetry.record_order_placed(ticker, data.side.value, data.order_type.value)

    # Attempt to match the order against the order book
    from app.services import matching

    await matching.match_order(session, order)

    await session.commit()
    await session.refresh(order)

    return order


async def cancel_order(session: AsyncSession, order: Order) -> Order:
    """Cancel an order.

    Args:
        session: Database session
        order: The order to cancel

    Returns:
        The cancelled order

    Raises:
        ValueError: If order cannot be cancelled
    """
    if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
        raise ValueError(f"Cannot cancel order with status {order.status.value}")

    order.status = OrderStatus.CANCELLED

    # Record telemetry for cancellation
    telemetry.record_order_cancelled(order.ticker)

    await session.commit()
    await session.refresh(order)

    return order
