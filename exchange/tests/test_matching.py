"""Tests for the order matching engine.

Tests price-time priority matching, settlement, and edge cases.
"""

from datetime import datetime, timedelta, UTC
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import (
    Account,
    Company,
    Holding,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Trade,
)
from app.services import matching
from app.services.admin import generate_api_key, hash_api_key


# ============================================================================
# Fixtures
# ============================================================================


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
    await test_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def buyer(test_session):
    """Create a buyer account with cash."""
    acc = Account(
        id="buyer",
        api_key_hash=hash_api_key(generate_api_key()),
        cash_balance=Decimal("100000.00"),
    )
    test_session.add(acc)
    await test_session.commit()
    await test_session.refresh(acc)
    return acc


@pytest_asyncio.fixture
async def seller(test_session, company):
    """Create a seller account with shares."""
    acc = Account(
        id="seller",
        api_key_hash=hash_api_key(generate_api_key()),
        cash_balance=Decimal("10000.00"),
    )
    test_session.add(acc)
    await test_session.flush()

    # Give seller some shares
    holding = Holding(
        account_id=acc.id,
        ticker=company.ticker,
        quantity=1000,
    )
    test_session.add(holding)
    await test_session.commit()
    await test_session.refresh(acc)
    return acc


@pytest_asyncio.fixture
async def seller2(test_session, company):
    """Create a second seller with shares."""
    acc = Account(
        id="seller2",
        api_key_hash=hash_api_key(generate_api_key()),
        cash_balance=Decimal("5000.00"),
    )
    test_session.add(acc)
    await test_session.flush()

    holding = Holding(
        account_id=acc.id,
        ticker=company.ticker,
        quantity=500,
    )
    test_session.add(holding)
    await test_session.commit()
    await test_session.refresh(acc)
    return acc


# ============================================================================
# Price Priority Tests
# ============================================================================


