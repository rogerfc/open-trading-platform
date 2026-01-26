"""
Holding model - tracks share ownership.

Represents who owns how many shares of each company.
Uses a composite primary key (account_id, ticker).
"""

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String
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

    # Relationships
    account: Mapped["Account"] = relationship(back_populates="holdings")
    company: Mapped["Company"] = relationship(back_populates="holdings")

    # Database constraints
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_quantity_positive"),
    )

    def __repr__(self) -> str:
        return f"Holding(account={self.account_id!r}, ticker={self.ticker!r}, quantity={self.quantity})"


# Import at end to avoid circular imports
from app.models.account import Account
from app.models.company import Company
