# Stock Exchange API - Trader Guide

Base URL: `http://localhost:8000`

## Authentication

All trader endpoints require an API key passed in the `X-API-Key` header:

```bash
curl -H "X-API-Key: sk_your_api_key_here" http://localhost:8000/account
```

---

## Public Endpoints (No Authentication)

### List Companies

```bash
curl http://localhost:8000/companies
```

Response:
```json
{
  "companies": [
    {"ticker": "TECH", "name": "TechCorp Industries", "total_shares": 10000000, "float_shares": 500},
    {"ticker": "BANK", "name": "First National Bank", "total_shares": 5000000, "float_shares": 1000}
  ]
}
```

### Get Company Details

```bash
curl http://localhost:8000/companies/TECH
```

Response:
```json
{
  "ticker": "TECH",
  "name": "TechCorp Industries",
  "total_shares": 10000000,
  "float_shares": 500,
  "last_price": "150.00",
  "market_cap": "1500000000.00",
  "volume_24h": 125
}
```

### Get Order Book

```bash
curl http://localhost:8000/orderbook/TECH
curl "http://localhost:8000/orderbook/TECH?depth=5"
```

Response:
```json
{
  "ticker": "TECH",
  "timestamp": "2026-01-27T10:30:00Z",
  "bids": [
    {"price": "149.50", "quantity": 10},
    {"price": "149.00", "quantity": 25}
  ],
  "asks": [
    {"price": "150.00", "quantity": 500},
    {"price": "151.00", "quantity": 15}
  ],
  "spread": "0.50",
  "last_price": "150.00"
}
```

### Get Recent Trades

```bash
curl http://localhost:8000/trades/TECH
curl "http://localhost:8000/trades/TECH?limit=10"
```

Response:
```json
{
  "ticker": "TECH",
  "trades": [
    {"id": "abc123", "price": "150.00", "quantity": 5, "timestamp": "2026-01-27T10:29:45Z"},
    {"id": "def456", "price": "149.50", "quantity": 10, "timestamp": "2026-01-27T10:28:30Z"}
  ]
}
```

### Get Market Data

Single ticker:
```bash
curl http://localhost:8000/market-data/TECH
```

Response:
```json
{
  "ticker": "TECH",
  "last_price": "150.00",
  "change_24h": "2.50",
  "change_percent_24h": "1.69",
  "volume_24h": 125,
  "high_24h": "152.00",
  "low_24h": "147.50",
  "market_cap": "1500000000.00",
  "timestamp": "2026-01-27T10:30:00Z"
}
```

All tickers:
```bash
curl http://localhost:8000/market-data
```

Response:
```json
{
  "markets": [
    {"ticker": "TECH", "last_price": "150.00", "change_24h": "2.50", "volume_24h": 125, "market_cap": "1500000000.00"},
    {"ticker": "BANK", "last_price": "85.00", "change_24h": "-1.00", "volume_24h": 50, "market_cap": "425000000.00"}
  ],
  "timestamp": "2026-01-27T10:30:00Z"
}
```

---

## Trader Endpoints (Authentication Required)

### Get Account Info

```bash
curl -H "X-API-Key: sk_your_key" http://localhost:8000/account
```

Response:
```json
{
  "account_id": "alice",
  "cash_balance": "100000.00",
  "created_at": "2026-01-27T08:00:00Z"
}
```

### Get Holdings

```bash
curl -H "X-API-Key: sk_your_key" http://localhost:8000/holdings
```

Response:
```json
{
  "holdings": [
    {"ticker": "TECH", "quantity": 10},
    {"ticker": "BANK", "quantity": 25}
  ]
}
```

### Place Order

**Buy Limit Order:**
```bash
curl -X POST http://localhost:8000/orders \
  -H "X-API-Key: sk_your_key" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "TECH", "side": "BUY", "order_type": "LIMIT", "quantity": 10, "price": "149.00"}'
```

