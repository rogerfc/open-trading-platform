"""
Tests for SQLAlchemy models.

Tests CRUD operations and database constraints for all models.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

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
from app.services.admin import generate_api_key, hash_api_key


# ============================================================================
# Company Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_company(test_session):
    """Test creating a company with valid data."""
    company = Company(
        ticker="TECH",
        name="Tech Corp",
        total_shares=10000000,
        float_shares=4000000,
    )
    test_session.add(company)
    await test_session.commit()

    result = await test_session.execute(
        select(Company).where(Company.ticker == "TECH")
    )
    saved = result.scalar_one()

    assert saved.ticker == "TECH"
    assert saved.name == "Tech Corp"
    assert saved.total_shares == 10000000
    assert saved.float_shares == 4000000


@pytest.mark.asyncio
async def test_company_ticker_primary_key(test_session):
    """Test that duplicate ticker fails (primary key constraint)."""
    company1 = Company(
        ticker="DUPE",
        name="First Company",
        total_shares=1000,
        float_shares=500,
    )
    test_session.add(company1)
    await test_session.commit()

    company2 = Company(
        ticker="DUPE",
        name="Second Company",
        total_shares=2000,
        float_shares=1000,
    )
    test_session.add(company2)

    with pytest.raises(IntegrityError):
        await test_session.commit()


@pytest.mark.asyncio
async def test_company_total_shares_positive(test_session):
    """Test that total_shares must be positive."""
    company = Company(
        ticker="BAD",
        name="Bad Company",
        total_shares=0,  # Invalid: must be > 0
        float_shares=0,
    )
    test_session.add(company)

    with pytest.raises(IntegrityError):
        await test_session.commit()


@pytest.mark.asyncio
async def test_company_float_shares_non_negative(test_session):
    """Test that float_shares must be non-negative."""
    company = Company(
        ticker="BAD",
        name="Bad Company",
        total_shares=1000,
        float_shares=-100,  # Invalid: must be >= 0
    )
    test_session.add(company)

    with pytest.raises(IntegrityError):
        await test_session.commit()


@pytest.mark.asyncio
async def test_company_float_not_exceed_total(test_session):
    """Test that float_shares cannot exceed total_shares."""
    company = Company(
        ticker="BAD",
        name="Bad Company",
        total_shares=1000,
        float_shares=2000,  # Invalid: float > total
    )
    test_session.add(company)

    with pytest.raises(IntegrityError):
        await test_session.commit()


# ============================================================================
# Account Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_account(test_session):
    """Test creating an account with valid data."""
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)

    account = Account(
        id="user123",
        api_key_hash=api_key_hash,
        cash_balance=Decimal("50000.00"),
    )
    test_session.add(account)
    await test_session.commit()

    result = await test_session.execute(
        select(Account).where(Account.id == "user123")
    )
    saved = result.scalar_one()

    assert saved.id == "user123"
    assert saved.cash_balance == Decimal("50000.00")
    assert saved.api_key_hash == api_key_hash


@pytest.mark.asyncio
async def test_account_default_cash_balance(test_session):
    """Test that cash_balance defaults to 0.00."""
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)

    account = Account(id="defaultuser", api_key_hash=api_key_hash)
    test_session.add(account)
    await test_session.commit()

    result = await test_session.execute(
        select(Account).where(Account.id == "defaultuser")
    )
    saved = result.scalar_one()

    assert saved.cash_balance == Decimal("0.00")


@pytest.mark.asyncio
async def test_account_cash_non_negative(test_session):
    """Test that cash_balance must be non-negative."""
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)

    account = Account(
        id="broke",
        api_key_hash=api_key_hash,
        cash_balance=Decimal("-100.00"),  # Invalid: must be >= 0
    )
    test_session.add(account)

    with pytest.raises(IntegrityError):
        await test_session.commit()


@pytest.mark.asyncio
async def test_account_created_at_auto(test_session):
    """Test that created_at is automatically set."""
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)

    account = Account(id="newuser", api_key_hash=api_key_hash, cash_balance=Decimal("100.00"))
    test_session.add(account)
    await test_session.commit()

    result = await test_session.execute(
        select(Account).where(Account.id == "newuser")
    )
    saved = result.scalar_one()

    assert saved.created_at is not None


# ============================================================================
# Holding Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_holding(test_session, sample_company, sample_account):
    """Test creating a holding with valid data."""
    holding = Holding(
        account_id=sample_account.id,
        ticker=sample_company.ticker,
        quantity=100,
    )
    test_session.add(holding)
    await test_session.commit()

    result = await test_session.execute(
        select(Holding).where(
            Holding.account_id == sample_account.id,
            Holding.ticker == sample_company.ticker,
        )
    )
    saved = result.scalar_one()

    assert saved.account_id == sample_account.id
    assert saved.ticker == sample_company.ticker
    assert saved.quantity == 100


@pytest.mark.asyncio
async def test_holding_composite_key(test_session, sample_company, sample_account):
    """Test that (account_id, ticker) is unique."""
    holding1 = Holding(
        account_id=sample_account.id,
        ticker=sample_company.ticker,
        quantity=100,
    )
    test_session.add(holding1)
    await test_session.commit()

    holding2 = Holding(
        account_id=sample_account.id,
        ticker=sample_company.ticker,
        quantity=200,  # Different quantity, same key
    )
    test_session.add(holding2)

    with pytest.raises(IntegrityError):
        await test_session.commit()


@pytest.mark.asyncio
async def test_holding_quantity_positive(test_session, sample_company, sample_account):
    """Test that quantity must be positive."""
    holding = Holding(
        account_id=sample_account.id,
        ticker=sample_company.ticker,
        quantity=0,  # Invalid: must be > 0
    )
    test_session.add(holding)

    with pytest.raises(IntegrityError):
        await test_session.commit()


# ============================================================================
# Order Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_limit_order(test_session, sample_company, sample_account):
    """Test creating a limit order with price."""
    order = Order(
        id="order1",
        account_id=sample_account.id,
        ticker=sample_company.ticker,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("50.00"),
        quantity=100,
        remaining_quantity=100,
        status=OrderStatus.OPEN,
    )
    test_session.add(order)
    await test_session.commit()

    result = await test_session.execute(
        select(Order).where(Order.id == "order1")
    )
    saved = result.scalar_one()

    assert saved.id == "order1"
    assert saved.side == OrderSide.BUY
    assert saved.order_type == OrderType.LIMIT
    assert saved.price == Decimal("50.00")
    assert saved.quantity == 100
    assert saved.remaining_quantity == 100
    assert saved.status == OrderStatus.OPEN


@pytest.mark.asyncio
async def test_create_market_order(test_session, sample_company, sample_account):
    """Test creating a market order without price."""
    order = Order(
        id="order2",
        account_id=sample_account.id,
        ticker=sample_company.ticker,
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        price=None,  # Market orders don't need price
        quantity=50,
        remaining_quantity=50,
        status=OrderStatus.OPEN,
    )
    test_session.add(order)
    await test_session.commit()

    result = await test_session.execute(
        select(Order).where(Order.id == "order2")
    )
    saved = result.scalar_one()

    assert saved.order_type == OrderType.MARKET
    assert saved.price is None


@pytest.mark.asyncio
async def test_order_quantity_positive(test_session, sample_company, sample_account):
    """Test that quantity must be positive."""
    order = Order(
        id="badorder",
        account_id=sample_account.id,
        ticker=sample_company.ticker,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("10.00"),
        quantity=0,  # Invalid: must be > 0
        remaining_quantity=0,
        status=OrderStatus.OPEN,
    )
    test_session.add(order)

    with pytest.raises(IntegrityError):
        await test_session.commit()


@pytest.mark.asyncio
async def test_order_remaining_quantity_valid(test_session, sample_company, sample_account):
    """Test that remaining_quantity cannot exceed quantity."""
    order = Order(
        id="badorder",
        account_id=sample_account.id,
        ticker=sample_company.ticker,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("10.00"),
        quantity=100,
        remaining_quantity=150,  # Invalid: remaining > quantity
        status=OrderStatus.OPEN,
    )
    test_session.add(order)

    with pytest.raises(IntegrityError):
        await test_session.commit()


@pytest.mark.asyncio
async def test_order_limit_requires_positive_price(test_session, sample_company, sample_account):
    """Test that limit orders require positive price."""
    order = Order(
        id="badorder",
        account_id=sample_account.id,
        ticker=sample_company.ticker,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("-10.00"),  # Invalid: must be > 0 for LIMIT
        quantity=100,
        remaining_quantity=100,
        status=OrderStatus.OPEN,
    )
    test_session.add(order)

    with pytest.raises(IntegrityError):
        await test_session.commit()


@pytest.mark.asyncio
async def test_order_status_transitions(test_session, sample_company, sample_account):
    """Test that all order status values work."""
    for i, status in enumerate(OrderStatus):
        order = Order(
            id=f"order_status_{i}",
            account_id=sample_account.id,
            ticker=sample_company.ticker,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("10.00"),
            quantity=100,
            remaining_quantity=100 if status != OrderStatus.FILLED else 0,
            status=status,
        )
        test_session.add(order)

    await test_session.commit()

    result = await test_session.execute(select(Order))
    orders = result.scalars().all()

    assert len(orders) == len(OrderStatus)


# ============================================================================
# Trade Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_trade(test_session, sample_company, sample_account, sample_account_2):
    """Test creating a trade with valid data."""
    # First create orders for the trade
    buy_order = Order(
        id="buy_order",
        account_id=sample_account.id,
        ticker=sample_company.ticker,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("50.00"),
        quantity=100,
        remaining_quantity=0,
        status=OrderStatus.FILLED,
    )
    sell_order = Order(
        id="sell_order",
        account_id=sample_account_2.id,
        ticker=sample_company.ticker,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        price=Decimal("50.00"),
        quantity=100,
        remaining_quantity=0,
        status=OrderStatus.FILLED,
    )
    test_session.add_all([buy_order, sell_order])
    await test_session.commit()

    # Create the trade
    trade = Trade(
        id="trade1",
        ticker=sample_company.ticker,
        price=Decimal("50.00"),
        quantity=100,
        buyer_id=sample_account.id,
        seller_id=sample_account_2.id,
        buy_order_id="buy_order",
        sell_order_id="sell_order",
    )
    test_session.add(trade)
    await test_session.commit()

    result = await test_session.execute(
        select(Trade).where(Trade.id == "trade1")
    )
    saved = result.scalar_one()

    assert saved.id == "trade1"
    assert saved.ticker == sample_company.ticker
    assert saved.price == Decimal("50.00")
    assert saved.quantity == 100
    assert saved.buyer_id == sample_account.id
    assert saved.seller_id == sample_account_2.id


@pytest.mark.asyncio
async def test_trade_price_positive(test_session, sample_company, sample_account, sample_account_2):
    """Test that trade price must be positive."""
    # Create orders first
    buy_order = Order(
        id="buy_order2",
        account_id=sample_account.id,
        ticker=sample_company.ticker,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100,
        remaining_quantity=0,
        status=OrderStatus.FILLED,
    )
    sell_order = Order(
        id="sell_order2",
        account_id=sample_account_2.id,
        ticker=sample_company.ticker,
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=100,
        remaining_quantity=0,
        status=OrderStatus.FILLED,
    )
    test_session.add_all([buy_order, sell_order])
    await test_session.commit()

    trade = Trade(
        id="badtrade",
        ticker=sample_company.ticker,
        price=Decimal("0.00"),  # Invalid: must be > 0
        quantity=100,
        buyer_id=sample_account.id,
        seller_id=sample_account_2.id,
        buy_order_id="buy_order2",
        sell_order_id="sell_order2",
    )
    test_session.add(trade)

    with pytest.raises(IntegrityError):
        await test_session.commit()


@pytest.mark.asyncio
async def test_trade_quantity_positive(test_session, sample_company, sample_account, sample_account_2):
    """Test that trade quantity must be positive."""
    # Create orders first
    buy_order = Order(
        id="buy_order3",
        account_id=sample_account.id,
        ticker=sample_company.ticker,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100,
        remaining_quantity=0,
        status=OrderStatus.FILLED,
    )
    sell_order = Order(
        id="sell_order3",
        account_id=sample_account_2.id,
        ticker=sample_company.ticker,
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=100,
        remaining_quantity=0,
        status=OrderStatus.FILLED,
    )
    test_session.add_all([buy_order, sell_order])
    await test_session.commit()

    trade = Trade(
        id="badtrade2",
        ticker=sample_company.ticker,
        price=Decimal("50.00"),
        quantity=0,  # Invalid: must be > 0
        buyer_id=sample_account.id,
        seller_id=sample_account_2.id,
        buy_order_id="buy_order3",
        sell_order_id="sell_order3",
    )
    test_session.add(trade)

    with pytest.raises(IntegrityError):
        await test_session.commit()
