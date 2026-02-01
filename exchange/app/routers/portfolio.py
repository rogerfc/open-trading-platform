"""Portfolio API endpoints - requires authentication."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_account
from app.database import get_session
from app.models import Account
from app.schemas.portfolio import (
    HoldingWithPnLResponse,
    PortfolioHoldingsResponse,
    PortfolioSummaryResponse,
)
from app.services import portfolio as portfolio_service

router = APIRouter()


@router.get(
    "/portfolio/summary",
    response_model=PortfolioSummaryResponse,
    summary="Get portfolio summary",
)
async def get_portfolio_summary(
    account: Account = Depends(get_current_account),
    session: AsyncSession = Depends(get_session),
) -> PortfolioSummaryResponse:
    """Get a summary of your portfolio.

    Returns your cash balance, total holdings value, and unrealized profit/loss.

    **What the numbers mean:**
    - **cash_balance**: Money available to buy stocks
    - **holdings_value**: What your stocks are worth right now
    - **total_value**: Cash + holdings (your total wealth)
    - **total_cost_basis**: How much you paid for your stocks
    - **unrealized_pnl**: Profit or loss if you sold everything now
    """
    summary = await portfolio_service.get_portfolio_summary(session, account.id)

    if summary is None:
        raise HTTPException(status_code=404, detail="Account not found")

    return PortfolioSummaryResponse(
        account_id=summary.account_id,
        cash_balance=summary.cash_balance,
        holdings_value=summary.holdings_value,
        total_value=summary.total_value,
        total_cost_basis=summary.total_cost_basis,
        unrealized_pnl=summary.unrealized_pnl,
        unrealized_pnl_percent=summary.unrealized_pnl_percent,
        total_invested=summary.total_cost_basis,
    )


@router.get(
    "/portfolio/holdings",
    response_model=PortfolioHoldingsResponse,
    summary="Get holdings with P/L",
)
async def get_portfolio_holdings(
    account: Account = Depends(get_current_account),
    session: AsyncSession = Depends(get_session),
) -> PortfolioHoldingsResponse:
    """Get all your stock holdings with profit/loss for each.

    **What the numbers mean for each stock:**
    - **quantity**: How many shares you own
    - **cost_basis**: Total amount you paid
    - **average_cost**: What you paid per share on average
    - **current_price**: What the stock is selling for now
    - **current_value**: What your shares are worth now
    - **unrealized_pnl**: Your profit or loss (positive = profit!)
    """
    holdings = await portfolio_service.get_holdings_with_pnl(session, account.id)

    return PortfolioHoldingsResponse(
        holdings=[
            HoldingWithPnLResponse(
                ticker=h.ticker,
                quantity=h.quantity,
                cost_basis=h.cost_basis,
                average_cost=h.average_cost,
                current_price=h.current_price,
                current_value=h.current_value,
                unrealized_pnl=h.unrealized_pnl,
                unrealized_pnl_percent=h.unrealized_pnl_percent,
            )
            for h in holdings
        ]
    )