**Sell Limit Order:**
```bash
curl -X POST http://localhost:8000/orders \
  -H "X-API-Key: sk_your_key" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "TECH", "side": "SELL", "order_type": "LIMIT", "quantity": 5, "price": "155.00"}'
```

**Market Order:**
```bash
curl -X POST http://localhost:8000/orders \
  -H "X-API-Key: sk_your_key" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "TECH", "side": "BUY", "order_type": "MARKET", "quantity": 10}'
```

Response (201 Created):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "ticker": "TECH",
  "side": "BUY",
  "order_type": "LIMIT",
  "price": "149.00",
  "quantity": 10,
  "remaining_quantity": 10,
  "status": "OPEN",
  "timestamp": "2026-01-27T10:31:00Z"
}
```

Order statuses: `OPEN`, `PARTIAL`, `FILLED`, `CANCELLED`

### List Orders

```bash
# All orders
curl -H "X-API-Key: sk_your_key" http://localhost:8000/orders

# Filter by status
curl -H "X-API-Key: sk_your_key" "http://localhost:8000/orders?status=OPEN"

# Filter by ticker
curl -H "X-API-Key: sk_your_key" "http://localhost:8000/orders?ticker=TECH"

# Combined filters
curl -H "X-API-Key: sk_your_key" "http://localhost:8000/orders?status=OPEN&ticker=TECH"
```

Response:
```json
{
  "orders": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "ticker": "TECH",
      "side": "BUY",
      "order_type": "LIMIT",
      "price": "149.00",
      "quantity": 10,
      "remaining_quantity": 10,
      "status": "OPEN",
      "timestamp": "2026-01-27T10:31:00Z"
    }
  ]
}
```

### Get Order Details

```bash
curl -H "X-API-Key: sk_your_key" http://localhost:8000/orders/550e8400-e29b-41d4-a716-446655440000
```

### Cancel Order

```bash
curl -X DELETE -H "X-API-Key: sk_your_key" http://localhost:8000/orders/550e8400-e29b-41d4-a716-446655440000
```

Response: Order object with `status: "CANCELLED"`

---

## Common Workflows

### 1. Check Balance and Buy Stock

```bash
# Check available cash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/account

# View order book to see best ask price
curl http://localhost:8000/orderbook/TECH

# Place buy order at or below best ask
curl -X POST http://localhost:8000/orders \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "TECH", "side": "BUY", "order_type": "LIMIT", "quantity": 5, "price": "150.00"}'

# Check if order was filled
curl -H "X-API-Key: $API_KEY" http://localhost:8000/orders?status=FILLED
```

### 2. Sell Holdings

```bash
# Check what you own
curl -H "X-API-Key: $API_KEY" http://localhost:8000/holdings

# View order book to see best bid price
curl http://localhost:8000/orderbook/TECH

# Place sell order at or above best bid
curl -X POST http://localhost:8000/orders \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "TECH", "side": "SELL", "order_type": "LIMIT", "quantity": 5, "price": "149.50"}'
```

### 3. Monitor and Cancel Open Orders

```bash
# List open orders
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/orders?status=OPEN"

# Cancel an order that hasn't filled
curl -X DELETE -H "X-API-Key: $API_KEY" http://localhost:8000/orders/$ORDER_ID
```

---

## Error Responses

**401 Unauthorized** - Missing or invalid API key
```json
{"detail": "Missing API key"}
```

**400 Bad Request** - Invalid order parameters
```json
{"detail": "Insufficient cash for order"}
```

**404 Not Found** - Resource doesn't exist
```json
{"detail": "Company not found"}
```

---

## Order Matching

Orders are matched immediately on placement using price-time priority:
- **Buy orders** match against the lowest-priced sell orders first
- **Sell orders** match against the highest-priced buy orders first
- **Limit orders** only match if the price constraint is satisfied
- **Market orders** match at whatever price is available; unfilled quantity is cancelled

When a trade executes:
- Cash is transferred from buyer to seller
- Shares are transferred from seller to buyer
- Order status updates to `PARTIAL` or `FILLED`
