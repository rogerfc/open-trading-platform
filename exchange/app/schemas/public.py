"""Pydantic schemas for public endpoints."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ============================================================================
# Company schemas
# ============================================================================


class CompanyPublic(BaseModel):
    """Public company info."""

    ticker: str
    name: str
    total_shares: int
    float_shares: int
    ipo_price: Decimal

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    """Response for listing all companies."""

    companies: list[CompanyPublic]


class CompanyDetailResponse(BaseModel):
    """Detailed company info with market data."""

    ticker: str
    name: str
    total_shares: int
    float_shares: int
    ipo_price: Decimal
    last_price: Decimal | None = None
    market_cap: Decimal | None = None
    volume_24h: int = 0


# ============================================================================
# Order book schemas
# ============================================================================


class OrderBookLevel(BaseModel):
    """A price level in the order book (aggregated)."""

    price: Decimal
    quantity: int


class OrderBookResponse(BaseModel):
    """Aggregated order book for a ticker."""

    ticker: str
    timestamp: datetime
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)
    spread: Decimal | None = None
    last_price: Decimal | None = None


# ============================================================================
# Trade schemas
# ============================================================================


class TradePublic(BaseModel):
    """Public trade info (anonymous - no buyer/seller)."""

    id: str
    price: Decimal
    quantity: int
    timestamp: datetime


class TradesResponse(BaseModel):
    """Response for listing trades."""

    ticker: str
    trades: list[TradePublic] = Field(default_factory=list)


# ============================================================================
# Market data schemas
# ============================================================================


class MarketDataResponse(BaseModel):
    """Full market data for a single ticker."""

    ticker: str
    last_price: Decimal | None = None
    change_24h: Decimal | None = None
    change_percent_24h: Decimal | None = None
    volume_24h: int = 0
    high_24h: Decimal | None = None
    low_24h: Decimal | None = None
    market_cap: Decimal | None = None
    timestamp: datetime


class MarketDataSummary(BaseModel):
    """Summary market data for list view."""

    ticker: str
    last_price: Decimal | None = None
    change_24h: Decimal | None = None
    volume_24h: int = 0
    market_cap: Decimal | None = None


class AllMarketDataResponse(BaseModel):
    """Response for all market data."""

    markets: list[MarketDataSummary] = Field(default_factory=list)
    timestamp: datetime
