"""Pydantic schemas for trader endpoints."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


# ============================================================================
# Enums (matching model enums)
# ============================================================================


class OrderSide(str, Enum):
    """Buy or sell."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type."""

    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(str, Enum):
    """Order status."""

    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


# ============================================================================
# Order schemas
# ============================================================================


class OrderCreate(BaseModel):
    """Request schema for placing an order."""

    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker")
    side: OrderSide = Field(..., description="BUY or SELL")
    order_type: OrderType = Field(..., description="LIMIT or MARKET")
    quantity: int = Field(..., gt=0, description="Number of shares")
    price: Decimal | None = Field(
        default=None,
        gt=0,
        description="Limit price (required for LIMIT orders)",
    )


class OrderResponse(BaseModel):
    """Response schema for order data."""

    id: str
    ticker: str
    side: OrderSide
    order_type: OrderType
    price: Decimal | None
    quantity: int
    remaining_quantity: int
    status: OrderStatus
    timestamp: datetime

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    """Response for listing orders."""

    orders: list[OrderResponse] = Field(default_factory=list)


# ============================================================================
# Account schemas
# ============================================================================


class AccountInfoResponse(BaseModel):
    """Response schema for account info (trader view)."""

    account_id: str
    cash_balance: Decimal
    created_at: datetime


# ============================================================================
# Holding schemas
# ============================================================================


class HoldingResponse(BaseModel):
    """Response schema for a single holding."""

    ticker: str
    quantity: int

    model_config = {"from_attributes": True}


class HoldingsListResponse(BaseModel):
    """Response for listing holdings."""

    holdings: list[HoldingResponse] = Field(default_factory=list)
