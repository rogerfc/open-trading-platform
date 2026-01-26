"""
Account model - represents a trader/participant in the exchange.

Accounts hold cash and can place orders. In Phase 1:
- Cash balance cannot go negative (no margin/credit)
- Cash cannot be added/withdrawn after account creation
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Account(Base):
    """A trader account on the exchange."""

    __tablename__ = "accounts"

    # Primary key: unique account identifier
    id: Mapped[str] = mapped_column(String, primary_key=True)

    # API key hash for authentication (SHA-256 hash of the API key)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Available cash for trading
    # Numeric(15,2) allows up to 999,999,999,999,999.99
    cash_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )

    # Account creation timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    holdings: Mapped[list["Holding"]] = relationship(back_populates="account")
    orders: Mapped[list["Order"]] = relationship(back_populates="account")

    # Trades where this account was the buyer
    buy_trades: Mapped[list["Trade"]] = relationship(
        back_populates="buyer", foreign_keys="Trade.buyer_id"
    )
    # Trades where this account was the seller
    sell_trades: Mapped[list["Trade"]] = relationship(
        back_populates="seller", foreign_keys="Trade.seller_id"
    )

    # Database constraints
    __table_args__ = (
        CheckConstraint("cash_balance >= 0", name="check_cash_non_negative"),
    )

    def __repr__(self) -> str:
        return f"Account(id={self.id!r}, cash_balance={self.cash_balance})"


# Import at end to avoid circular imports
from app.models.holding import Holding
from app.models.order import Order
from app.models.trade import Trade
