# Stock Exchange API Specification

## Overview

RESTful API for the stock exchange simulation. Supports public market data access, authenticated trading operations, and administrative functions.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

### Authentication Methods

**API Key (Simple)**
```
Authorization: Bearer <api_key>
```

**Token Types:**
- **Trader tokens**: Access to trading and own portfolio
- **Admin tokens**: Full system access

### Public Endpoints
No authentication required for market data queries.

### Private Endpoints
Require valid trader or admin token.

---

## Public Endpoints

### List All Companies

Get all tradeable companies.

```http
GET /companies
```

**Response:**
```json
{
  "companies": [
    {
      "ticker": "TECH",
      "name": "TechCorp",
      "total_shares": 10000000,
      "float_shares": 4000000
    },
    {
      "ticker": "RETAIL",
      "name": "RetailCo",
      "total_shares": 5000000,
      "float_shares": 3000000
    }
  ]
}
```

### Get Company Info

Get details for a specific company.

```http
GET /companies/{ticker}
```

**Parameters:**
- `ticker` (path): Company ticker symbol

**Response:**
```json
{
  "ticker": "TECH",
  "name": "TechCorp",
  "total_shares": 10000000,
  "float_shares": 4000000,
  "last_price": 50.25,
  "market_cap": 502500000.00,
  "volume_24h": 125000
}
```

**Errors:**
- `404`: Company not found

### Get Order Book

Get current order book for a ticker (aggregated view).

```http
GET /orderbook/{ticker}
```

**Query Parameters:**
- `depth` (optional, default=10): Number of price levels to show

**Response:**
```json
{
  "ticker": "TECH",
  "timestamp": "2026-01-24T10:30:00Z",
  "bids": [
    {"price": 50.15, "quantity": 200},
    {"price": 50.10, "quantity": 400},
    {"price": 50.05, "quantity": 100}
  ],
  "asks": [
    {"price": 50.20, "quantity": 150},
    {"price": 50.25, "quantity": 300},
    {"price": 50.30, "quantity": 500}
  ],
  "spread": 0.05,
  "last_price": 50.18
}
```

**Notes:**
- Bids sorted by price DESC (highest first)
- Asks sorted by price ASC (lowest first)
- Quantities are aggregated by price level (anonymous)

**Errors:**
- `404`: Ticker not found

### Get Recent Trades

Get recent trade history for a ticker.

```http
GET /trades/{ticker}
```

**Query Parameters:**
- `limit` (optional, default=50, max=500): Number of trades to return
- `since` (optional): Timestamp - only trades after this time

**Response:**
```json
{
  "ticker": "TECH",
  "trades": [
    {
      "id": "trade_123",
      "price": 50.20,
      "quantity": 100,
      "timestamp": "2026-01-24T10:29:45Z"
    },
    {
      "id": "trade_122",
      "price": 50.18,
      "quantity": 250,
      "timestamp": "2026-01-24T10:29:30Z"
    }
  ]
}
```

**Notes:**
- Trades sorted by timestamp DESC (most recent first)
- Does NOT include buyer/seller IDs (anonymous)

**Errors:**
- `404`: Ticker not found

### Get Market Data

Get summary market data for a ticker.

```http
GET /market-data/{ticker}
```

**Response:**
```json
{
  "ticker": "TECH",
  "last_price": 50.20,
  "change_24h": 1.25,
  "change_percent_24h": 2.55,
  "volume_24h": 125000,
  "high_24h": 51.00,
  "low_24h": 49.50,
  "market_cap": 502000000.00,
  "timestamp": "2026-01-24T10:30:00Z"
}
```

**Errors:**
- `404`: Ticker not found

### Get All Market Data

Get summary data for all tickers.

```http
GET /market-data
```

**Response:**
```json
{
  "markets": [
    {
      "ticker": "TECH",
      "last_price": 50.20,
      "change_24h": 1.25,
      "volume_24h": 125000,
      "market_cap": 502000000.00
    },
    {
      "ticker": "RETAIL",
      "last_price": 25.50,
      "change_24h": -0.30,
      "volume_24h": 85000,
      "market_cap": 127500000.00
    }
  ],
  "timestamp": "2026-01-24T10:30:00Z"
}
```

---

## Authenticated Trader Endpoints

Require valid trader authentication token.

### Get Account Info

Get current account balance and summary.

```http
GET /account
```

