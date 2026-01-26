# Stock Exchange Simulation - Data Model

## Overview

This document defines the database schema for a simplified stock exchange simulation. The system uses a relational database to ensure ACID properties, particularly atomicity for trade execution.

## Core Principles

- **Zero-sum system** (Phase 1): Fixed cash, fixed traders, no fees
- **Companies are passive**: No active trading or decision-making
- **Traders are active**: Seek profit through buying/selling
- **Exchange is neutral**: Infrastructure for order matching
- **Sequential processing**: Orders processed one at a time

## Database Schema

### Companies Table

Represents publicly traded companies. Static entities that define tradeable securities.

```sql
CREATE TABLE companies (
    ticker VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    total_shares BIGINT NOT NULL,
    float_shares BIGINT NOT NULL,
    CHECK (float_shares <= total_shares),
    CHECK (total_shares > 0),
    CHECK (float_shares >= 0)
);
```

**Fields:**
- `ticker`: Unique symbol for the company (e.g., "TECH", "RETAIL")
- `name`: Company name
- `total_shares`: Total shares outstanding (100% of company ownership)
- `float_shares`: Shares available for public trading

**Notes:**
- Float shares are a subset of total shares
- Difference (total - float) represents privately held shares
- For Phase 1, these values are fixed (no dilution, buybacks, or releases)

### Accounts Table

Represents traders/participants in the exchange.

```sql
CREATE TABLE accounts (
    id VARCHAR PRIMARY KEY,
    cash_balance DECIMAL(15,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (cash_balance >= 0)
);
```

**Fields:**
- `id`: Unique account identifier
- `cash_balance`: Available cash for trading
- `created_at`: Account creation timestamp

**Notes:**
- All traders must be registered (exist in this table)
- Cash balance cannot be negative (no margin/credit in Phase 1)
- For Phase 1, cash cannot be added/withdrawn after account creation

### Holdings Table

Tracks share ownership. Represents who owns how many shares of each company.

```sql
CREATE TABLE holdings (
    account_id VARCHAR,
    ticker VARCHAR,
    quantity BIGINT NOT NULL,
    PRIMARY KEY (account_id, ticker),
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (ticker) REFERENCES companies(ticker),
    CHECK (quantity > 0)
);
```

**Fields:**
- `account_id`: Account that owns the shares
- `ticker`: Company ticker
- `quantity`: Number of shares owned

**Notes:**
- Composite primary key (one row per account-ticker pair)
- Quantity must be positive (rows deleted when quantity reaches 0)
- Updated immediately during trade execution

### Orders Table

The order book. Contains all buy and sell orders waiting to be matched.

```sql
CREATE TABLE orders (
    id VARCHAR PRIMARY KEY,
    account_id VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    side ENUM('BUY', 'SELL') NOT NULL,
    order_type ENUM('LIMIT', 'MARKET') NOT NULL,
    price DECIMAL(10,2),
    quantity BIGINT NOT NULL,
    remaining_quantity BIGINT NOT NULL,
    status ENUM('OPEN', 'PARTIAL', 'FILLED', 'CANCELLED') NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (ticker) REFERENCES companies(ticker),
    CHECK (quantity > 0),
    CHECK (remaining_quantity >= 0),
    CHECK (remaining_quantity <= quantity),
    CHECK (price > 0 OR order_type = 'MARKET')
);
```

**Fields:**
- `id`: Unique order identifier
- `account_id`: Account that placed the order
- `ticker`: Company being traded
- `side`: BUY or SELL
- `order_type`: LIMIT (specific price) or MARKET (best available)
- `price`: Limit price (NULL for market orders)
- `quantity`: Original order size
- `remaining_quantity`: Shares still to be filled
- `status`: Order state
- `timestamp`: When order was placed

**Order Status:**
- `OPEN`: No fills yet, full quantity remaining
- `PARTIAL`: Some fills, but quantity remaining
- `FILLED`: Completely executed, no quantity remaining
- `CANCELLED`: Cancelled by user, no longer active

**Notes:**
- Price-time priority: Orders matched by best price first, then earliest timestamp
- Market orders must specify side but not price
- Limit orders must specify both side and price

### Trades Table

Historical record of all executed trades. Single source of truth for trade history.

```sql
CREATE TABLE trades (
    id VARCHAR PRIMARY KEY,
    ticker VARCHAR NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    quantity BIGINT NOT NULL,
    buyer_id VARCHAR NOT NULL,
    seller_id VARCHAR NOT NULL,
    buy_order_id VARCHAR NOT NULL,
    sell_order_id VARCHAR NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticker) REFERENCES companies(ticker),
    FOREIGN KEY (buyer_id) REFERENCES accounts(id),
    FOREIGN KEY (seller_id) REFERENCES accounts(id),
    FOREIGN KEY (buy_order_id) REFERENCES orders(id),
    FOREIGN KEY (sell_order_id) REFERENCES orders(id),
    CHECK (price > 0),
    CHECK (quantity > 0)
);
```

**Fields:**
- `id`: Unique trade identifier
- `ticker`: Company traded
- `price`: Execution price
- `quantity`: Shares traded
- `buyer_id`: Account that bought
- `seller_id`: Account that sold
- `buy_order_id`: Buy order that was matched
- `sell_order_id`: Sell order that was matched
- `timestamp`: When trade executed

