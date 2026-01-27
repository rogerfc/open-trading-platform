"""Order matching engine.

Implements price-time priority matching with the following rules:
1. BUY orders match against the lowest-priced SELL orders
2. SELL orders match against the highest-priced BUY orders
3. At the same price, earlier orders have priority (FIFO)
4. Execution price is the resting order's price (price improvement)
5. Self-trades are prevented (orders from same account don't match)
6. Market orders that cannot be fully filled have unfilled portion cancelled (IOC)
"""

import logging
import uuid
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Account,
    Holding,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Trade,
)
from app import telemetry

logger = logging.getLogger(__name__)


def generate_trade_id() -> str:
    """Generate a unique trade ID."""
    return str(uuid.uuid4())


async def match_order(session: AsyncSession, order: Order) -> list[Trade]:
    """Match an incoming order against the order book.

    Attempts to match the order against resting orders using price-time priority.
    Creates Trade records and updates accounts/holdings for each match.

    Args:
        session: Database session (caller manages transaction)
        order: The incoming order to match

    Returns:
        List of Trade objects created during matching
    """
    trades: list[Trade] = []

    while order.remaining_quantity > 0:
        # Find best matching resting order
        resting = await _get_matching_order(session, order)

        if resting is None:
            break  # No more matches available

        # Determine execution details
        execution_price = resting.price  # Price improvement for incoming order
        execution_quantity = min(order.remaining_quantity, resting.remaining_quantity)

        # Determine buyer and seller
        if order.side == OrderSide.BUY:
            buy_order, sell_order = order, resting
            buyer_id, seller_id = order.account_id, resting.account_id
        else:
            buy_order, sell_order = resting, order
            buyer_id, seller_id = resting.account_id, order.account_id

        # Validate buyer has sufficient cash (important for market buys)
        has_cash = await _validate_buyer_cash(
            session, buyer_id, execution_price, execution_quantity
        )
        if not has_cash:
            # For market orders, stop matching (cancel rest)
            # For limit orders, this shouldn't happen (validated at placement)
            break

        # Create trade record
        trade = Trade(
            id=generate_trade_id(),
            ticker=order.ticker,
            price=execution_price,
            quantity=execution_quantity,
            buyer_id=buyer_id,
            seller_id=seller_id,
            buy_order_id=buy_order.id,
            sell_order_id=sell_order.id,
        )
        session.add(trade)

        # Transfer cash and shares
        total_cash = execution_price * execution_quantity
        await _transfer_cash(session, buyer_id, seller_id, total_cash)
        await _transfer_shares(session, order.ticker, seller_id, buyer_id, execution_quantity)

        # Update order quantities and statuses
        _update_order_after_fill(order, execution_quantity)
        _update_order_after_fill(resting, execution_quantity)

        # Record telemetry
        telemetry.record_trade(order.ticker, execution_quantity, execution_price)
        if order.status == OrderStatus.FILLED:
            telemetry.record_order_filled(order.ticker)
        if resting.status == OrderStatus.FILLED:
            telemetry.record_order_filled(resting.ticker)

        # Structured logging for trade
        logger.info(
            "Trade executed",
            extra={
                "trade_id": trade.id,
                "ticker": order.ticker,
                "quantity": execution_quantity,
                "price": float(execution_price),
                "buyer_id": buyer_id,
                "seller_id": seller_id,
            },
        )

        trades.append(trade)

    # Handle unfilled market orders (IOC behavior)
    if order.order_type == OrderType.MARKET and order.remaining_quantity > 0:
        _cancel_unfilled_market_portion(order)

    return trades


