"""Tests for public API endpoints."""

from datetime import datetime, timedelta, UTC
from decimal import Decimal

import pytest
import pytest_asyncio

from app.models import Company, Account, Order, OrderSide, OrderType, OrderStatus, Trade


# --- Test Data Fixtures ---


@pytest_asyncio.fixture
async def companies(test_session):
    """Create multiple companies for testing."""
    companies = [
        Company(ticker="TECH", name="TechCorp", total_shares=1000000, float_shares=500000),
        Company(ticker="BANK", name="First Bank", total_shares=500000, float_shares=300000),
    ]
    for c in companies:
        test_session.add(c)
    await test_session.commit()
    for c in companies:
        await test_session.refresh(c)
    return companies


@pytest_asyncio.fixture
async def accounts(test_session, companies):
    """Create accounts for testing."""
    from app.services.admin import generate_api_key, hash_api_key

    accounts = [
        Account(id="buyer1", api_key_hash=hash_api_key(generate_api_key()), cash_balance=Decimal("100000.00")),
        Account(id="seller1", api_key_hash=hash_api_key(generate_api_key()), cash_balance=Decimal("50000.00")),
    ]
    for a in accounts:
        test_session.add(a)
    await test_session.commit()
    for a in accounts:
        await test_session.refresh(a)
    return accounts


@pytest_asyncio.fixture
async def orders(test_session, companies, accounts):
    """Create orders for order book testing."""
    orders = [
        # Buy orders for TECH
        Order(
            id="buy1", account_id="buyer1", ticker="TECH",
            side=OrderSide.BUY, order_type=OrderType.LIMIT,
            price=Decimal("100.00"), quantity=100, remaining_quantity=100,
            status=OrderStatus.OPEN,
        ),
        Order(
            id="buy2", account_id="buyer1", ticker="TECH",
            side=OrderSide.BUY, order_type=OrderType.LIMIT,
            price=Decimal("99.50"), quantity=200, remaining_quantity=200,
            status=OrderStatus.OPEN,
        ),
        Order(
            id="buy3", account_id="buyer1", ticker="TECH",
            side=OrderSide.BUY, order_type=OrderType.LIMIT,
            price=Decimal("100.00"), quantity=50, remaining_quantity=50,
            status=OrderStatus.OPEN,
        ),
        # Sell orders for TECH
        Order(
            id="sell1", account_id="seller1", ticker="TECH",
            side=OrderSide.SELL, order_type=OrderType.LIMIT,
            price=Decimal("101.00"), quantity=150, remaining_quantity=150,
            status=OrderStatus.OPEN,
        ),
        Order(
            id="sell2", account_id="seller1", ticker="TECH",
            side=OrderSide.SELL, order_type=OrderType.LIMIT,
            price=Decimal("102.00"), quantity=100, remaining_quantity=100,
            status=OrderStatus.OPEN,
        ),
    ]
    for o in orders:
        test_session.add(o)
    await test_session.commit()
    return orders


@pytest_asyncio.fixture
async def trades(test_session, companies, accounts, orders):
    """Create trades for testing."""
    now = datetime.now(UTC).replace(tzinfo=None)
    trades = [
        Trade(
            id="trade1", ticker="TECH", price=Decimal("100.50"),
            quantity=50, buyer_id="buyer1", seller_id="seller1",
            buy_order_id="buy1", sell_order_id="sell1",
            timestamp=now - timedelta(hours=1),
        ),
        Trade(
            id="trade2", ticker="TECH", price=Decimal("101.00"),
            quantity=30, buyer_id="buyer1", seller_id="seller1",
            buy_order_id="buy1", sell_order_id="sell1",
            timestamp=now - timedelta(minutes=30),
        ),
        Trade(
            id="trade3", ticker="TECH", price=Decimal("100.75"),
            quantity=20, buyer_id="buyer1", seller_id="seller1",
            buy_order_id="buy1", sell_order_id="sell1",
            timestamp=now - timedelta(minutes=10),
        ),
    ]
    for t in trades:
        test_session.add(t)
    await test_session.commit()
    return trades


