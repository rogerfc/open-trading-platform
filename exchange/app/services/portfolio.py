"""Portfolio service - P/L calculations and portfolio analytics."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, Holding
from app.services.public import get_last_price


@dataclass
class HoldingWithPnL:
    """A holding with current value and profit/loss calculations."""

    ticker: str
    quantity: int
    cost_basis: Decimal
    current_price: Decimal | None
    current_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None

    @property
    def average_cost(self) -> Decimal | None:
        """Average cost per share."""
        if self.quantity == 0:
            return None
        return self.cost_basis / self.quantity


@dataclass
class PortfolioSummary:
    """Summary of an account's portfolio."""

    account_id: str
    cash_balance: Decimal
    holdings_value: Decimal | None  # None if prices unavailable
    total_value: Decimal | None  # cash + holdings
    total_cost_basis: Decimal
    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None


async def get_holdings_with_pnl(
    session: AsyncSession, account_id: str
) -> list[HoldingWithPnL]:
    """Get all holdings for an account with P/L calculations.

    Args:
        session: Database session
        account_id: Account ID

    Returns:
        List of holdings with current values and unrealized P/L
    """
    # Get all holdings for the account
    result = await session.execute(
        select(Holding).where(Holding.account_id == account_id)
    )
    holdings = result.scalars().all()

    holdings_with_pnl = []
    for holding in holdings:
        # Get current price
        current_price = await get_last_price(session, holding.ticker)

        # Calculate values
        if current_price is not None:
            current_value = current_price * holding.quantity
            unrealized_pnl = current_value - holding.cost_basis
            if holding.cost_basis > 0:
                unrealized_pnl_percent = (unrealized_pnl / holding.cost_basis) * 100
            else:
                unrealized_pnl_percent = None
        else:
            current_value = None
            unrealized_pnl = None
            unrealized_pnl_percent = None

        holdings_with_pnl.append(
            HoldingWithPnL(
                ticker=holding.ticker,
                quantity=holding.quantity,
                cost_basis=holding.cost_basis,
                current_price=current_price,
                current_value=current_value,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_percent=unrealized_pnl_percent,
            )
        )

    return holdings_with_pnl


async def get_portfolio_summary(
    session: AsyncSession, account_id: str
) -> PortfolioSummary | None:
    """Get portfolio summary for an account.

    Args:
        session: Database session
        account_id: Account ID

    Returns:
        Portfolio summary or None if account not found
    """
    # Get account
    result = await session.execute(
        select(Account).where(Account.id == account_id)
    )
    account = result.scalar_one_or_none()
    if account is None:
        return None

    # Get holdings with P/L
    holdings = await get_holdings_with_pnl(session, account_id)

    # Calculate totals
    total_cost_basis = sum(h.cost_basis for h in holdings)

    # Only calculate holdings_value if all prices are available
    if all(h.current_value is not None for h in holdings) and holdings:
        holdings_value = sum(h.current_value for h in holdings)  # type: ignore
        total_value = account.cash_balance + holdings_value
        unrealized_pnl = holdings_value - total_cost_basis
        if total_cost_basis > 0:
            unrealized_pnl_percent = (unrealized_pnl / total_cost_basis) * 100
        else:
            unrealized_pnl_percent = None
    elif not holdings:
        # No holdings - just cash
        holdings_value = Decimal("0.00")
        total_value = account.cash_balance
        unrealized_pnl = Decimal("0.00")
        unrealized_pnl_percent = Decimal("0.00")
    else:
        # Some prices unavailable
        holdings_value = None
        total_value = None
        unrealized_pnl = None
        unrealized_pnl_percent = None

    return PortfolioSummary(
        account_id=account_id,
        cash_balance=account.cash_balance,
        holdings_value=holdings_value,
        total_value=total_value,
        total_cost_basis=total_cost_basis,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_percent=unrealized_pnl_percent,
    )
