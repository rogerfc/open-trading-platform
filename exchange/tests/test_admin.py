"""Tests for admin API endpoints."""

import pytest


# ============================================================================
# Company Endpoint Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_company(test_client):
    """Test creating a company with valid data."""
    response = await test_client.post(
        "/admin/companies",
        json={
            "ticker": "tech",  # Should be uppercased
            "name": "Tech Corp",
            "total_shares": 1000000,
            "float_shares": 500000,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["ticker"] == "TECH"  # Uppercased
    assert data["name"] == "Tech Corp"
    assert data["total_shares"] == 1000000
    assert data["float_shares"] == 500000


@pytest.mark.asyncio
async def test_create_company_duplicate(test_client):
    """Test that duplicate ticker returns 409."""
    # Create first company
    await test_client.post(
        "/admin/companies",
        json={
            "ticker": "DUPE",
            "name": "First Company",
            "total_shares": 1000,
            "float_shares": 500,
        },
    )

    # Try to create duplicate
    response = await test_client.post(
        "/admin/companies",
        json={
            "ticker": "DUPE",
            "name": "Second Company",
            "total_shares": 2000,
            "float_shares": 1000,
        },
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_company_invalid_shares(test_client):
    """Test that float_shares > total_shares returns 422."""
    response = await test_client.post(
        "/admin/companies",
        json={
            "ticker": "BAD",
            "name": "Bad Company",
            "total_shares": 1000,
            "float_shares": 2000,  # Invalid: exceeds total
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_company_negative_shares(test_client):
    """Test that negative shares returns 422."""
    response = await test_client.post(
        "/admin/companies",
        json={
            "ticker": "BAD",
            "name": "Bad Company",
            "total_shares": -1000,
            "float_shares": 500,
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_companies_empty(test_client):
    """Test listing companies when none exist."""
    response = await test_client.get("/admin/companies")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_companies(test_client):
    """Test listing companies after creation."""
    # Create companies
    await test_client.post(
        "/admin/companies",
        json={"ticker": "AAA", "name": "AAA Corp", "total_shares": 1000, "float_shares": 500},
    )
    await test_client.post(
        "/admin/companies",
        json={"ticker": "BBB", "name": "BBB Corp", "total_shares": 2000, "float_shares": 1000},
    )

    response = await test_client.get("/admin/companies")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Should be sorted by ticker
    assert data[0]["ticker"] == "AAA"
    assert data[1]["ticker"] == "BBB"


# ============================================================================
# Account Endpoint Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_account(test_client):
    """Test creating an account with valid data."""
    response = await test_client.post(
        "/admin/accounts",
        json={
            "account_id": "trader1",
            "initial_cash": 10000.00,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["account_id"] == "trader1"
    assert data["cash_balance"] == "10000.00"
    assert "api_key" in data
    assert data["api_key"].startswith("sk_")
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_account_default_cash(test_client):
    """Test creating an account with default cash balance."""
    response = await test_client.post(
        "/admin/accounts",
        json={"account_id": "broke_trader"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["cash_balance"] == "0.00"


@pytest.mark.asyncio
async def test_create_account_duplicate(test_client):
    """Test that duplicate account_id returns 409."""
    # Create first account
    await test_client.post(
        "/admin/accounts",
        json={"account_id": "dupe_account", "initial_cash": 1000.00},
    )

    # Try to create duplicate
    response = await test_client.post(
        "/admin/accounts",
        json={"account_id": "dupe_account", "initial_cash": 2000.00},
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_account_negative_cash(test_client):
    """Test that negative initial cash returns 422."""
    response = await test_client.post(
        "/admin/accounts",
        json={"account_id": "negative", "initial_cash": -1000.00},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_accounts_empty(test_client):
    """Test listing accounts when none exist."""
    response = await test_client.get("/admin/accounts")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_accounts(test_client):
    """Test listing accounts after creation."""
    # Create accounts
    await test_client.post(
        "/admin/accounts",
        json={"account_id": "trader_a", "initial_cash": 1000.00},
    )
    await test_client.post(
        "/admin/accounts",
        json={"account_id": "trader_b", "initial_cash": 2000.00},
    )

    response = await test_client.get("/admin/accounts")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Should not include api_key in list response
    assert "api_key" not in data[0]
    assert "api_key" not in data[1]
