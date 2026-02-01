"""Tests for the portfolio service."""

from datetime import datetime, UTC
from decimal import Decimal

import pytest
import pytest_asyncio

from app.models import Account, Company, Holding, Trade
from app.services.admin import generate_api_key, hash_api_key
from app.services import portfolio


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
async def account(test_session):
    """Create a test account."""
    acc = Account(
        id="investor1",
        api_key_hash=hash_api_key(generate_api_key()),
        cash_balance=Decimal("5000.00"),
    )
    test_session.add(acc)
    await test_session.commit()
    return acc


class TestGetHoldingsWithPnL:
    """Tests for get_holdings_with_pnl."""

    @pytest.mark.asyncio
    async def test_empty_holdings(self, test_session, account):
        """Returns empty list when no holdings."""
        holdings = await portfolio.get_holdings_with_pnl(test_session, account.id)
        assert holdings == []

    @pytest.mark.asyncio
    async def test_holding_with_trade(self, test_session, account, company):
        """Returns holding with P/L when trade exists."""
        # Create holding: 100 shares at $50 cost basis
        holding = Holding(
            account_id=account.id,
            ticker=company.ticker,
            quantity=100,
            cost_basis=Decimal("5000.00"),
        )
        test_session.add(holding)

        # Create a trade to establish current price at $60
        trade = Trade(
            id="trade1",
            ticker=company.ticker,
            price=Decimal("60.00"),
            quantity=10,
            buyer_id="other",
            seller_id="other2",
            buy_order_id="order1",
            sell_order_id="order2",
        )
        test_session.add(trade)
        await test_session.commit()

        holdings = await portfolio.get_holdings_with_pnl(test_session, account.id)

        assert len(holdings) == 1
        h = holdings[0]
        assert h.ticker == "TECH"
        assert h.quantity == 100
        assert h.cost_basis == Decimal("5000.00")
        assert h.current_price == Decimal("60.00")
        assert h.current_value == Decimal("6000.00")  # 100 * 60
        assert h.unrealized_pnl == Decimal("1000.00")  # 6000 - 5000
        assert h.unrealized_pnl_percent == Decimal("20.00")  # 1000/5000 * 100

    @pytest.mark.asyncio
    async def test_holding_no_trades(self, test_session, account, company):
        """Returns holding with None values when no trades exist."""
        holding = Holding(
            account_id=account.id,
            ticker=company.ticker,
            quantity=100,
            cost_basis=Decimal("5000.00"),
        )
        test_session.add(holding)
        await test_session.commit()

        holdings = await portfolio.get_holdings_with_pnl(test_session, account.id)

        assert len(holdings) == 1
        h = holdings[0]
        assert h.ticker == "TECH"
        assert h.current_price is None
        assert h.current_value is None
        assert h.unrealized_pnl is None

    @pytest.mark.asyncio
    async def test_average_cost(self, test_session, account, company):
        """Average cost is calculated correctly."""
        holding = Holding(
            account_id=account.id,
            ticker=company.ticker,
            quantity=100,
            cost_basis=Decimal("7500.00"),  # $75 average
        )
        test_session.add(holding)
        await test_session.commit()

        holdings = await portfolio.get_holdings_with_pnl(test_session, account.id)
        assert holdings[0].average_cost == Decimal("75.00")


class TestGetPortfolioSummary:
    """Tests for get_portfolio_summary."""

    @pytest.mark.asyncio
    async def test_account_not_found(self, test_session):
        """Returns None for unknown account."""
        summary = await portfolio.get_portfolio_summary(test_session, "unknown")
        assert summary is None

    @pytest.mark.asyncio
    async def test_cash_only(self, test_session, account):
        """Returns summary for account with only cash."""
        summary = await portfolio.get_portfolio_summary(test_session, account.id)

        assert summary.account_id == account.id
        assert summary.cash_balance == Decimal("5000.00")
        assert summary.holdings_value == Decimal("0.00")
        assert summary.total_value == Decimal("5000.00")
        assert summary.total_cost_basis == Decimal("0.00")
        assert summary.unrealized_pnl == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_with_holdings(self, test_session, account, company):
        """Returns summary with holdings value."""
        # Create holding: 100 shares at $50 cost
        holding = Holding(
            account_id=account.id,
            ticker=company.ticker,
            quantity=100,
            cost_basis=Decimal("5000.00"),
        )
        test_session.add(holding)

        # Create trade at $75
        trade = Trade(
            id="trade1",
            ticker=company.ticker,
            price=Decimal("75.00"),
            quantity=10,
            buyer_id="other",
            seller_id="other2",
            buy_order_id="order1",
            sell_order_id="order2",
        )
        test_session.add(trade)
        await test_session.commit()

        summary = await portfolio.get_portfolio_summary(test_session, account.id)

        assert summary.cash_balance == Decimal("5000.00")
        assert summary.holdings_value == Decimal("7500.00")  # 100 * 75
        assert summary.total_value == Decimal("12500.00")  # 5000 + 7500
        assert summary.total_cost_basis == Decimal("5000.00")
        assert summary.unrealized_pnl == Decimal("2500.00")  # 7500 - 5000
        assert summary.unrealized_pnl_percent == Decimal("50.00")  # 2500/5000 * 100

    @pytest.mark.asyncio
    async def test_losing_position(self, test_session, account, company):
        """Correctly calculates negative P/L."""
        # Create holding: 100 shares at $100 cost
        holding = Holding(
            account_id=account.id,
            ticker=company.ticker,
            quantity=100,
            cost_basis=Decimal("10000.00"),
        )
        test_session.add(holding)

        # Price dropped to $80
        trade = Trade(
            id="trade1",
            ticker=company.ticker,
            price=Decimal("80.00"),
            quantity=10,
            buyer_id="other",
            seller_id="other2",
            buy_order_id="order1",
            sell_order_id="order2",
        )
        test_session.add(trade)
        await test_session.commit()

        summary = await portfolio.get_portfolio_summary(test_session, account.id)

        assert summary.holdings_value == Decimal("8000.00")  # 100 * 80
        assert summary.unrealized_pnl == Decimal("-2000.00")  # 8000 - 10000
        assert summary.unrealized_pnl_percent == Decimal("-20.00")
