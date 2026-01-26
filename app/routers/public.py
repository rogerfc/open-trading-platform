"""Public API endpoints - no authentication required."""

from datetime import datetime, UTC
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.public import (
    AllMarketDataResponse,
    CompanyDetailResponse,
    CompanyListResponse,
    CompanyPublic,
    MarketDataResponse,
    MarketDataSummary,
    OrderBookLevel,
    OrderBookResponse,
    TradePublic,
    TradesResponse,
)
from app.services import public as public_service

router = APIRouter()


@router.get(
    "/companies",
    response_model=CompanyListResponse,
    summary="List all companies",
)
async def list_companies(
    session: AsyncSession = Depends(get_session),
) -> CompanyListResponse:
    """Get all registered companies available for trading."""
    companies = await public_service.get_companies(session)
    return CompanyListResponse(
        companies=[CompanyPublic.model_validate(c) for c in companies]
    )


@router.get(
    "/companies/{ticker}",
    response_model=CompanyDetailResponse,
    summary="Get company details",
)
async def get_company(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> CompanyDetailResponse:
    """Get detailed information about a company including market data."""
    company = await public_service.get_company(session, ticker)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ticker '{ticker.upper()}' not found",
        )

    last_price = await public_service.get_last_price(session, ticker)
    volume_24h = await public_service.get_volume_24h(session, ticker)

    market_cap = None
    if last_price is not None:
        market_cap = last_price * company.float_shares

    return CompanyDetailResponse(
        ticker=company.ticker,
        name=company.name,
        total_shares=company.total_shares,
        float_shares=company.float_shares,
        last_price=last_price,
        market_cap=market_cap,
        volume_24h=volume_24h,
    )


@router.get(
    "/orderbook/{ticker}",
    response_model=OrderBookResponse,
    summary="Get order book",
)
async def get_order_book(
    ticker: str,
    depth: int = Query(default=10, ge=1, le=50, description="Number of price levels"),
    session: AsyncSession = Depends(get_session),
) -> OrderBookResponse:
    """Get the aggregated order book for a ticker.

    Returns bids (buy orders) and asks (sell orders) aggregated by price level.
    """
    company = await public_service.get_company(session, ticker)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ticker '{ticker.upper()}' not found",
        )

    bids, asks = await public_service.get_order_book(session, ticker, depth)
    last_price = await public_service.get_last_price(session, ticker)

    # Calculate spread
    spread = None
    if bids and asks:
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        spread = best_ask - best_bid

    return OrderBookResponse(
        ticker=company.ticker,
        timestamp=datetime.now(UTC).replace(tzinfo=None),
        bids=[OrderBookLevel(price=p, quantity=q) for p, q in bids],
        asks=[OrderBookLevel(price=p, quantity=q) for p, q in asks],
        spread=spread,
        last_price=last_price,
    )


@router.get(
    "/trades/{ticker}",
    response_model=TradesResponse,
    summary="Get recent trades",
)
async def get_trades(
    ticker: str,
    limit: int = Query(default=50, ge=1, le=500, description="Maximum trades to return"),
    session: AsyncSession = Depends(get_session),
) -> TradesResponse:
    """Get recent trades for a ticker.

    Trades are anonymous - buyer/seller information is not included.
    """
    company = await public_service.get_company(session, ticker)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ticker '{ticker.upper()}' not found",
        )

    trades = await public_service.get_recent_trades(session, ticker, limit)

    return TradesResponse(
        ticker=company.ticker,
        trades=[
            TradePublic(
                id=t.id,
                price=t.price,
                quantity=t.quantity,
                timestamp=t.timestamp,
            )
            for t in trades
        ],
    )


@router.get(
    "/market-data/{ticker}",
    response_model=MarketDataResponse,
    summary="Get market data for a ticker",
)
async def get_market_data(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> MarketDataResponse:
    """Get comprehensive market data for a single ticker."""
    company = await public_service.get_company(session, ticker)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ticker '{ticker.upper()}' not found",
        )

    last_price = await public_service.get_last_price(session, ticker)
    volume_24h = await public_service.get_volume_24h(session, ticker)
    opening_price, high_24h, low_24h = await public_service.get_price_stats_24h(
        session, ticker
    )

    # Calculate change
    change_24h = None
    change_percent_24h = None
    if last_price is not None and opening_price is not None:
        change_24h = last_price - opening_price
        if opening_price > 0:
            change_percent_24h = (change_24h / opening_price) * Decimal("100")

    # Calculate market cap
    market_cap = None
    if last_price is not None:
        market_cap = last_price * company.float_shares

    return MarketDataResponse(
        ticker=company.ticker,
        last_price=last_price,
        change_24h=change_24h,
        change_percent_24h=change_percent_24h,
        volume_24h=volume_24h,
        high_24h=high_24h,
        low_24h=low_24h,
        market_cap=market_cap,
        timestamp=datetime.now(UTC).replace(tzinfo=None),
    )


@router.get(
    "/market-data",
    response_model=AllMarketDataResponse,
    summary="Get market data for all tickers",
)
async def get_all_market_data(
    session: AsyncSession = Depends(get_session),
) -> AllMarketDataResponse:
    """Get summary market data for all tickers."""
    companies = await public_service.get_companies(session)

    markets = []
    for company in companies:
        last_price = await public_service.get_last_price(session, company.ticker)
        volume_24h = await public_service.get_volume_24h(session, company.ticker)
        opening_price, _, _ = await public_service.get_price_stats_24h(
            session, company.ticker
        )

        # Calculate change
        change_24h = None
        if last_price is not None and opening_price is not None:
            change_24h = last_price - opening_price

        # Calculate market cap
        market_cap = None
        if last_price is not None:
            market_cap = last_price * company.float_shares

        markets.append(
            MarketDataSummary(
                ticker=company.ticker,
                last_price=last_price,
                change_24h=change_24h,
                volume_24h=volume_24h,
                market_cap=market_cap,
            )
        )

    return AllMarketDataResponse(
        markets=markets,
        timestamp=datetime.now(UTC).replace(tzinfo=None),
    )
