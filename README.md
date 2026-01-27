# Stock Exchange Simulation

A complete stock exchange simulation with three independent components.

## Components

| Directory | Description | Port |
|-----------|-------------|------|
| `exchange/` | Stock exchange API server | 8000 |
| `agents/` | Autonomous trading agent platform | 8001 |
| `observability/` | Grafana + Prometheus + Loki stack | 3000 |

## Quick Start

```bash
# Build and run exchange only
docker compose up -d exchange

# Run with agent platform
docker compose --profile agents up -d

# Run with observability stack
docker compose --profile observability up -d

# Run everything
docker compose --profile agents --profile observability up -d
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│ Agent Platform  │────▶│    Exchange     │
│   (port 8001)   │     │   (port 8000)   │
└─────────────────┘     └────────┬────────┘
                                 │
                                 │ OTLP
                                 ▼
                        ┌─────────────────┐
                        │  Observability  │
                        │  (port 3000)    │
                        └─────────────────┘
```

## Development

Each component can be run independently:

```bash
# Exchange
cd exchange
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# Agents
cd agents
pip install -r requirements.txt
uvicorn agentplatform.main:app --port 8001

# Observability (requires Docker)
docker compose --profile observability up -d
```

## Documentation

- Exchange API: `exchange/docs/`
- Agents usage: `agents/README.md`
- Market health metrics: `exchange/docs/MARKET_HEALTH.md`
