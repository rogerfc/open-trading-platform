"""Pydantic schemas for admin endpoints."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class CompanyCreate(BaseModel):
    """Request schema for creating a company."""

    ticker: str = Field(..., min_length=1, max_length=10, description="Unique ticker symbol")
    name: str = Field(..., min_length=1, max_length=255, description="Company name")
    total_shares: int = Field(..., gt=0, description="Total shares outstanding")
    float_shares: int = Field(..., ge=0, description="Shares available for trading")

    @field_validator("float_shares")
    @classmethod
    def float_not_exceed_total(cls, v: int, info) -> int:
        """Validate that float_shares doesn't exceed total_shares."""
        total = info.data.get("total_shares")
        if total is not None and v > total:
            raise ValueError("float_shares cannot exceed total_shares")
        return v


class CompanyResponse(BaseModel):
    """Response schema for company data."""

    ticker: str
    name: str
    total_shares: int
    float_shares: int

    model_config = {"from_attributes": True}


class AccountCreate(BaseModel):
    """Request schema for creating an account."""

    account_id: str = Field(..., min_length=1, max_length=255, description="Unique account ID")
    initial_cash: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        description="Initial cash balance",
    )


class AccountResponse(BaseModel):
    """Response schema for newly created account (includes API key)."""

    account_id: str
    cash_balance: Decimal
    api_key: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountListItem(BaseModel):
    """Response schema for account in list view."""

    account_id: str
    cash_balance: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}