**Headers:**
```
Authorization: Bearer <trader_token>
```

**Response:**
```json
{
  "account_id": "trader_123",
  "cash_balance": 98750.00,
  "portfolio_value": 153250.00,
  "total_value": 252000.00,
  "created_at": "2026-01-20T09:00:00Z"
}
```

**Notes:**
- `portfolio_value`: Sum of (holdings × last_price) for all positions
- `total_value`: cash_balance + portfolio_value

**Errors:**
- `401`: Invalid or missing token

### Get Portfolio

Get all current holdings.

```http
GET /account/portfolio
```

**Headers:**
```
Authorization: Bearer <trader_token>
```

**Response:**
```json
{
  "account_id": "trader_123",
  "cash_balance": 98750.00,
  "holdings": [
    {
      "ticker": "TECH",
      "quantity": 100,
      "avg_cost": 48.50,
      "current_price": 50.20,
      "market_value": 5020.00,
      "unrealized_pnl": 170.00
    },
    {
      "ticker": "RETAIL",
      "quantity": 50,
      "avg_cost": 24.00,
      "current_price": 25.50,
      "market_value": 1275.00,
      "unrealized_pnl": 75.00
    }
  ],
  "total_portfolio_value": 6295.00,
  "total_value": 105045.00
}
```

**Notes:**
- `avg_cost`: Average purchase price (calculated from trade history)
- `unrealized_pnl`: (current_price - avg_cost) × quantity

**Errors:**
- `401`: Invalid or missing token

### Get Open Orders

Get all active orders for the account.

```http
GET /account/orders
```

**Query Parameters:**
- `ticker` (optional): Filter by specific ticker
- `status` (optional): Filter by status (OPEN, PARTIAL)

**Headers:**
```
Authorization: Bearer <trader_token>
```

**Response:**
```json
{
  "account_id": "trader_123",
  "orders": [
    {
      "id": "order_456",
      "ticker": "TECH",
      "side": "BUY",
      "order_type": "LIMIT",
      "price": 49.50,
      "quantity": 100,
      "remaining_quantity": 100,
      "status": "OPEN",
      "timestamp": "2026-01-24T10:15:00Z"
    },
    {
      "id": "order_457",
      "ticker": "RETAIL",
      "side": "SELL",
      "order_type": "LIMIT",
      "price": 26.00,
      "quantity": 50,
      "remaining_quantity": 20,
      "status": "PARTIAL",
      "timestamp": "2026-01-24T10:20:00Z"
    }
  ]
}
```

**Errors:**
- `401`: Invalid or missing token

### Get Trade History

Get trade history for the account.

```http
GET /account/trades
```

**Query Parameters:**
- `ticker` (optional): Filter by specific ticker
- `limit` (optional, default=50, max=500): Number of trades
- `since` (optional): Timestamp - only trades after this time

**Headers:**
```
Authorization: Bearer <trader_token>
```

**Response:**
```json
{
  "account_id": "trader_123",
  "trades": [
    {
      "id": "trade_789",
      "ticker": "TECH",
      "side": "BUY",
      "price": 50.20,
      "quantity": 100,
      "total": 5020.00,
      "order_id": "order_455",
      "timestamp": "2026-01-24T10:25:00Z"
    },
    {
      "id": "trade_788",
      "ticker": "RETAIL",
      "side": "SELL",
      "price": 25.50,
      "quantity": 30,
      "total": 765.00,
      "order_id": "order_457",
      "timestamp": "2026-01-24T10:22:00Z"
    }
  ]
}
```

**Notes:**
- `side`: Whether YOU were buying or selling
- `total`: price × quantity (what you paid/received)

**Errors:**
- `401`: Invalid or missing token

### Place Order

Place a new buy or sell order.

```http
POST /orders
```

**Headers:**
```
Authorization: Bearer <trader_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "ticker": "TECH",
  "side": "BUY",
  "order_type": "LIMIT",
  "price": 50.00,
  "quantity": 100
}
```

**Fields:**
- `ticker` (required): Company ticker
- `side` (required): "BUY" or "SELL"
- `order_type` (required): "LIMIT" or "MARKET"
- `price` (required for LIMIT, omit for MARKET): Limit price
- `quantity` (required): Number of shares

