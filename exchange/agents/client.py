"""HTTP client for the stock exchange API."""

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from typing import Any

import httpx


@dataclass
class AccountInfo:
    """Account information."""

    account_id: str
    cash_balance: Decimal
    created_at: datetime


@dataclass
class Holding:
    """Stock holding."""

    ticker: str
    quantity: int


@dataclass
class Company:
    """Company information."""

    ticker: str
    name: str
    total_shares: int
    float_shares: int


@dataclass
class OrderBookLevel:
    """Single price level in order book."""

    price: Decimal
    quantity: int


@dataclass
class OrderBook:
    """Order book for a ticker."""

    ticker: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    spread: Decimal | None
    last_price: Decimal | None


@dataclass
class Trade:
    """A completed trade."""

    id: str
    price: Decimal
    quantity: int
    timestamp: datetime


@dataclass
class Order:
    """An order."""

    id: str
    ticker: str
    side: str  # BUY or SELL
    order_type: str  # LIMIT or MARKET
    price: Decimal | None
    quantity: int
    remaining_quantity: int
    status: str  # OPEN, PARTIAL, FILLED, CANCELLED
    timestamp: datetime


@dataclass
class MarketData:
    """Market data for a ticker."""

    ticker: str
    last_price: Decimal | None
    change_24h: Decimal | None
    volume_24h: int
    high_24h: Decimal | None
    low_24h: Decimal | None


class ExchangeClient:
    """Async HTTP client for the stock exchange API."""

    def __init__(self, base_url: str, api_key: str | None = None):
        """Initialize the client.

        Args:
            base_url: Base URL of the exchange API (e.g., http://localhost:8000)
            api_key: API key for authenticated endpoints (optional for public endpoints)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ExchangeClient":
        """Enter async context."""
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, creating one if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    def _headers(self, authenticated: bool = False) -> dict[str, str]:
        """Get headers for a request."""
        headers = {"Content-Type": "application/json"}
        if authenticated and self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    # --- Public Endpoints ---

    async def get_companies(self) -> list[Company]:
        """Get all companies."""
        resp = await self.client.get(f"{self.base_url}/companies")
        resp.raise_for_status()
        data = resp.json()
        return [
            Company(
                ticker=c["ticker"],
                name=c["name"],
                total_shares=c["total_shares"],
                float_shares=c["float_shares"],
            )
            for c in data["companies"]
        ]

    async def get_orderbook(self, ticker: str, depth: int = 10) -> OrderBook:
        """Get order book for a ticker."""
        resp = await self.client.get(
            f"{self.base_url}/orderbook/{ticker}", params={"depth": depth}
        )
        resp.raise_for_status()
        data = resp.json()
        return OrderBook(
            ticker=data["ticker"],
            bids=[
                OrderBookLevel(price=Decimal(b["price"]), quantity=b["quantity"])
                for b in data["bids"]
            ],
            asks=[
                OrderBookLevel(price=Decimal(a["price"]), quantity=a["quantity"])
                for a in data["asks"]
            ],
            spread=Decimal(data["spread"]) if data.get("spread") else None,
            last_price=Decimal(data["last_price"]) if data.get("last_price") else None,
        )

    async def get_trades(self, ticker: str, limit: int = 50) -> list[Trade]:
        """Get recent trades for a ticker."""
        resp = await self.client.get(
            f"{self.base_url}/trades/{ticker}", params={"limit": limit}
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            Trade(
                id=t["id"],
                price=Decimal(t["price"]),
                quantity=t["quantity"],
                timestamp=datetime.fromisoformat(t["timestamp"].replace("Z", "+00:00")),
            )
            for t in data["trades"]
        ]

    async def get_market_data(self, ticker: str | None = None) -> list[MarketData]:
        """Get market data for one or all tickers."""
        if ticker:
            resp = await self.client.get(f"{self.base_url}/market-data/{ticker}")
            resp.raise_for_status()
            data = resp.json()
            return [
                MarketData(
                    ticker=data["ticker"],
                    last_price=Decimal(data["last_price"]) if data.get("last_price") else None,
                    change_24h=Decimal(data["change_24h"]) if data.get("change_24h") else None,
                    volume_24h=data["volume_24h"],
                    high_24h=Decimal(data["high_24h"]) if data.get("high_24h") else None,
                    low_24h=Decimal(data["low_24h"]) if data.get("low_24h") else None,
                )
            ]
        else:
            resp = await self.client.get(f"{self.base_url}/market-data")
            resp.raise_for_status()
            data = resp.json()
            return [
                MarketData(
                    ticker=m["ticker"],
                    last_price=Decimal(m["last_price"]) if m.get("last_price") else None,
                    change_24h=Decimal(m["change_24h"]) if m.get("change_24h") else None,
                    volume_24h=m["volume_24h"],
                    high_24h=None,
                    low_24h=None,
                )
                for m in data["markets"]
            ]

    # --- Authenticated Endpoints ---

    async def get_account(self) -> AccountInfo:
        """Get account information."""
        resp = await self.client.get(
            f"{self.base_url}/account", headers=self._headers(authenticated=True)
        )
        resp.raise_for_status()
        data = resp.json()
        return AccountInfo(
            account_id=data["account_id"],
            cash_balance=Decimal(data["cash_balance"]),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
        )

    async def get_holdings(self) -> list[Holding]:
        """Get account holdings."""
        resp = await self.client.get(
            f"{self.base_url}/holdings", headers=self._headers(authenticated=True)
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            Holding(ticker=h["ticker"], quantity=h["quantity"]) for h in data["holdings"]
        ]

    async def get_orders(
        self, status: str | None = None, ticker: str | None = None
    ) -> list[Order]:
        """Get orders with optional filters."""
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        if ticker:
            params["ticker"] = ticker

        resp = await self.client.get(
            f"{self.base_url}/orders",
            headers=self._headers(authenticated=True),
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        return [self._parse_order(o) for o in data["orders"]]

    async def get_order(self, order_id: str) -> Order:
        """Get a specific order."""
        resp = await self.client.get(
            f"{self.base_url}/orders/{order_id}",
            headers=self._headers(authenticated=True),
        )
        resp.raise_for_status()
        return self._parse_order(resp.json())

    async def place_order(
        self,
        ticker: str,
        side: str,
        order_type: str,
        quantity: int,
        price: Decimal | None = None,
    ) -> Order:
        """Place an order.

        Args:
            ticker: Stock ticker symbol
            side: BUY or SELL
            order_type: LIMIT or MARKET
            quantity: Number of shares
            price: Price per share (required for LIMIT orders)

        Returns:
            The created order
        """
        payload: dict[str, Any] = {
            "ticker": ticker,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
        }
        if price is not None:
            payload["price"] = str(price)

        resp = await self.client.post(
            f"{self.base_url}/orders",
            headers=self._headers(authenticated=True),
            json=payload,
        )
        resp.raise_for_status()
        return self._parse_order(resp.json())

    async def cancel_order(self, order_id: str) -> Order:
        """Cancel an order."""
        resp = await self.client.delete(
            f"{self.base_url}/orders/{order_id}",
            headers=self._headers(authenticated=True),
        )
        resp.raise_for_status()
        return self._parse_order(resp.json())

    def _parse_order(self, data: dict[str, Any]) -> Order:
        """Parse order from API response."""
        return Order(
            id=data["id"],
            ticker=data["ticker"],
            side=data["side"],
            order_type=data["order_type"],
            price=Decimal(data["price"]) if data.get("price") else None,
            quantity=data["quantity"],
            remaining_quantity=data["remaining_quantity"],
            status=data["status"],
            timestamp=datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00")),
        )
