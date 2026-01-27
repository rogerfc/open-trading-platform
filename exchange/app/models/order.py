"""
Order model - the order book.

Contains all buy and sell orders waiting to be matched.
Orders follow price-time priority: best price first, then earliest timestamp.
"""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderSide(enum.Enum):
    """Buy or sell."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(enum.Enum):
    """Order type determines how price is handled."""

    LIMIT = "LIMIT"  # Execute at specified price or better
    MARKET = "MARKET"  # Execute immediately at best available price


class OrderStatus(enum.Enum):
    """Order lifecycle status."""

    OPEN = "OPEN"  # No fills yet, full quantity remaining
    PARTIAL = "PARTIAL"  # Some fills, but quantity remaining
    FILLED = "FILLED"  # Completely executed, no quantity remaining
    CANCELLED = "CANCELLED"  # Cancelled by user, no longer active


class Order(Base):
    """A buy or sell order in the order book."""

    __tablename__ = "orders"

    # Primary key: unique order identifier
    id: Mapped[str] = mapped_column(String, primary_key=True)

    # Who placed the order
    account_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.id"), nullable=False
    )

    # What is being traded
    ticker: Mapped[str] = mapped_column(
        String, ForeignKey("companies.ticker"), nullable=False
    )

    # Buy or sell
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide), nullable=False)

    # Limit or market order
    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType), nullable=False)

    # Limit price (NULL for market orders)
    # For LIMIT orders: BUY at this price or lower, SELL at this price or higher
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Original order size (shares)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Shares still to be filled (decreases as trades execute)
    remaining_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Order lifecycle status
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), nullable=False, default=OrderStatus.OPEN
    )

    # When order was placed (used for time priority in matching)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    account: Mapped["Account"] = relationship(back_populates="orders")
    company: Mapped["Company"] = relationship(back_populates="orders")

    # Trades where this was the buy order
    buy_trades: Mapped[list["Trade"]] = relationship(
        back_populates="buy_order", foreign_keys="Trade.buy_order_id"
    )
    # Trades where this was the sell order
    sell_trades: Mapped[list["Trade"]] = relationship(
        back_populates="sell_order", foreign_keys="Trade.sell_order_id"
    )

    # Database constraints
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_order_quantity_positive"),
        CheckConstraint(
            "remaining_quantity >= 0", name="check_remaining_quantity_non_negative"
        ),
        CheckConstraint(
            "remaining_quantity <= quantity",
            name="check_remaining_not_exceed_quantity",
        ),
        # Price must be positive for LIMIT orders, can be NULL for MARKET
        CheckConstraint(
            "price > 0 OR order_type = 'MARKET'",
            name="check_price_positive_for_limit",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"Order(id={self.id!r}, {self.side.value} {self.quantity} {self.ticker} "
            f"@ {self.price}, status={self.status.value})"
        )


# Import at end to avoid circular imports
from app.models.account import Account
from app.models.company import Company
from app.models.trade import Trade
