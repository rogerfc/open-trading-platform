# Agent Platform

Autonomous trading agent management platform. Create, configure, and run trading agents with custom strategies.

## Quick Start

```bash
cd platform

# Install dependencies
pip install -r requirements.txt

# Run the platform
uvicorn agentplatform.main:app --port 8001

# Or with docker (Colima)
docker build -t agent-platform .
docker run -p 8001:8001 agent-platform
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/strategies` | List available strategies |
| GET | `/strategies/{id}` | Get strategy details |
| POST | `/strategies/validate` | Validate strategy config |
| POST | `/agents` | Create agent |
| GET | `/agents` | List agents |
| GET | `/agents/{id}` | Get agent details |
| PATCH | `/agents/{id}` | Update agent |
| DELETE | `/agents/{id}` | Delete agent |
| POST | `/agents/{id}/start` | Start trading |
| POST | `/agents/{id}/stop` | Stop trading |
| POST | `/agents/{id}/pause` | Pause trading |

## Creating an Agent

### 1. With a built-in strategy (Random)

```bash
curl -X POST http://localhost:8001/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Random Bot",
    "exchange_url": "http://localhost:8000",
    "api_key": "your-exchange-api-key",
    "strategy_type": "random",
    "strategy_params": {
      "max_order_value": 500,
      "cancel_probability": 0.2
    }
  }'
```

### 2. With a custom YAML strategy

```bash
curl -X POST http://localhost:8001/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Buy Low Sell High",
    "exchange_url": "http://localhost:8000",
    "api_key": "your-exchange-api-key",
    "strategy_type": "rule_based",
    "strategy_source": "name: Buy Low Sell High\nrules:\n  - name: Buy Dip\n    when:\n      - metric: price_change_pct\n        operator: \"<\"\n        value: -5\n    then:\n      - action: buy\n        quantity_pct: 0.25"
  }'
```

## YAML Strategy DSL

Write trading strategies using simple IF-THEN rules:

```yaml
name: "My First Strategy"
description: "Buys when price drops, sells when price rises"

settings:
  max_order_value: 500      # Max $ per trade
  min_cash_reserve: 100     # Always keep this much cash

rules:
  - name: "Buy the Dip"
    ticker: all             # Apply to all stocks
    when:
      - metric: price_change_pct
        operator: "<"
        value: -5           # Price dropped 5%
      - metric: my_cash
        operator: ">"
        value: 200
    then:
      - action: buy
        quantity_pct: 0.25  # Use 25% of cash
        order_type: limit
    cooldown_seconds: 300   # Wait 5 min between triggers

  - name: "Take Profits"
    when:
      - metric: price_change_pct
        operator: ">"
        value: 10
      - metric: my_holdings
        operator: ">"
        value: 0
    then:
      - action: sell
        quantity_pct: 0.5   # Sell half
```

### Available Metrics

| Metric | Description |
|--------|-------------|
| `price` | Current stock price |
| `price_change_pct` | % change from recent average |
| `bid_price` | Best bid price |
| `ask_price` | Best ask price |
| `spread_pct` | Bid-ask spread as % |
| `my_cash` | Available cash |
| `my_holdings` | Shares owned |
| `my_position_value` | Holdings × price |
| `my_open_orders` | Number of open orders |

### Available Actions

| Action | Options |
|--------|---------|
| `buy` | `quantity`, `quantity_pct`, `quantity_all`, `price`, `price_offset_pct`, `order_type` |
| `sell` | Same as buy |
| `cancel_orders` | Cancels all open orders for ticker |

## Architecture

```
Agent Platform (port 8001)
    │
    │  HTTP API
    ▼
Stock Exchange (port 8000)
```

The platform is completely separate from the exchange. It communicates via the exchange's public API using the trader's API key.