**Response (Synchronous):**
```json
{
  "order_id": "order_890",
  "status": "FILLED",
  "quantity": 100,
  "remaining_quantity": 0,
  "fills": [
    {
      "trade_id": "trade_901",
      "price": 49.80,
      "quantity": 50,
      "timestamp": "2026-01-24T10:30:01Z"
    },
    {
      "trade_id": "trade_902",
      "price": 50.00,
      "quantity": 50,
      "timestamp": "2026-01-24T10:30:01Z"
    }
  ],
  "average_price": 49.90,
  "total_cost": 4990.00,
  "timestamp": "2026-01-24T10:30:01Z"
}
```

**Possible Status Values:**
- `FILLED`: Completely executed
- `PARTIAL`: Partially filled, remainder in order book
- `OPEN`: Not filled, posted to order book

**Errors:**
- `400`: Invalid parameters (bad ticker, negative quantity, etc.)
- `401`: Invalid or missing token
- `403`: Insufficient funds (BUY) or shares (SELL)
- `404`: Ticker not found

**Validation Rules:**
- BUY orders: Must have cash ≥ price × quantity
- SELL orders: Must own ≥ quantity of shares
- Quantity must be positive integer
- Price must be positive (for LIMIT orders)

### Cancel Order

Cancel an open or partially filled order.

```http
DELETE /orders/{order_id}
```

**Parameters:**
- `order_id` (path): Order to cancel

**Headers:**
```
Authorization: Bearer <trader_token>
```

**Response:**
```json
{
  "order_id": "order_456",
  "status": "CANCELLED",
  "remaining_quantity": 100,
  "message": "Order cancelled successfully"
}
```

**Errors:**
- `401`: Invalid or missing token
- `403`: Order doesn't belong to this account
- `404`: Order not found
- `409`: Order already filled or cancelled

---

## Admin Endpoints

Require admin authentication token. Full system access.

### Create Company

Register a new company for trading.

```http
POST /admin/companies
```

**Headers:**
```
Authorization: Bearer <admin_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "ticker": "FINANCE",
  "name": "FinanceCorp",
  "total_shares": 8000000,
  "float_shares": 5000000
}
```

**Response:**
```json
{
  "ticker": "FINANCE",
  "name": "FinanceCorp",
  "total_shares": 8000000,
  "float_shares": 5000000,
  "created_at": "2026-01-24T10:35:00Z"
}
```

**Errors:**
- `400`: Invalid parameters (float > total, negative values, etc.)
- `401`: Invalid or missing admin token
- `409`: Ticker already exists

### Create Account

Register a new trader account.

```http
POST /admin/accounts
```

**Headers:**
```
Authorization: Bearer <admin_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "account_id": "trader_456",
  "initial_cash": 100000.00
}
```

**Response:**
```json
{
  "account_id": "trader_456",
  "cash_balance": 100000.00,
  "api_key": "sk_live_AbCdEf123456...",
  "created_at": "2026-01-24T10:40:00Z"
}
```

**Notes:**
- Returns API key for the new trader
- Store this key - cannot be retrieved later

**Errors:**
- `400`: Invalid parameters (negative cash, etc.)
- `401`: Invalid or missing admin token
- `409`: Account ID already exists

### Get All Accounts

List all trader accounts (admin view).

```http
GET /admin/accounts
```

**Headers:**
```
Authorization: Bearer <admin_token>
```

**Response:**
```json
{
  "accounts": [
    {
      "account_id": "trader_123",
      "cash_balance": 98750.00,
      "portfolio_value": 6295.00,
      "total_value": 105045.00,
      "created_at": "2026-01-20T09:00:00Z"
    },
    {
      "account_id": "trader_456",
      "cash_balance": 100000.00,
      "portfolio_value": 0.00,
      "total_value": 100000.00,
      "created_at": "2026-01-24T10:40:00Z"
    }
  ]
}
```

**Errors:**
- `401`: Invalid or missing admin token

### Get Account Details (Admin)

Get full details for any account.

```http
GET /admin/accounts/{account_id}
```

**Parameters:**
- `account_id` (path): Account to view

**Headers:**
```
Authorization: Bearer <admin_token>
```

**Response:**
```json
{
  "account_id": "trader_123",
  "cash_balance": 98750.00,
  "holdings": [...],
  "open_orders": [...],
  "recent_trades": [...],
  "created_at": "2026-01-20T09:00:00Z"
}
```

**Errors:**
- `401`: Invalid or missing admin token
- `404`: Account not found

