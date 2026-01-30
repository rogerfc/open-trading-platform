# Stock Exchange Simulation

A complete stock exchange simulation with autonomous trading agents and observability.

## Components

| Directory | Description | Port |
|-----------|-------------|------|
| `exchange/` | Stock exchange API server | 8000 |
| `agents/` | Autonomous trading agent platform | 8001 |
| `observability/` | Grafana + Prometheus + Loki stack | 3000 |
| `market/` | Unified CLI for all operations | - |
| `scenario/` | Scenario definitions and management | - |

## Quick Start

### 1. Start Services

```bash
# Exchange only
docker compose up -d exchange

# With agent platform
docker compose --profile agents up -d

# With observability (Grafana dashboards)
docker compose --profile observability up -d

# Full stack
docker compose --profile agents --profile observability up -d
```

### 2. Load a Scenario

Scenarios define companies, accounts, and agents in a single YAML file:

```bash
# List available scenarios
python -m market.cli scenario list

# Load the basic market scenario
python -m market.cli scenario load scenario/scenarios/basic_market.yaml

# Check status
python -m market.cli scenario status
```

### 3. Monitor

- **Grafana**: http://localhost:3000 (admin/admin)
  - Exchange Dashboard: trades, volume, order flow
  - Agent Dashboard: cycles, actions, errors
- **Exchange API**: http://localhost:8000/docs
- **Agent Platform API**: http://localhost:8001/docs

## Market CLI

The `market` CLI provides unified access to all operations:

```bash
python -m market.cli [OPTIONS] <resource> <verb> [ARGS]
```

### Global Options

| Option | Description |
|--------|-------------|
| `-e, --exchange-url` | Exchange API URL (default: http://localhost:8000) |
| `-a, --agents-url` | Agent Platform URL (default: http://localhost:8001) |
| `-o, --output` | Output format: table, json, yaml |

### Commands

```bash
# Service status
python -m market.cli status

# Companies
python -m market.cli company list
python -m market.cli company show TECH
python -m market.cli company create TECH "TechCorp" --total-shares 1000000 --float-shares 1000 --ipo-price 100

# Accounts
python -m market.cli account list
python -m market.cli account create alice --cash 50000
python -m market.cli account show alice --api-key sk_xxx

# Orders (requires API key)
python -m market.cli order list --api-key sk_xxx
python -m market.cli order create --api-key sk_xxx --ticker TECH --side BUY --type LIMIT --quantity 10 --price 99.50
python -m market.cli order cancel <order-id> --api-key sk_xxx

# Order book & trades
python -m market.cli orderbook show TECH --depth 10
python -m market.cli trade list TECH --limit 20

# Agents
python -m market.cli agent list
python -m market.cli agent create "My Bot" --api-key sk_xxx --strategy random --interval 5
python -m market.cli agent start <agent-id>
python -m market.cli agent stop <agent-id>

# Strategies
python -m market.cli strategy list
python -m market.cli strategy show random

# Scenarios
python -m market.cli scenario list
python -m market.cli scenario load scenario/scenarios/basic_market.yaml
python -m market.cli scenario status
python -m market.cli scenario stop
python -m market.cli scenario start

# Reset databases
python -m market.cli reset exchange
python -m market.cli reset agents
python -m market.cli reset all
```

## Scenarios

Scenarios define a complete trading environment in YAML:

```yaml
name: "Basic Market"
description: "Simple market with two companies and one trader"

exchange:
  url: "http://localhost:8000"

companies:
  - ticker: TECH
    name: "TechCorp Industries"
    total_shares: 1000000
    float_shares: 1000
    ipo_price: 100.00

accounts:
  - id: alice
    initial_cash: 50000.00

agent_platform:
  url: "http://localhost:8001"

agents:
  - name: "Alice Random Trader"
    account: alice
    strategy_type: random
    strategy_params:
      max_order_value: 500
    interval_seconds: 5
    auto_start: true
```

Available scenarios:
- `scenario/scenarios/basic_market.yaml` - Minimal setup (2 companies, 2 accounts, 1 agent)
- `scenario/scenarios/market_makers.yaml` - Multiple agents with different strategies

## Architecture

```
┌─────────────────┐
│   Market CLI    │
│  (market/)      │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Agent Platform  │────▶│    Exchange     │
│   (port 8001)   │     │   (port 8000)   │
└─────────────────┘     └────────┬────────┘
         │                       │
         │ OTLP                  │ OTLP
         ▼                       ▼
┌─────────────────────────────────────────┐
│           Observability Stack           │
│  Alloy → Prometheus → Grafana           │
│              (port 3000)                │
└─────────────────────────────────────────┘
```

## Development

### Running Locally

```bash
# Install dependencies (from project root)
pip install -r exchange/requirements.txt
pip install -r agents/requirements.txt

# Start exchange
cd exchange && uvicorn app.main:app --port 8000

# Start agent platform (separate terminal)
cd agents && uvicorn agentplatform.main:app --port 8001
```

### Running Tests

```bash
# Exchange tests
pytest exchange/tests/

# Agent tests
pytest agents/tests/
```

### Exchange Management (Legacy)

The exchange also has a standalone management script:

```bash
cd exchange

# Load sample companies
python manage.py companies load

# Show database status
python manage.py db status

# Clear database
python manage.py db clear
```

## API Documentation

- **Exchange**: http://localhost:8000/docs (Swagger UI)
- **Agent Platform**: http://localhost:8001/docs (Swagger UI)

### Key Exchange Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /companies` | List all companies |
| `GET /orderbook/{ticker}` | Get order book |
| `GET /trades/{ticker}` | Get recent trades |
| `POST /orders` | Place order (requires API key) |
| `GET /holdings` | Get holdings (requires API key) |

### Key Agent Platform Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /strategies` | List available strategies |
| `POST /agents` | Create agent |
| `POST /agents/{id}/start` | Start agent |
| `POST /agents/{id}/stop` | Stop agent |

## Documentation

- [Agent Creation Guide](agents/docs/AGENT_CREATION.md)
- [Agent Platform README](agents/README.md)
- [Exchange API Documentation](exchange/docs/)