# --- Company Endpoints Tests ---


class TestListCompanies:
    """Tests for GET /companies."""

    @pytest.mark.asyncio
    async def test_empty_list(self, test_client):
        """Returns empty list when no companies exist."""
        response = await test_client.get("/api/v1/companies")
        assert response.status_code == 200
        data = response.json()
        assert data["companies"] == []

    @pytest.mark.asyncio
    async def test_list_companies(self, test_client, companies):
        """Returns all companies."""
        response = await test_client.get("/api/v1/companies")
        assert response.status_code == 200
        data = response.json()
        assert len(data["companies"]) == 2
        tickers = [c["ticker"] for c in data["companies"]]
        assert "TECH" in tickers
        assert "BANK" in tickers


class TestGetCompany:
    """Tests for GET /companies/{ticker}."""

    @pytest.mark.asyncio
    async def test_not_found(self, test_client):
        """Returns 404 for unknown ticker."""
        response = await test_client.get("/api/v1/companies/UNKNOWN")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_company(self, test_client, companies):
        """Returns company details."""
        response = await test_client.get("/api/v1/companies/TECH")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TECH"
        assert data["name"] == "TechCorp"
        assert data["total_shares"] == 1000000
        assert data["float_shares"] == 500000
        # No trades yet
        assert data["last_price"] is None
        assert data["market_cap"] is None
        assert data["volume_24h"] == 0

    @pytest.mark.asyncio
    async def test_get_company_with_trades(self, test_client, trades):
        """Returns company with market data from trades."""
        response = await test_client.get("/api/v1/companies/TECH")
        assert response.status_code == 200
        data = response.json()
        assert data["last_price"] == "100.75"  # Most recent trade
        assert data["volume_24h"] == 100  # 50 + 30 + 20
        # market_cap = last_price * float_shares = 100.75 * 500000
        assert data["market_cap"] == "50375000.00"

    @pytest.mark.asyncio
    async def test_case_insensitive(self, test_client, companies):
        """Ticker lookup is case-insensitive."""
        response = await test_client.get("/api/v1/companies/tech")
        assert response.status_code == 200
        assert response.json()["ticker"] == "TECH"


# --- Order Book Tests ---


