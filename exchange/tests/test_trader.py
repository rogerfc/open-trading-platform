"""Tests for trader API endpoints."""

from decimal import Decimal

import pytest
import pytest_asyncio

from app.models import Account, Company, Holding, Order, OrderSide, OrderStatus, OrderType
from app.services.admin import generate_api_key, hash_api_key


# --- Test Data Fixtures ---


@pytest_asyncio.fixture
async def company(test_session):
    """Create a company for testing."""
    company = Company(
        ticker="TEST",
        name="Test Corp",
        total_shares=1000000,
        float_shares=500000,
    )
    test_session.add(company)
    await test_session.commit()
    await test_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def trader_account(test_session):
    """Create a trader account with API key."""
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)

    account = Account(
        id="trader1",
        api_key_hash=api_key_hash,
        cash_balance=Decimal("10000.00"),
    )
    test_session.add(account)
    await test_session.commit()
    await test_session.refresh(account)

    # Return both account and API key
    return account, api_key


@pytest_asyncio.fixture
async def trader_with_holding(test_session, company, trader_account):
    """Create a trader with a stock holding."""
    account, api_key = trader_account

    holding = Holding(
        account_id=account.id,
        ticker=company.ticker,
        quantity=100,
    )
    test_session.add(holding)
    await test_session.commit()
    await test_session.refresh(holding)

    return account, api_key, holding


# --- Authentication Tests ---