class TestPricePriority:
    """Tests for price priority in matching."""

    @pytest.mark.asyncio
    async def test_lowest_ask_matched_first(self, test_session, company, buyer, seller, seller2):
        """Lower-priced sell orders are matched before higher-priced."""
        # Create two sell orders at different prices
        sell_high = Order(
            id="sell_high",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("55.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        sell_low = Order(
            id="sell_low",
            account_id=seller2.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add_all([sell_high, sell_low])
        await test_session.commit()

        # Create buy order that could match either
        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("60.00"),  # Willing to pay up to 60
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        # Match
        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        # Should match the lower-priced sell
        assert len(trades) == 1
        assert trades[0].price == Decimal("50.00")
        assert trades[0].sell_order_id == "sell_low"

    @pytest.mark.asyncio
    async def test_highest_bid_matched_first(self, test_session, company, buyer, seller):
        """Higher-priced buy orders are matched before lower-priced."""
        # Create a second buyer
        buyer2 = Account(
            id="buyer2",
            api_key_hash=hash_api_key(generate_api_key()),
            cash_balance=Decimal("100000.00"),
        )
        test_session.add(buyer2)
        await test_session.flush()

        # Create two buy orders at different prices
        buy_low = Order(
            id="buy_low",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("45.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        buy_high = Order(
            id="buy_high",
            account_id=buyer2.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add_all([buy_low, buy_high])
        await test_session.commit()

        # Create sell order that could match either
        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("40.00"),  # Willing to accept at least 40
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.flush()

        # Match
        trades = await matching.match_order(test_session, sell_order)
        await test_session.commit()

        # Should match the higher-priced buy
        assert len(trades) == 1
        assert trades[0].price == Decimal("50.00")
        assert trades[0].buy_order_id == "buy_high"


# ============================================================================
# Time Priority Tests
# ============================================================================


class TestTimePriority:
    """Tests for time priority when prices are equal."""

    @pytest.mark.asyncio
    async def test_earlier_order_matched_first(self, test_session, company, buyer, seller, seller2):
        """At same price, earlier orders are matched first (FIFO)."""
        now = datetime.now(UTC)

        # Create two sell orders at same price, different times
        sell_early = Order(
            id="sell_early",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=now - timedelta(minutes=5),
        )
        sell_late = Order(
            id="sell_late",
            account_id=seller2.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=now,
        )
        test_session.add_all([sell_early, sell_late])
        await test_session.commit()

        # Create buy order
        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=now,
        )
        test_session.add(buy_order)
        await test_session.flush()

        # Match
        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        # Should match the earlier sell
        assert len(trades) == 1
        assert trades[0].sell_order_id == "sell_early"


# ============================================================================
# Limit Order Tests
# ============================================================================


class TestLimitOrders:
    """Tests for LIMIT order matching."""

    @pytest.mark.asyncio
    async def test_limit_buy_matches_at_or_below(self, test_session, company, buyer, seller):
        """LIMIT BUY matches sells at or below limit price."""
        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("48.00"),  # Below buyer's limit
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        assert len(trades) == 1
        assert trades[0].price == Decimal("48.00")  # Executes at resting price

    @pytest.mark.asyncio
    async def test_limit_buy_no_match_above_limit(self, test_session, company, buyer, seller):
        """LIMIT BUY does not match sells above limit price."""
        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("55.00"),  # Above buyer's limit
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        assert len(trades) == 0
        assert buy_order.status == OrderStatus.OPEN
        assert buy_order.remaining_quantity == 100

    @pytest.mark.asyncio
    async def test_limit_sell_matches_at_or_above(self, test_session, company, buyer, seller):
        """LIMIT SELL matches buys at or above limit price."""
        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("52.00"),  # Above seller's limit
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.commit()

        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, sell_order)
        await test_session.commit()

        assert len(trades) == 1
        assert trades[0].price == Decimal("52.00")  # Executes at resting price

    @pytest.mark.asyncio
    async def test_price_improvement(self, test_session, company, buyer, seller):
        """Execution price is resting order's price (price improvement)."""
        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("45.00"),  # Willing to sell at 45
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),  # Willing to pay up to 50
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        # Buyer gets price improvement: pays 45, not 50
        assert trades[0].price == Decimal("45.00")


# ============================================================================
# Market Order Tests
# ============================================================================


class TestMarketOrders:
    """Tests for MARKET order matching."""

    @pytest.mark.asyncio
    async def test_market_buy_matches_any_ask(self, test_session, company, buyer, seller):
        """MARKET BUY matches any available sell."""
        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("100.00"),  # High price
            quantity=50,
            remaining_quantity=50,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=None,
            quantity=50,
            remaining_quantity=50,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        assert len(trades) == 1
        assert trades[0].price == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_market_sell_matches_any_bid(self, test_session, company, buyer, seller):
        """MARKET SELL matches any available buy."""
        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("10.00"),  # Low price
            quantity=50,
            remaining_quantity=50,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.commit()

        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            price=None,
            quantity=50,
            remaining_quantity=50,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, sell_order)
        await test_session.commit()

        assert len(trades) == 1
        assert trades[0].price == Decimal("10.00")

    @pytest.mark.asyncio
    async def test_market_order_unfilled_cancelled(self, test_session, company, buyer, seller):
        """Unfilled portion of market order is cancelled (IOC)."""
        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=30,  # Only 30 available
            remaining_quantity=30,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=None,
            quantity=100,  # Wants 100
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        # Should fill 30, cancel remaining 70
        assert len(trades) == 1
        assert trades[0].quantity == 30
        assert buy_order.remaining_quantity == 70
        assert buy_order.status == OrderStatus.CANCELLED


# ============================================================================
# Self-Trade Prevention Tests
# ============================================================================


