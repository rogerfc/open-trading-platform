"""Admin API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.admin import (
    AccountCreate,
    AccountListItem,
    AccountResponse,
    CompanyCreate,
    CompanyResponse,
)
from app.services import admin as admin_service

router = APIRouter()


@router.post(
    "/companies",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new company",
)
async def create_company(
    data: CompanyCreate,
    session: AsyncSession = Depends(get_session),
) -> CompanyResponse:
    """Register a new company for trading.

    - **ticker**: Unique symbol (will be uppercased)
    - **name**: Company name
    - **total_shares**: Total shares outstanding
    - **float_shares**: Shares available for public trading
    """
    try:
        company = await admin_service.create_company(session, data)
        return CompanyResponse.model_validate(company)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Company with ticker '{data.ticker.upper()}' already exists",
        )


@router.get(
    "/companies",
    response_model=list[CompanyResponse],
    summary="List all companies",
)
async def list_companies(
    session: AsyncSession = Depends(get_session),
) -> list[CompanyResponse]:
    """Get all registered companies."""
    companies = await admin_service.list_companies(session)
    return [CompanyResponse.model_validate(c) for c in companies]


@router.post(
    "/accounts",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new trader account",
)
async def create_account(
    data: AccountCreate,
    session: AsyncSession = Depends(get_session),
) -> AccountResponse:
    """Register a new trader account.

    Returns the account details including the API key.
    **Store the API key securely - it cannot be retrieved later.**

    - **account_id**: Unique account identifier
    - **initial_cash**: Starting cash balance (default: 0.00)
    """
    try:
        account, api_key = await admin_service.create_account(session, data)
        return AccountResponse(
            account_id=account.id,
            cash_balance=account.cash_balance,
            api_key=api_key,
            created_at=account.created_at,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account with ID '{data.account_id}' already exists",
        )


@router.get(
    "/accounts",
    response_model=list[AccountListItem],
    summary="List all accounts",
)
async def list_accounts(
    session: AsyncSession = Depends(get_session),
) -> list[AccountListItem]:
    """Get all trader accounts."""
    accounts = await admin_service.list_accounts(session)
    return [
        AccountListItem(
            account_id=a.id,
            cash_balance=a.cash_balance,
            created_at=a.created_at,
        )
        for a in accounts
    ]