async def _get_matching_order(
    session: AsyncSession,
    order: Order,
) -> Order | None:
    """Find the best matching resting order from the book.

    Uses price-time priority:
    - For BUY: lowest-priced SELL first, then earliest timestamp
    - For SELL: highest-priced BUY first, then earliest timestamp

    Args:
        session: Database session
        order: The incoming order seeking a match

    Returns:
        Best matching resting order, or None if no match available
    """
    if order.side == OrderSide.BUY:
        # Look for sells: lowest price first, then earliest time
        query = (
            select(Order)
            .where(
                and_(
                    Order.ticker == order.ticker,
                    Order.side == OrderSide.SELL,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
                    Order.account_id != order.account_id,  # Prevent self-trade
                )
            )
            .order_by(Order.price.asc(), Order.timestamp.asc())
            .limit(1)
        )

        # LIMIT orders have price constraint
        if order.order_type == OrderType.LIMIT:
            query = query.where(Order.price <= order.price)

    else:  # SELL
        # Look for buys: highest price first, then earliest time
        query = (
            select(Order)
            .where(
                and_(
                    Order.ticker == order.ticker,
                    Order.side == OrderSide.BUY,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
                    Order.price.isnot(None),  # Exclude market orders from book
                    Order.account_id != order.account_id,  # Prevent self-trade
                )
            )
            .order_by(Order.price.desc(), Order.timestamp.asc())
            .limit(1)
        )

        # LIMIT orders have price constraint
        if order.order_type == OrderType.LIMIT:
            query = query.where(Order.price >= order.price)

    result = await session.execute(query)
    return result.scalar_one_or_none()


async def _validate_buyer_cash(
    session: AsyncSession,
    buyer_id: str,
    price: Decimal,
    quantity: int,
) -> bool:
    """Check if buyer has sufficient cash for the trade.

    For market buys, we must validate at match time since we don't
    know the execution price when the order is placed.

    Args:
        session: Database session
        buyer_id: Account ID of the buyer
        price: Execution price per share
        quantity: Number of shares

    Returns:
        True if buyer has sufficient cash
    """
    result = await session.execute(
        select(Account).where(Account.id == buyer_id)
    )
    buyer = result.scalar_one()

    required_cash = price * quantity
    return buyer.cash_balance >= required_cash


async def _transfer_cash(
    session: AsyncSession,
    buyer_id: str,
    seller_id: str,
    amount: Decimal,
) -> None:
    """Transfer cash from buyer to seller.

    Args:
        session: Database session
        buyer_id: Account paying cash
        seller_id: Account receiving cash
        amount: Total cash amount (price * quantity)
    """
    # Get both accounts
    result = await session.execute(
        select(Account).where(Account.id == buyer_id)
    )
    buyer = result.scalar_one()

    result = await session.execute(
        select(Account).where(Account.id == seller_id)
    )
    seller = result.scalar_one()

    # Transfer cash
    buyer.cash_balance -= amount
    seller.cash_balance += amount


async def _transfer_shares(
    session: AsyncSession,
    ticker: str,
    from_account_id: str,
    to_account_id: str,
    quantity: int,
) -> None:
    """Transfer shares from seller to buyer.

    Creates holding for buyer if needed.
    Deletes holding for seller if quantity reaches 0.

    Args:
        session: Database session
        ticker: Stock ticker
        from_account_id: Seller's account
        to_account_id: Buyer's account
        quantity: Number of shares to transfer
    """
    # Decrease seller's holding
    result = await session.execute(
        select(Holding).where(
            and_(
                Holding.account_id == from_account_id,
                Holding.ticker == ticker,
            )
        )
    )
    seller_holding = result.scalar_one()
    seller_holding.quantity -= quantity

    if seller_holding.quantity == 0:
        await session.delete(seller_holding)

    # Increase buyer's holding (create if needed)
    result = await session.execute(
        select(Holding).where(
            and_(
                Holding.account_id == to_account_id,
                Holding.ticker == ticker,
            )
        )
    )
    buyer_holding = result.scalar_one_or_none()

    if buyer_holding:
        buyer_holding.quantity += quantity
    else:
        new_holding = Holding(
            account_id=to_account_id,
            ticker=ticker,
            quantity=quantity,
        )
        session.add(new_holding)


def _update_order_after_fill(order: Order, filled_quantity: int) -> None:
    """Update order after a fill.

    Decrements remaining_quantity and updates status.

    Args:
        order: Order that was filled
        filled_quantity: Number of shares filled
    """
    order.remaining_quantity -= filled_quantity

    if order.remaining_quantity == 0:
        order.status = OrderStatus.FILLED
    else:
        order.status = OrderStatus.PARTIAL


def _cancel_unfilled_market_portion(order: Order) -> None:
    """Cancel the unfilled portion of a market order.

    Market orders follow IOC-like behavior - unfilled portion is cancelled.

    Args:
        order: Market order with unfilled quantity
    """
    order.status = OrderStatus.CANCELLED
