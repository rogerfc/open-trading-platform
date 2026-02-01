"""
Holding model - tracks share ownership.

Represents who owns how many shares of each company.
Uses a composite primary key (account_id, ticker).
"""

from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Holding(Base):
    """Share ownership record - links an account to shares of a company."""

    __tablename__ = "holdings"

    # Composite primary key: account + ticker
    account_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.id"), primary_key=True
    )
    ticker: Mapped[str] = mapped_column(
        String, ForeignKey("companies.ticker"), primary_key=True
    )

    # Number of shares owned (must be positive)
    # When quantity reaches 0, the row should be deleted
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Total cost basis for this holding (sum of purchase prices)
    # Used to calculate profit/loss when selling
    cost_basis: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )

    # Relationships
    account: Mapped["Account"] = relationship(back_populates="holdings")
    company: Mapped["Company"] = relationship(back_populates="holdings")

    # Database constraints
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_quantity_positive"),
    )

    def __repr__(self) -> str:
        return f"Holding(account={self.account_id!r}, ticker={self.ticker!r}, quantity={self.quantity}, cost_basis={self.cost_basis})"


# Import at end to avoid circular imports
from app.models.account import Account
from app.models.company import Company
