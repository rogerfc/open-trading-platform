# Docker Setup

## Quick Start

```bash
# Build the exchange image
docker compose build

# Exchange only
docker compose up -d

# Exchange + observability (Grafana, Prometheus, Loki)
docker compose --profile observability up -d
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| exchange | 8000 | Stock Exchange API |
| grafana | 3000 | Dashboards (admin/admin) |
| prometheus | 9090 | Metrics storage |
| loki | 3100 | Logs storage |
| alloy | 4318 | OTLP collector |

## Test Basic Functionality

```bash
# Health check
curl http://localhost:8000/health

# Create a company with IPO (admin)
# This creates treasury, allocates float shares, and places sell order at IPO price
curl -X POST http://localhost:8000/admin/companies \
  -H "Content-Type: application/json" \
  -d '{"ticker": "TEST", "name": "Test Corp", "total_shares": 10000, "float_shares": 1000, "ipo_price": 50}'

# Create a trader account (admin) - save the api_key from response
curl -X POST http://localhost:8000/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{"account_id": "alice", "initial_cash": 10000}'

# Place an order (use api_key from account creation)
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-api-key>" \
  -d '{"ticker": "TEST", "side": "BUY", "order_type": "LIMIT", "quantity": 10, "price": 50}'
```

## View Logs in Grafana

1. Open http://localhost:3000
2. Go to Explore → Select Loki
3. Query: `{service_name="stock-exchange"}`

## Stop

```bash
docker compose --profile observability down
```
