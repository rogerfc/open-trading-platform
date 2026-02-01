"""Tests for portfolio API endpoints."""

from decimal import Decimal

import pytest
import pytest_asyncio

from app.models import Account, Company, Holding, Trade
from app.services.admin import generate_api_key, hash_api_key


@pytest_asyncio.fixture
async def company(test_session):
    """Create a test company."""
    c = Company(
        ticker="TECH",
        name="Tech Corp",
        total_shares=1000000,
        float_shares=500000,
    )
    test_session.add(c)
    await test_session.commit()
    return c


@pytest_asyncio.fixture
async def account_with_key(test_session):
    """Create account and return (account, api_key)."""
    api_key = generate_api_key()
    acc = Account(
        id="investor1",
        api_key_hash=hash_api_key(api_key),
        cash_balance=Decimal("10000.00"),
    )
    test_session.add(acc)
    await test_session.commit()
    return acc, api_key


class TestPortfolioSummary:
    """Tests for GET /api/v1/portfolio/summary."""

    @pytest.mark.asyncio
    async def test_unauthenticated(self, test_client):
        """Returns 401 without API key."""
        response = await test_client.get("/api/v1/portfolio/summary")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cash_only(self, test_client, account_with_key):
        """Returns summary with just cash."""
        account, api_key = account_with_key

        response = await test_client.get(
            "/api/v1/portfolio/summary",
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["account_id"] == "investor1"
        assert data["cash_balance"] == "10000.00"
        assert data["holdings_value"] == "0.00"
        assert data["total_value"] == "10000.00"
        assert data["unrealized_pnl"] == "0.00"

    @pytest.mark.asyncio
    async def test_with_holdings(self, test_client, test_session, account_with_key, company):
        """Returns summary with holdings value."""
        account, api_key = account_with_key

        # Create holding
        holding = Holding(
            account_id=account.id,
            ticker=company.ticker,
            quantity=100,
            cost_basis=Decimal("5000.00"),
        )
        test_session.add(holding)

        # Create trade to set price at $75
        trade = Trade(
            id="trade1",
            ticker=company.ticker,
            price=Decimal("75.00"),
            quantity=10,
            buyer_id="other",
            seller_id="other2",
            buy_order_id="o1",
            sell_order_id="o2",
        )
        test_session.add(trade)
        await test_session.commit()

        response = await test_client.get(
            "/api/v1/portfolio/summary",
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["holdings_value"] == "7500.00"  # 100 * 75
        assert data["total_value"] == "17500.00"  # 10000 + 7500
        assert data["unrealized_pnl"] == "2500.00"  # 7500 - 5000


class TestPortfolioHoldings:
    """Tests for GET /api/v1/portfolio/holdings."""

    @pytest.mark.asyncio
    async def test_unauthenticated(self, test_client):
        """Returns 401 without API key."""
        response = await test_client.get("/api/v1/portfolio/holdings")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_holdings(self, test_client, account_with_key):
        """Returns empty list when no holdings."""
        account, api_key = account_with_key

        response = await test_client.get(
            "/api/v1/portfolio/holdings",
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["holdings"] == []

    @pytest.mark.asyncio
    async def test_holdings_with_pnl(self, test_client, test_session, account_with_key, company):
        """Returns holdings with P/L calculations."""
        account, api_key = account_with_key

        # Create holding: 100 shares at $50 average
        holding = Holding(
            account_id=account.id,
            ticker=company.ticker,
            quantity=100,
            cost_basis=Decimal("5000.00"),
        )
        test_session.add(holding)

        # Price is now $60
        trade = Trade(
            id="trade1",
            ticker=company.ticker,
            price=Decimal("60.00"),
            quantity=10,
            buyer_id="other",
            seller_id="other2",
            buy_order_id="o1",
            sell_order_id="o2",
        )
        test_session.add(trade)
        await test_session.commit()

        response = await test_client.get(
            "/api/v1/portfolio/holdings",
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["holdings"]) == 1

        h = data["holdings"][0]
        assert h["ticker"] == "TECH"
        assert h["quantity"] == 100
        assert h["cost_basis"] == "5000.00"
        assert h["average_cost"] == "50.00"
        assert h["current_price"] == "60.00"
        assert h["current_value"] == "6000.00"
        assert h["unrealized_pnl"] == "1000.00"
        assert float(h["unrealized_pnl_percent"]) == 20.0
