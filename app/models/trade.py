"""
Trade model - historical record of executed trades.

Single source of truth for trade history. Trades are append-only
(never modified or deleted) and record the atomic transfer of
shares and cash between accounts.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Trade(Base):
    """A completed trade between two accounts."""

    __tablename__ = "trades"

    # Primary key: unique trade identifier
    id: Mapped[str] = mapped_column(String, primary_key=True)

    # What was traded
    ticker: Mapped[str] = mapped_column(
        String, ForeignKey("companies.ticker"), nullable=False
    )

    # Execution price (the price at which the trade occurred)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Number of shares traded
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Who bought (received shares, paid cash)
    buyer_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.id"), nullable=False
    )

    # Who sold (paid shares, received cash)
    seller_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.id"), nullable=False
    )

    # The orders that were matched to create this trade
    buy_order_id: Mapped[str] = mapped_column(
        String, ForeignKey("orders.id"), nullable=False
    )
    sell_order_id: Mapped[str] = mapped_column(
        String, ForeignKey("orders.id"), nullable=False
    )

    # When the trade executed
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="trades")
    buyer: Mapped["Account"] = relationship(
        back_populates="buy_trades", foreign_keys=[buyer_id]
    )
    seller: Mapped["Account"] = relationship(
        back_populates="sell_trades", foreign_keys=[seller_id]
    )
    buy_order: Mapped["Order"] = relationship(
        back_populates="buy_trades", foreign_keys=[buy_order_id]
    )
    sell_order: Mapped["Order"] = relationship(
        back_populates="sell_trades", foreign_keys=[sell_order_id]
    )

    # Database constraints
    __table_args__ = (
        CheckConstraint("price > 0", name="check_trade_price_positive"),
        CheckConstraint("quantity > 0", name="check_trade_quantity_positive"),
    )

    def __repr__(self) -> str:
        return (
            f"Trade(id={self.id!r}, {self.quantity} {self.ticker} @ {self.price}, "
            f"buyer={self.buyer_id!r}, seller={self.seller_id!r})"
        )


# Import at end to avoid circular imports
from app.models.account import Account
from app.models.company import Company
from app.models.order import Order