class TestAuthentication:
    """Tests for API key authentication."""

    @pytest.mark.asyncio
    async def test_missing_api_key(self, test_client):
        """Returns 401 when API key is missing."""
        response = await test_client.get("/account")
        assert response.status_code == 401
        assert "Missing API key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, test_client):
        """Returns 401 when API key is invalid."""
        response = await test_client.get(
            "/account",
            headers={"X-API-Key": "sk_invalid_key_12345"},
        )
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_valid_api_key(self, test_client, trader_account):
        """Returns 200 with valid API key."""
        account, api_key = trader_account
        response = await test_client.get(
            "/account",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200


# --- Account Endpoint Tests ---


class TestAccount:
    """Tests for GET /account."""

    @pytest.mark.asyncio
    async def test_get_account(self, test_client, trader_account):
        """Returns account info."""
        account, api_key = trader_account
        response = await test_client.get(
            "/account",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["account_id"] == "trader1"
        assert data["cash_balance"] == "10000.00"
        assert "created_at" in data


# --- Holdings Endpoint Tests ---


class TestHoldings:
    """Tests for GET /holdings."""

    @pytest.mark.asyncio
    async def test_empty_holdings(self, test_client, trader_account):
        """Returns empty list when no holdings."""
        account, api_key = trader_account
        response = await test_client.get(
            "/holdings",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["holdings"] == []

    @pytest.mark.asyncio
    async def test_list_holdings(self, test_client, trader_with_holding):
        """Returns holdings list."""
        account, api_key, holding = trader_with_holding
        response = await test_client.get(
            "/holdings",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["ticker"] == "TEST"
        assert data["holdings"][0]["quantity"] == 100


# --- Order Endpoint Tests ---


class TestPlaceOrder:
    """Tests for POST /orders."""

    @pytest.mark.asyncio
    async def test_place_limit_buy_order(self, test_client, company, trader_account):
        """Can place a limit buy order."""
        account, api_key = trader_account
        response = await test_client.post(
            "/orders",
            headers={"X-API-Key": api_key},
            json={
                "ticker": "TEST",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 10,
                "price": "100.00",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ticker"] == "TEST"
        assert data["side"] == "BUY"
        assert data["order_type"] == "LIMIT"
        assert data["quantity"] == 10
        assert data["remaining_quantity"] == 10
        assert data["price"] == "100.00"
        assert data["status"] == "OPEN"

    @pytest.mark.asyncio
    async def test_place_limit_sell_order(self, test_client, trader_with_holding):
        """Can place a limit sell order with sufficient shares."""
        account, api_key, holding = trader_with_holding
        response = await test_client.post(
            "/orders",
            headers={"X-API-Key": api_key},
            json={
                "ticker": "TEST",
                "side": "SELL",
                "order_type": "LIMIT",
                "quantity": 50,
                "price": "150.00",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["side"] == "SELL"
        assert data["quantity"] == 50
        assert data["status"] == "OPEN"

    @pytest.mark.asyncio
    async def test_place_market_buy_order(self, test_client, company, trader_account):
        """Can place a market buy order."""
        account, api_key = trader_account
        response = await test_client.post(
            "/orders",
            headers={"X-API-Key": api_key},
            json={
                "ticker": "TEST",
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 10,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["order_type"] == "MARKET"
        assert data["price"] is None

    @pytest.mark.asyncio
    async def test_limit_order_requires_price(self, test_client, company, trader_account):
        """Limit order without price returns 400."""
        account, api_key = trader_account
        response = await test_client.post(
            "/orders",
            headers={"X-API-Key": api_key},
            json={
                "ticker": "TEST",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 10,
            },
        )
        assert response.status_code == 400
        assert "require a price" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_unknown_ticker(self, test_client, trader_account):
        """Unknown ticker returns 400."""
        account, api_key = trader_account
        response = await test_client.post(
            "/orders",
            headers={"X-API-Key": api_key},
            json={
                "ticker": "UNKNOWN",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 10,
                "price": "100.00",
            },
        )
        assert response.status_code == 400
        assert "Unknown ticker" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_insufficient_shares(self, test_client, company, trader_account):
        """Sell order without sufficient shares returns 400."""
        account, api_key = trader_account
        response = await test_client.post(
            "/orders",
            headers={"X-API-Key": api_key},
            json={
                "ticker": "TEST",
                "side": "SELL",
                "order_type": "LIMIT",
                "quantity": 100,
                "price": "100.00",
            },
        )
        assert response.status_code == 400
        assert "Insufficient shares" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_insufficient_funds(self, test_client, company, trader_account):
        """Buy order exceeding available funds returns 400."""
        account, api_key = trader_account
        # Account has 10000, try to buy 200 shares at 100 = 20000
        response = await test_client.post(
            "/orders",
            headers={"X-API-Key": api_key},
            json={
                "ticker": "TEST",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 200,
                "price": "100.00",
            },
        )
        assert response.status_code == 400
        assert "Insufficient funds" in response.json()["detail"]


class TestListOrders:
    """Tests for GET /orders."""

    @pytest.mark.asyncio
    async def test_empty_orders(self, test_client, trader_account):
        """Returns empty list when no orders."""
        account, api_key = trader_account
        response = await test_client.get(
            "/orders",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["orders"] == []

    @pytest.mark.asyncio
    async def test_list_orders(self, test_client, company, trader_account):
        """Returns orders list."""
        account, api_key = trader_account

        # Place an order first
        await test_client.post(
            "/orders",
            headers={"X-API-Key": api_key},
            json={
                "ticker": "TEST",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 10,
                "price": "100.00",
            },
        )

        response = await test_client.get(
            "/orders",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["orders"]) == 1

    @pytest.mark.asyncio
    async def test_filter_by_status(self, test_client, company, trader_account):
        """Can filter orders by status."""
        account, api_key = trader_account

        # Place an order
        await test_client.post(
            "/orders",
            headers={"X-API-Key": api_key},
            json={
                "ticker": "TEST",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 10,
                "price": "100.00",
            },
        )

        # Filter for FILLED (should be empty)
        response = await test_client.get(
            "/orders?status=FILLED",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["orders"] == []

        # Filter for OPEN (should have 1)
        response = await test_client.get(
            "/orders?status=OPEN",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["orders"]) == 1


class TestGetOrder:
    """Tests for GET /orders/{order_id}."""

    @pytest.mark.asyncio
    async def test_get_order(self, test_client, company, trader_account):
        """Can get a specific order."""
        account, api_key = trader_account

        # Place an order first
        create_response = await test_client.post(
            "/orders",
            headers={"X-API-Key": api_key},
            json={
                "ticker": "TEST",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 10,
                "price": "100.00",
            },
        )
        order_id = create_response.json()["id"]

        response = await test_client.get(
            f"/orders/{order_id}",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == order_id

    @pytest.mark.asyncio
    async def test_order_not_found(self, test_client, trader_account):
        """Returns 404 for unknown order."""
        account, api_key = trader_account
        response = await test_client.get(
            "/orders/nonexistent-id",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 404


class TestCancelOrder:
    """Tests for DELETE /orders/{order_id}."""

    @pytest.mark.asyncio
    async def test_cancel_order(self, test_client, company, trader_account):
        """Can cancel an open order."""
        account, api_key = trader_account

        # Place an order first
        create_response = await test_client.post(
            "/orders",
            headers={"X-API-Key": api_key},
            json={
                "ticker": "TEST",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 10,
                "price": "100.00",
            },
        )
        order_id = create_response.json()["id"]

        response = await test_client.delete(
            f"/orders/{order_id}",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled(self, test_client, company, trader_account):
        """Cannot cancel an already cancelled order."""
        account, api_key = trader_account

        # Place and cancel an order
        create_response = await test_client.post(
            "/orders",
            headers={"X-API-Key": api_key},
            json={
                "ticker": "TEST",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 10,
                "price": "100.00",
            },
        )
        order_id = create_response.json()["id"]
        await test_client.delete(
            f"/orders/{order_id}",
            headers={"X-API-Key": api_key},
        )

        # Try to cancel again
        response = await test_client.delete(
            f"/orders/{order_id}",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 400
        assert "Cannot cancel" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, test_client, trader_account):
        """Returns 404 for unknown order."""
        account, api_key = trader_account
        response = await test_client.delete(
            "/orders/nonexistent-id",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 404