**Notes:**
- Records created atomically with ownership/cash transfers
- Trade history is append-only (never modified/deleted)
- Used for: price charts, analytics, audit trail, tax reporting
- Filtered by ticker to get per-company history

## Data Relationships

```
companies (1) ----< (many) holdings
companies (1) ----< (many) orders
companies (1) ----< (many) trades

accounts (1) ----< (many) holdings
accounts (1) ----< (many) orders
accounts (1) ----< (many) trades (as buyer)
accounts (1) ----< (many) trades (as seller)

orders (1) ----< (many) trades (buy side)
orders (1) ----< (many) trades (sell side)
```

## Key Concepts

### Order Book

The order book for a ticker consists of:
- **Bids**: All BUY orders with status OPEN or PARTIAL, sorted by price DESC, timestamp ASC
- **Asks**: All SELL orders with status OPEN or PARTIAL, sorted by price ASC, timestamp ASC

Retrieved via query, not stored separately.

### Last Traded Price

The current "price" of a stock is the price from the most recent trade:

```sql
SELECT price FROM trades 
WHERE ticker = ? 
ORDER BY timestamp DESC 
LIMIT 1
```

### Market Capitalization

Calculated dynamically:
```
Market Cap = Last Traded Price × Total Shares
```

### Spread

The gap between best bid and best ask:
```
Spread = Best Ask Price - Best Bid Price
```

### Account Portfolio

For a given account:
- **Cash**: `accounts.cash_balance`
- **Holdings**: All rows in `holdings` where `account_id` matches
- **Portfolio Value**: Cash + Σ(quantity × last_price) for all holdings
- **Open Orders**: All rows in `orders` where `account_id` matches and status is OPEN or PARTIAL

## Trade Execution Flow

### Atomicity Guarantee

All trade operations occur within a database transaction:

1. **Validate**:
   - Seller has sufficient shares
   - Buyer has sufficient cash
   - Orders still valid (not cancelled)

2. **Transfer Shares**:
   - Deduct from seller's holdings
   - Add to buyer's holdings

3. **Transfer Cash**:
   - Add to seller's cash balance
   - Deduct from buyer's cash balance

4. **Update Orders**:
   - Reduce remaining_quantity
   - Update status (PARTIAL or FILLED)

5. **Record Trade**:
   - Insert into trades table

If any step fails, entire transaction rolls back automatically.

### Order Matching

Basic price-time priority algorithm:
1. Find best opposing order (highest bid for sell, lowest ask for buy)
2. If prices cross (bid ≥ ask), execute trade
3. Match quantity (partial fill if necessary)
4. Repeat until no more matches possible

## Example Data

### Initial State

```sql
-- Companies
INSERT INTO companies VALUES ('TECH', 'TechCorp', 10000000, 4000000);
INSERT INTO companies VALUES ('RETAIL', 'RetailCo', 5000000, 3000000);

-- Accounts
INSERT INTO accounts (id, cash_balance) VALUES ('trader1', 100000.00);
INSERT INTO accounts (id, cash_balance) VALUES ('trader2', 50000.00);

-- Holdings
INSERT INTO holdings VALUES ('trader1', 'TECH', 100);
INSERT INTO holdings VALUES ('trader2', 'RETAIL', 200);
```

### After Trading

```sql
-- Orders (trader1 wants to buy RETAIL)
INSERT INTO orders VALUES (
    'order1', 'trader1', 'RETAIL', 'BUY', 'LIMIT', 
    25.00, 50, 50, 'OPEN', CURRENT_TIMESTAMP
);

-- Orders (trader2 willing to sell RETAIL)
INSERT INTO orders VALUES (
    'order2', 'trader2', 'RETAIL', 'SELL', 'LIMIT',
    25.00, 50, 50, 'OPEN', CURRENT_TIMESTAMP
);

-- Trade executed (orders matched)
INSERT INTO trades VALUES (
    'trade1', 'RETAIL', 25.00, 50,
    'trader1', 'trader2', 'order1', 'order2',
    CURRENT_TIMESTAMP
);

-- Updated holdings
UPDATE holdings SET quantity = 150 WHERE account_id = 'trader2' AND ticker = 'RETAIL';
INSERT INTO holdings VALUES ('trader1', 'RETAIL', 50);

-- Updated cash
UPDATE accounts SET cash_balance = 98750.00 WHERE id = 'trader1';  -- -1250
UPDATE accounts SET cash_balance = 51250.00 WHERE id = 'trader2';  -- +1250

-- Updated orders
UPDATE orders SET remaining_quantity = 0, status = 'FILLED' WHERE id = 'order1';
UPDATE orders SET remaining_quantity = 0, status = 'FILLED' WHERE id = 'order2';
```

## Future Extensions (Phase 2+)

Possible additions not in Phase 1:
- Company actions (dividends, splits, buybacks, new issuance)
- Account deposits/withdrawals
- Transaction fees
- Different account types (market makers, institutions)
- Order types (stop-loss, stop-limit, trailing stops)
- Short selling
- Margin/credit
- Market depth data
- Price history aggregates (OHLC candles)

---

*Version: Phase 1 - Basic Trading*
*Last updated: 2026-01-24*