class TestSelfTradePrevention:
    """Tests for self-trade prevention."""

    @pytest.mark.asyncio
    async def test_own_orders_skipped(self, test_session, company, buyer):
        """Orders from same account are not matched."""
        # Give buyer some shares to sell
        holding = Holding(
            account_id=buyer.id,
            ticker=company.ticker,
            quantity=100,
        )
        test_session.add(holding)
        await test_session.flush()

        # Buyer places a sell order
        sell_order = Order(
            id="sell",
            account_id=buyer.id,  # Same account
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        # Buyer places a buy order that would match
        buy_order = Order(
            id="buy",
            account_id=buyer.id,  # Same account
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        # Should not match own order
        assert len(trades) == 0
        assert buy_order.status == OrderStatus.OPEN


# ============================================================================
# Partial Fill Tests
# ============================================================================


class TestPartialFills:
    """Tests for partial fills."""

    @pytest.mark.asyncio
    async def test_partial_fill_updates_status(self, test_session, company, buyer, seller):
        """Partial fill changes status to PARTIAL."""
        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=50,  # Only 50 available
            remaining_quantity=50,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,  # Wants 100
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        assert len(trades) == 1
        assert buy_order.remaining_quantity == 50
        assert buy_order.status == OrderStatus.PARTIAL
        assert sell_order.remaining_quantity == 0
        assert sell_order.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_multiple_fills_until_complete(self, test_session, company, buyer, seller, seller2):
        """Order fills against multiple resting orders."""
        # Two sell orders
        sell1 = Order(
            id="sell1",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=30,
            remaining_quantity=30,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        sell2 = Order(
            id="sell2",
            account_id=seller2.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("51.00"),
            quantity=70,
            remaining_quantity=70,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add_all([sell1, sell2])
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("52.00"),  # Can match both
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        # Should create two trades
        assert len(trades) == 2
        assert trades[0].quantity == 30
        assert trades[0].price == Decimal("50.00")
        assert trades[1].quantity == 70
        assert trades[1].price == Decimal("51.00")
        assert buy_order.status == OrderStatus.FILLED
        assert buy_order.remaining_quantity == 0


# ============================================================================
# Settlement Tests
# ============================================================================


class TestSettlement:
    """Tests for cash and share settlement."""

    @pytest.mark.asyncio
    async def test_cash_transferred(self, test_session, company, buyer, seller):
        """Cash moves from buyer to seller."""
        initial_buyer_cash = buyer.cash_balance
        initial_seller_cash = seller.cash_balance

        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        await matching.match_order(test_session, buy_order)
        await test_session.commit()

        # Refresh accounts to see updates
        await test_session.refresh(buyer)
        await test_session.refresh(seller)

        expected_transfer = Decimal("50.00") * 100
        assert buyer.cash_balance == initial_buyer_cash - expected_transfer
        assert seller.cash_balance == initial_seller_cash + expected_transfer

    @pytest.mark.asyncio
    async def test_shares_transferred(self, test_session, company, buyer, seller):
        """Shares move from seller to buyer."""
        # Check initial seller holding
        result = await test_session.execute(
            select(Holding).where(
                Holding.account_id == seller.id,
                Holding.ticker == company.ticker,
            )
        )
        seller_holding = result.scalar_one()
        initial_seller_shares = seller_holding.quantity

        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        await matching.match_order(test_session, buy_order)
        await test_session.commit()

        # Check buyer now has shares
        result = await test_session.execute(
            select(Holding).where(
                Holding.account_id == buyer.id,
                Holding.ticker == company.ticker,
            )
        )
        buyer_holding = result.scalar_one()
        assert buyer_holding.quantity == 100

        # Check seller's shares decreased
        await test_session.refresh(seller_holding)
        assert seller_holding.quantity == initial_seller_shares - 100

    @pytest.mark.asyncio
    async def test_holding_created_for_buyer(self, test_session, company, buyer, seller):
        """Holding created if buyer had no shares."""
        # Verify buyer has no holding initially
        result = await test_session.execute(
            select(Holding).where(
                Holding.account_id == buyer.id,
                Holding.ticker == company.ticker,
            )
        )
        assert result.scalar_one_or_none() is None

        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=50,
            remaining_quantity=50,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=50,
            remaining_quantity=50,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        await matching.match_order(test_session, buy_order)
        await test_session.commit()

        # Now buyer should have a holding
        result = await test_session.execute(
            select(Holding).where(
                Holding.account_id == buyer.id,
                Holding.ticker == company.ticker,
            )
        )
        buyer_holding = result.scalar_one()
        assert buyer_holding.quantity == 50

    @pytest.mark.asyncio
    async def test_holding_deleted_when_zero(self, test_session, company, buyer, seller):
        """Holding deleted when seller sells all shares."""
        # Give seller exactly 100 shares
        result = await test_session.execute(
            select(Holding).where(
                Holding.account_id == seller.id,
                Holding.ticker == company.ticker,
            )
        )
        seller_holding = result.scalar_one()
        seller_holding.quantity = 100
        await test_session.commit()

        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,  # Sell all
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        await matching.match_order(test_session, buy_order)
        await test_session.commit()

        # Seller's holding should be deleted
        result = await test_session.execute(
            select(Holding).where(
                Holding.account_id == seller.id,
                Holding.ticker == company.ticker,
            )
        )
        assert result.scalar_one_or_none() is None


# ============================================================================
# Trade Record Tests
# ============================================================================


class TestTradeRecords:
    """Tests for Trade record creation."""

    @pytest.mark.asyncio
    async def test_trade_created_with_correct_data(self, test_session, company, buyer, seller):
        """Trade has correct price, quantity, parties."""
        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        assert len(trades) == 1
        trade = trades[0]
        assert trade.ticker == company.ticker
        assert trade.price == Decimal("50.00")
        assert trade.quantity == 100
        assert trade.buyer_id == buyer.id
        assert trade.seller_id == seller.id
        assert trade.buy_order_id == buy_order.id
        assert trade.sell_order_id == sell_order.id


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_no_matching_orders(self, test_session, company, buyer):
        """Order remains OPEN when no matches."""
        buy_order = Order(
            id="buy",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        assert len(trades) == 0
        assert buy_order.status == OrderStatus.OPEN
        assert buy_order.remaining_quantity == 100

    @pytest.mark.asyncio
    async def test_market_buy_insufficient_cash(self, test_session, company, seller):
        """Market buy stops when buyer lacks cash for match."""
        # Create buyer with limited cash
        poor_buyer = Account(
            id="poor_buyer",
            api_key_hash=hash_api_key(generate_api_key()),
            cash_balance=Decimal("100.00"),  # Only $100
        )
        test_session.add(poor_buyer)
        await test_session.flush()

        sell_order = Order(
            id="sell",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("50.00"),  # 50 * 100 = $5000 needed
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        buy_order = Order(
            id="buy",
            account_id=poor_buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=None,
            quantity=100,
            remaining_quantity=100,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        # No trade due to insufficient cash
        assert len(trades) == 0
        assert buy_order.status == OrderStatus.CANCELLED


class TestCostBasisTracking:
    """Tests for cost basis tracking during trades."""

    @pytest.mark.asyncio
    async def test_cost_basis_on_buy(self, test_session, company, seller, buyer):
        """Buyer's cost basis is set to purchase price * quantity."""
        # Seller fixture already has 1000 shares - update with cost basis
        seller_holding = await test_session.get(Holding, (seller.id, company.ticker))
        seller_holding.cost_basis = Decimal("50000.00")  # $50/share
        await test_session.commit()

        # Create sell order at $100
        sell_order = Order(
            id="sell_cb1",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("100.00"),
            quantity=50,
            remaining_quantity=50,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        # Buyer places buy order
        buy_order = Order(
            id="buy_cb1",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("100.00"),
            quantity=50,
            remaining_quantity=50,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        assert len(trades) == 1

        # Buyer's cost basis should be 50 shares * $100 = $5000
        buyer_holding = await test_session.get(Holding, (buyer.id, company.ticker))
        assert buyer_holding.quantity == 50
        assert buyer_holding.cost_basis == Decimal("5000.00")

    @pytest.mark.asyncio
    async def test_cost_basis_on_sell(self, test_session, company, seller, buyer):
        """Seller's cost basis is reduced proportionally when selling."""
        # Seller fixture has 1000 shares - set to 100 with cost basis $5000
        seller_holding = await test_session.get(Holding, (seller.id, company.ticker))
        seller_holding.quantity = 100
        seller_holding.cost_basis = Decimal("5000.00")  # $50/share avg
        await test_session.commit()

        # Create sell order for 40 shares at $100
        sell_order = Order(
            id="sell_cb2",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("100.00"),
            quantity=40,
            remaining_quantity=40,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        # Buyer places buy order
        buy_order = Order(
            id="buy_cb2",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("100.00"),
            quantity=40,
            remaining_quantity=40,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        assert len(trades) == 1

        # Seller's cost basis: sold 40 of 100 shares at avg cost $50
        # Cost basis reduces by 40 * $50 = $2000
        # Remaining: $5000 - $2000 = $3000
        await test_session.refresh(seller_holding)
        assert seller_holding.quantity == 60
        assert seller_holding.cost_basis == Decimal("3000.00")

    @pytest.mark.asyncio
    async def test_cost_basis_accumulates_on_multiple_buys(
        self, test_session, company, seller, buyer
    ):
        """Cost basis accumulates when buying more shares."""
        # Update seller to have 200 shares with cost basis
        seller_holding = await test_session.get(Holding, (seller.id, company.ticker))
        seller_holding.quantity = 200
        seller_holding.cost_basis = Decimal("10000.00")

        # Create buyer holding with 50 shares at cost basis $2500 ($50/share)
        buyer_holding = Holding(
            account_id=buyer.id,
            ticker=company.ticker,
            quantity=50,
            cost_basis=Decimal("2500.00"),
        )
        test_session.add(buyer_holding)
        await test_session.commit()

        # Create sell order at $100
        sell_order = Order(
            id="sell_cb3",
            account_id=seller.id,
            ticker=company.ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("100.00"),
            quantity=50,
            remaining_quantity=50,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(sell_order)
        await test_session.commit()

        # Buyer buys 50 more shares at $100
        buy_order = Order(
            id="buy_cb3",
            account_id=buyer.id,
            ticker=company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("100.00"),
            quantity=50,
            remaining_quantity=50,
            status=OrderStatus.OPEN,
            timestamp=datetime.now(UTC),
        )
        test_session.add(buy_order)
        await test_session.flush()

        trades = await matching.match_order(test_session, buy_order)
        await test_session.commit()

        assert len(trades) == 1

        # Buyer's cost basis: $2500 (original) + $5000 (new) = $7500
        await test_session.refresh(buyer_holding)
        assert buyer_holding.quantity == 100
        assert buyer_holding.cost_basis == Decimal("7500.00")