class TestOrderBook:
    """Tests for GET /orderbook/{ticker}."""

    @pytest.mark.asyncio
    async def test_not_found(self, test_client):
        """Returns 404 for unknown ticker."""
        response = await test_client.get("/api/v1/orderbook/UNKNOWN")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_empty_order_book(self, test_client, companies):
        """Returns empty order book when no orders."""
        response = await test_client.get("/api/v1/orderbook/TECH")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TECH"
        assert data["bids"] == []
        assert data["asks"] == []
        assert data["spread"] is None
        assert data["last_price"] is None

    @pytest.mark.asyncio
    async def test_order_book_with_orders(self, test_client, orders):
        """Returns aggregated order book."""
        response = await test_client.get("/api/v1/orderbook/TECH")
        assert response.status_code == 200
        data = response.json()

        # Bids should be aggregated and sorted by price descending
        assert len(data["bids"]) == 2
        assert data["bids"][0]["price"] == "100.00"
        assert data["bids"][0]["quantity"] == 150  # 100 + 50 aggregated
        assert data["bids"][1]["price"] == "99.50"
        assert data["bids"][1]["quantity"] == 200

        # Asks should be sorted by price ascending
        assert len(data["asks"]) == 2
        assert data["asks"][0]["price"] == "101.00"
        assert data["asks"][0]["quantity"] == 150
        assert data["asks"][1]["price"] == "102.00"
        assert data["asks"][1]["quantity"] == 100

        # Spread = best ask - best bid = 101.00 - 100.00 = 1.00
        assert data["spread"] == "1.00"

    @pytest.mark.asyncio
    async def test_order_book_depth_limit(self, test_client, orders):
        """Respects depth parameter."""
        response = await test_client.get("/api/v1/orderbook/TECH?depth=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["bids"]) == 1
        assert len(data["asks"]) == 1


# --- Trades Tests ---


class TestTrades:
    """Tests for GET /trades/{ticker}."""

    @pytest.mark.asyncio
    async def test_not_found(self, test_client):
        """Returns 404 for unknown ticker."""
        response = await test_client.get("/api/v1/trades/UNKNOWN")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_empty_trades(self, test_client, companies):
        """Returns empty list when no trades."""
        response = await test_client.get("/api/v1/trades/TECH")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TECH"
        assert data["trades"] == []

    @pytest.mark.asyncio
    async def test_list_trades(self, test_client, trades):
        """Returns trades most recent first."""
        response = await test_client.get("/api/v1/trades/TECH")
        assert response.status_code == 200
        data = response.json()
        assert len(data["trades"]) == 3
        # Most recent first
        assert data["trades"][0]["id"] == "trade3"
        assert data["trades"][0]["price"] == "100.75"
        assert data["trades"][1]["id"] == "trade2"
        assert data["trades"][2]["id"] == "trade1"

    @pytest.mark.asyncio
    async def test_trades_limit(self, test_client, trades):
        """Respects limit parameter."""
        response = await test_client.get("/api/v1/trades/TECH?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["trades"]) == 2

    @pytest.mark.asyncio
    async def test_trades_anonymous(self, test_client, trades):
        """Trades don't include buyer/seller info."""
        response = await test_client.get("/api/v1/trades/TECH")
        data = response.json()
        trade = data["trades"][0]
        assert "buyer_id" not in trade
        assert "seller_id" not in trade
        assert "buy_order_id" not in trade
        assert "sell_order_id" not in trade


# --- Market Data Tests ---


class TestMarketData:
    """Tests for GET /market-data/{ticker}."""

    @pytest.mark.asyncio
    async def test_not_found(self, test_client):
        """Returns 404 for unknown ticker."""
        response = await test_client.get("/api/v1/market-data/UNKNOWN")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_market_data_no_trades(self, test_client, companies):
        """Returns null values when no trades."""
        response = await test_client.get("/api/v1/market-data/TECH")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TECH"
        assert data["last_price"] is None
        assert data["change_24h"] is None
        assert data["change_percent_24h"] is None
        assert data["volume_24h"] == 0
        assert data["high_24h"] is None
        assert data["low_24h"] is None
        assert data["market_cap"] is None

    @pytest.mark.asyncio
    async def test_market_data_with_trades(self, test_client, trades):
        """Returns computed market data."""
        response = await test_client.get("/api/v1/market-data/TECH")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TECH"
        assert data["last_price"] == "100.75"
        assert data["volume_24h"] == 100
        assert data["high_24h"] == "101.00"
        assert data["low_24h"] == "100.50"
        # Opening price was 100.50, last is 100.75
        # change = 100.75 - 100.50 = 0.25
        assert data["change_24h"] == "0.25"


class TestAllMarketData:
    """Tests for GET /market-data."""

    @pytest.mark.asyncio
    async def test_empty(self, test_client):
        """Returns empty list when no companies."""
        response = await test_client.get("/api/v1/market-data")
        assert response.status_code == 200
        data = response.json()
        assert data["markets"] == []

    @pytest.mark.asyncio
    async def test_all_market_data(self, test_client, companies):
        """Returns summary for all companies."""
        response = await test_client.get("/api/v1/market-data")
        assert response.status_code == 200
        data = response.json()
        assert len(data["markets"]) == 2
        tickers = [m["ticker"] for m in data["markets"]]
        assert "TECH" in tickers
        assert "BANK" in tickers

    @pytest.mark.asyncio
    async def test_all_market_data_with_trades(self, test_client, trades):
        """Returns market data for companies with trades."""
        response = await test_client.get("/api/v1/market-data")
        assert response.status_code == 200
        data = response.json()

        tech = next(m for m in data["markets"] if m["ticker"] == "TECH")
        assert tech["last_price"] == "100.75"
        assert tech["volume_24h"] == 100

        bank = next(m for m in data["markets"] if m["ticker"] == "BANK")
        assert bank["last_price"] is None
        assert bank["volume_24h"] == 0
