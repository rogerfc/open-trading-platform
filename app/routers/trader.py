"""Trader API endpoints - requires authentication."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_account
from app.database import get_session
from app.models import Account
from app.models import OrderStatus as ModelOrderStatus
from app.schemas.trader import (
    AccountInfoResponse,
    HoldingResponse,
    HoldingsListResponse,
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderStatus,
)
from app.services import trader as trader_service

router = APIRouter()


# ============================================================================
# Account endpoints
# ============================================================================


@router.get(
    "/account",
    response_model=AccountInfoResponse,
    summary="Get my account info",
)
async def get_account(
    account: Account = Depends(get_current_account),
) -> AccountInfoResponse:
    """Get the authenticated trader's account information."""
    return AccountInfoResponse(
        account_id=account.id,
        cash_balance=account.cash_balance,
        created_at=account.created_at,
    )


@router.get(
    "/holdings",
    response_model=HoldingsListResponse,
    summary="Get my holdings",
)
async def get_holdings(
    account: Account = Depends(get_current_account),
    session: AsyncSession = Depends(get_session),
) -> HoldingsListResponse:
    """Get all stock holdings for the authenticated trader."""
    holdings = await trader_service.get_account_holdings(session, account.id)
    return HoldingsListResponse(
        holdings=[HoldingResponse.model_validate(h) for h in holdings]
    )


# ============================================================================
# Order endpoints
# ============================================================================


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place an order",
)
async def place_order(
    data: OrderCreate,
    account: Account = Depends(get_current_account),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """Place a new buy or sell order.

    - **ticker**: Stock symbol to trade
    - **side**: BUY or SELL
    - **order_type**: LIMIT or MARKET
    - **quantity**: Number of shares
    - **price**: Required for LIMIT orders, ignored for MARKET orders
    """
    try:
        order = await trader_service.place_order(session, account, data)
        return OrderResponse(
            id=order.id,
            ticker=order.ticker,
            side=order.side.value,
            order_type=order.order_type.value,
            price=order.price,
            quantity=order.quantity,
            remaining_quantity=order.remaining_quantity,
            status=order.status.value,
            timestamp=order.timestamp,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/orders",
    response_model=OrderListResponse,
    summary="List my orders",
)
async def list_orders(
    status_filter: OrderStatus | None = Query(
        default=None, alias="status", description="Filter by order status"
    ),
    ticker: str | None = Query(default=None, description="Filter by ticker"),
    account: Account = Depends(get_current_account),
    session: AsyncSession = Depends(get_session),
) -> OrderListResponse:
    """Get all orders for the authenticated trader.

    Optionally filter by status (OPEN, PARTIAL, FILLED, CANCELLED) or ticker.
    """
    # Convert schema enum to model enum if provided
    model_status = None
    if status_filter:
        model_status = ModelOrderStatus[status_filter.value]

    orders = await trader_service.get_account_orders(
        session, account.id, status=model_status, ticker=ticker
    )

    return OrderListResponse(
        orders=[
            OrderResponse(
                id=o.id,
                ticker=o.ticker,
                side=o.side.value,
                order_type=o.order_type.value,
                price=o.price,
                quantity=o.quantity,
                remaining_quantity=o.remaining_quantity,
                status=o.status.value,
                timestamp=o.timestamp,
            )
            for o in orders
        ]
    )


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Get order details",
)
async def get_order(
    order_id: str,
    account: Account = Depends(get_current_account),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """Get details of a specific order."""
    order = await trader_service.get_order(session, order_id, account.id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found",
        )

    return OrderResponse(
        id=order.id,
        ticker=order.ticker,
        side=order.side.value,
        order_type=order.order_type.value,
        price=order.price,
        quantity=order.quantity,
        remaining_quantity=order.remaining_quantity,
        status=order.status.value,
        timestamp=order.timestamp,
    )


@router.delete(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Cancel an order",
)
async def cancel_order(
    order_id: str,
    account: Account = Depends(get_current_account),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """Cancel an open or partially filled order."""
    order = await trader_service.get_order(session, order_id, account.id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found",
        )

    try:
        order = await trader_service.cancel_order(session, order)
        return OrderResponse(
            id=order.id,
            ticker=order.ticker,
            side=order.side.value,
            order_type=order.order_type.value,
            price=order.price,
            quantity=order.quantity,
            remaining_quantity=order.remaining_quantity,
            status=order.status.value,
            timestamp=order.timestamp,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
