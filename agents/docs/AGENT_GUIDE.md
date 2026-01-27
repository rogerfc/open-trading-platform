# Agent Creation Guide

## Prerequisites

1. Running exchange at `http://localhost:8000`
2. A trader account with API key (from exchange admin)
3. Running agent platform at `http://localhost:8001`

## Quick Start: Create an Agent

### 1. List Available Strategies

```bash
curl http://localhost:8001/strategies
```

Returns:
```json
[
  {"id": "random", "name": "Random Strategy", "difficulty": "beginner", ...},
  {"id": "rule_based", "name": "Rule-Based Strategy", "difficulty": "beginner", ...}
]
```

### 2. Create an Agent with a Built-in Strategy

```bash
curl -X POST http://localhost:8001/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Bot",
    "exchange_url": "http://localhost:8000",
    "api_key": "your-exchange-api-key",
    "strategy_type": "random",
    "interval_seconds": 10
  }'
```

### 3. Start the Agent

```bash
curl -X POST http://localhost:8001/agents/{agent_id}/start
```

### 4. Monitor the Agent

```bash
# Get agent status
curl http://localhost:8001/agents/{agent_id}

# List all agents
curl http://localhost:8001/agents
```

### 5. Stop the Agent

```bash
curl -X POST http://localhost:8001/agents/{agent_id}/stop
```

---

## Creating a Custom Strategy (YAML)

### Step 1: Understand the DSL

Strategies are defined as a list of rules. Each rule has:
- **when**: Conditions that must ALL be true
- **then**: Actions to take when conditions are met

### Step 2: Write Your Strategy

Create a YAML file (e.g., `my_strategy.yaml`):

```yaml
name: "My Custom Strategy"
description: "Buys dips, sells rallies"

settings:
  max_order_value: 500      # Max $ per order
  min_cash_reserve: 100     # Always keep this much cash

rules:
  - name: "Buy the Dip"
    ticker: all
    when:
      - metric: price_change_pct
        operator: "<"
        value: -5
      - metric: my_cash
        operator: ">"
        value: 200
    then:
      - action: buy
        quantity_pct: 0.25
        order_type: limit
    cooldown_seconds: 300

  - name: "Take Profits"
    ticker: all
    when:
      - metric: price_change_pct
        operator: ">"
        value: 10
      - metric: my_holdings
        operator: ">"
        value: 0
    then:
      - action: sell
        quantity_pct: 0.5
        order_type: limit
    cooldown_seconds: 300
```

### Step 3: Validate Your Strategy

```bash
curl -X POST http://localhost:8001/strategies/validate \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "rule_based",
    "strategy_source": "name: Test\nrules:\n  - name: R1\n    when:\n      - metric: my_cash\n        operator: \">\"\n        value: 100\n    then:\n      - action: buy\n        quantity: 1"
  }'
```

### Step 4: Create Agent with Your Strategy

```bash
curl -X POST http://localhost:8001/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Custom Bot",
    "exchange_url": "http://localhost:8000",
    "api_key": "your-api-key",
    "strategy_type": "rule_based",
    "strategy_source": "name: My Strategy\nrules:\n  - name: Buy Dip\n    when:\n      - metric: price_change_pct\n        operator: \"<\"\n        value: -5\n    then:\n      - action: buy\n        quantity_pct: 0.25"
  }'
```

---

## DSL Reference

### Available Metrics

| Metric | Description | Example |
|--------|-------------|---------|
| `price` | Current stock price | `price > 50` |
| `price_change_pct` | % change from recent average | `price_change_pct < -5` |
| `bid_price` | Best bid price | `bid_price > 45` |
| `ask_price` | Best ask price | `ask_price < 55` |
| `spread_pct` | Bid-ask spread as % | `spread_pct > 2` |
| `my_cash` | Your available cash | `my_cash > 1000` |
| `my_holdings` | Shares you own (for ticker) | `my_holdings > 0` |
| `my_position_value` | Holdings × price | `my_position_value < 5000` |
| `my_open_orders` | Number of open orders | `my_open_orders < 3` |

### Operators

`<`, `<=`, `>`, `>=`, `==`, `!=`

### Actions

**Buy:**
```yaml
- action: buy
  quantity: 10              # Exact shares
  # OR
  quantity_pct: 0.25        # 25% of affordable
  # OR
  quantity_all: true        # Max affordable

  price: 50.00              # Exact price
  # OR
  price_offset_pct: -0.01   # 1% below market

  order_type: limit         # or "market"
```

**Sell:**
```yaml
- action: sell
  quantity: 10              # Exact shares
  # OR
  quantity_pct: 0.5         # 50% of holdings
  # OR
  quantity_all: true        # All holdings

  price_offset_pct: 0.01    # 1% above market
  order_type: limit
```

**Cancel Orders:**
```yaml
- action: cancel_orders     # Cancels all open orders for ticker
```

### Rule Options

```yaml
rules:
  - name: "Rule Name"
    description: "What this rule does"
    ticker: all             # "all" or specific ticker like "AAPL"
    when: [...]
    then: [...]
    cooldown_seconds: 300   # Wait time before rule can trigger again
    priority: 10            # Higher = checked first
```

---

## Example Strategies

### Conservative: Only Buy Dips

```yaml
name: "Conservative Buyer"
settings:
  max_order_value: 200
  min_cash_reserve: 500

rules:
  - name: "Buy Big Dips Only"
    when:
      - metric: price_change_pct
        operator: "<"
        value: -10
      - metric: my_cash
        operator: ">"
        value: 700
    then:
      - action: buy
        quantity_pct: 0.1
    cooldown_seconds: 600
```

### Spread Trading

```yaml
name: "Spread Trader"
settings:
  max_order_value: 1000

rules:
  - name: "Wide Spread"
    when:
      - metric: spread_pct
        operator: ">"
        value: 3
      - metric: my_open_orders
        operator: "<"
        value: 4
    then:
      - action: buy
        quantity: 5
        price_offset_pct: -0.005
      - action: sell
        quantity: 5
        price_offset_pct: 0.005
    cooldown_seconds: 120
```

---

## Troubleshooting

**Agent won't start:**
- Check API key is valid
- Verify exchange is running
- Check `last_error` field in agent response

**Strategy validation fails:**
- Every rule needs at least one `when` condition
- Every rule needs at least one `then` action
- Check metric names are spelled correctly

**Agent keeps erroring:**
- After 10 errors, agent auto-stops with ERROR status
- Check `last_error` for details
- Fix the issue, then restart the agent
