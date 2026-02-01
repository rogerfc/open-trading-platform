"""Pydantic schemas for portfolio endpoints."""

from decimal import Decimal

from pydantic import BaseModel, Field


class HoldingWithPnLResponse(BaseModel):
    """Response schema for a holding with P/L calculations."""

    ticker: str = Field(..., description="Stock ticker symbol")
    quantity: int = Field(..., description="Number of shares owned")
    cost_basis: Decimal = Field(..., description="Total amount paid for shares")
    average_cost: Decimal | None = Field(None, description="Average cost per share")
    current_price: Decimal | None = Field(None, description="Current market price")
    current_value: Decimal | None = Field(None, description="Current market value")
    unrealized_pnl: Decimal | None = Field(
        None, description="Unrealized profit/loss (current value - cost basis)"
    )
    unrealized_pnl_percent: Decimal | None = Field(
        None, description="Unrealized P/L as percentage"
    )


class PortfolioHoldingsResponse(BaseModel):
    """Response for listing holdings with P/L."""

    holdings: list[HoldingWithPnLResponse] = Field(default_factory=list)


class PortfolioSummaryResponse(BaseModel):
    """Response schema for portfolio summary."""

    account_id: str = Field(..., description="Account identifier")
    cash_balance: Decimal = Field(..., description="Available cash")
    holdings_value: Decimal | None = Field(
        None, description="Total market value of holdings"
    )
    total_value: Decimal | None = Field(
        None, description="Total portfolio value (cash + holdings)"
    )
    total_cost_basis: Decimal = Field(
        ..., description="Total amount invested in holdings"
    )
    unrealized_pnl: Decimal | None = Field(
        None, description="Total unrealized profit/loss"
    )
    unrealized_pnl_percent: Decimal | None = Field(
        None, description="Total unrealized P/L as percentage"
    )

    # Beginner-friendly summary
    total_invested: Decimal = Field(
        ..., description="Total amount you've put into stocks"
    )

    @property
    def is_profitable(self) -> bool | None:
        """Whether the portfolio is currently profitable."""
        if self.unrealized_pnl is None:
            return None
        return self.unrealized_pnl > 0