### Get System Stats

Get overall exchange statistics.

```http
GET /admin/stats
```

**Headers:**
```
Authorization: Bearer <admin_token>
```

**Response:**
```json
{
  "total_accounts": 15,
  "total_companies": 3,
  "total_cash_in_system": 1500000.00,
  "total_trades_24h": 1247,
  "total_volume_24h": 2500000.00,
  "active_orders": 89,
  "timestamp": "2026-01-24T10:45:00Z"
}
```

**Errors:**
- `401`: Invalid or missing admin token

### View Full Order Book (Admin)

Get non-aggregated order book with order IDs and accounts.

```http
GET /admin/orderbook/{ticker}
```

**Parameters:**
- `ticker` (path): Company ticker

**Headers:**
```
Authorization: Bearer <admin_token>
```

**Response:**
```json
{
  "ticker": "TECH",
  "bids": [
    {
      "order_id": "order_456",
      "account_id": "trader_123",
      "price": 50.15,
      "quantity": 200,
      "timestamp": "2026-01-24T10:15:00Z"
    }
  ],
  "asks": [
    {
      "order_id": "order_789",
      "account_id": "trader_456",
      "price": 50.20,
      "quantity": 150,
      "timestamp": "2026-01-24T10:18:00Z"
    }
  ]
}
```

**Notes:**
- Shows individual orders (not aggregated)
- Includes order IDs and account IDs
- Only available to admins (privacy)

**Errors:**
- `401`: Invalid or missing admin token
- `404`: Ticker not found

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Account has insufficient cash balance for this order",
    "details": {
      "required": 5000.00,
      "available": 3500.00
    }
  },
  "timestamp": "2026-01-24T10:50:00Z"
}
```

### Common Error Codes

**Client Errors (4xx):**
- `INVALID_PARAMETERS`: Bad request parameters
- `UNAUTHORIZED`: Missing or invalid authentication
- `FORBIDDEN`: Valid auth but insufficient permissions
- `NOT_FOUND`: Resource doesn't exist
- `CONFLICT`: Resource state conflict (e.g., duplicate)
- `INSUFFICIENT_FUNDS`: Not enough cash for BUY order
- `INSUFFICIENT_SHARES`: Not enough shares for SELL order

**Server Errors (5xx):**
- `INTERNAL_ERROR`: Unexpected server error
- `DATABASE_ERROR`: Database transaction failed

---

## Rate Limiting

**Public endpoints:**
- 100 requests per minute per IP

**Authenticated endpoints:**
- 1000 requests per minute per account

**Admin endpoints:**
- No rate limit

Exceeded limits return `429 Too Many Requests`.

---

## Webhooks (Future)

Not implemented in Phase 1, but planned:

```http
POST /account/webhooks
```

Subscribe to order fill notifications, price alerts, etc.

---

## WebSocket API (Future)

Not implemented in Phase 1, but planned for real-time updates:

```
ws://localhost:8000/ws/orderbook/{ticker}
ws://localhost:8000/ws/trades/{ticker}
```

---

## Example Workflows

### Complete Trading Flow

1. **Get market data**
```http
GET /market-data/TECH
```

2. **Check account balance**
```http
GET /account
Authorization: Bearer <token>
```

3. **View order book**
```http
GET /orderbook/TECH
```

4. **Place limit buy order**
```http
POST /orders
Authorization: Bearer <token>
{
  "ticker": "TECH",
  "side": "BUY",
  "order_type": "LIMIT",
  "price": 50.00,
  "quantity": 100
}
```

5. **Check if filled**
Response from step 4 shows status.

6. **View updated portfolio**
```http
GET /account/portfolio
Authorization: Bearer <token>
```

### Admin Setup Flow

1. **Create company**
```http
POST /admin/companies
Authorization: Bearer <admin_token>
{
  "ticker": "TECH",
  "name": "TechCorp",
  "total_shares": 10000000,
  "float_shares": 4000000
}
```

2. **Create traders**
```http
POST /admin/accounts
Authorization: Bearer <admin_token>
{
  "account_id": "trader_1",
  "initial_cash": 100000.00
}
```

3. **Give trader initial shares** (manually insert into holdings table for setup)

4. **Monitor system**
```http
GET /admin/stats
Authorization: Bearer <admin_token>
```

---

*Version: Phase 1*
*Last updated: 2026-01-24*
