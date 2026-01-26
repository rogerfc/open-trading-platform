"""
Company model - represents a publicly traded company.

Companies are static entities that define tradeable securities.
In Phase 1, company data (shares) is fixed after creation.
"""

from sqlalchemy import BigInteger, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Company(Base):
    """A publicly traded company on the exchange."""

    __tablename__ = "companies"

    # Primary key: unique ticker symbol (e.g., "TECH", "RETAIL")
    ticker: Mapped[str] = mapped_column(String, primary_key=True)

    # Company name
    name: Mapped[str] = mapped_column(String, nullable=False)

    # Total shares outstanding (100% of company ownership)
    total_shares: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Shares available for public trading (float)
    # The difference (total - float) represents privately held shares
    float_shares: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationships (defined for ORM navigation)
    holdings: Mapped[list["Holding"]] = relationship(back_populates="company")
    orders: Mapped[list["Order"]] = relationship(back_populates="company")
    trades: Mapped[list["Trade"]] = relationship(back_populates="company")

    # Database constraints
    __table_args__ = (
        CheckConstraint("total_shares > 0", name="check_total_shares_positive"),
        CheckConstraint("float_shares >= 0", name="check_float_shares_non_negative"),
        CheckConstraint(
            "float_shares <= total_shares", name="check_float_not_exceed_total"
        ),
    )

    def __repr__(self) -> str:
        return f"Company(ticker={self.ticker!r}, name={self.name!r})"


# Import at end to avoid circular imports
from app.models.holding import Holding
from app.models.order import Order
from app.models.trade import Trade
