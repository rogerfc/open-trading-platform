# Stock Exchange Simulation

A complete stock exchange simulation with autonomous trading agents, deployed on Kubernetes.

## Components

| Directory | Description |
|-----------|-------------|
| `exchange/` | Stock exchange API server |
| `agents/` | Autonomous trading agent platform |
| `k8s/` | Kubernetes manifests |
| `market/` | Unified CLI for all operations |
| `scenario/` | Scenario definitions and management |

## Quick Start

### Prerequisites

```bash
# Start Colima with Kubernetes and network address
colima start --kubernetes --network-address

# Verify cluster
kubectl cluster-info

# PostgreSQL running on host
psql -h localhost -U postgres -c "SELECT 1"
```

### 1. Create Databases and Users

```sql
CREATE DATABASE exchange;
CREATE DATABASE agents;
CREATE USER exchange_user WITH PASSWORD 'your_password';
CREATE USER agents_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE exchange TO exchange_user;
GRANT ALL PRIVILEGES ON DATABASE agents TO agents_user;
\c exchange
GRANT ALL ON SCHEMA public TO exchange_user;
\c agents
GRANT ALL ON SCHEMA public TO agents_user;
```

### 2. Build Images

```bash
docker build -t stockexchange/exchange:latest ./exchange
docker build -t stockexchange/agents:latest ./agents
```

### 3. Deploy to Kubernetes

```bash
# Apply Gateway API and NGINX Gateway Fabric CRDs
kubectl apply --server-side -f k8s/gateway/crds.yaml
kubectl apply -f k8s/gateway/nginx-crds.yaml

# Deploy NGINX Gateway Fabric
kubectl apply -f k8s/gateway/nginx-gateway-fabric.yaml

# Create namespaces
kubectl apply -f k8s/namespaces.yaml

# Create secrets (not stored in git)
kubectl create secret generic exchange-db -n exchange \
  --from-literal=url='postgresql+asyncpg://exchange_user:PASSWORD@host.docker.internal:5432/exchange'

kubectl create secret generic agents-db -n agents \
  --from-literal=url='postgresql+asyncpg://agents_user:PASSWORD@host.docker.internal:5432/agents'

# Deploy Gateway and applications
kubectl apply -f k8s/gateway/gateway.yaml
kubectl apply -f k8s/observability/
kubectl apply -f k8s/exchange/
kubectl apply -f k8s/agents/
```

### 4. Configure Host Access

Get the Gateway IP:
```bash
kubectl get svc -n nginx-gateway nginx-gateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Add to `/etc/hosts`:
```
<GATEWAY_IP> exchange.local agents.local
```

### 5. Verify

```bash
curl http://exchange.local/health
curl http://agents.local/health
```

### 6. Load a Scenario

```bash
python -m market.cli scenario load scenario/scenarios/basic_market.yaml
python -m market.cli scenario status
```

## Architecture

```
                    ┌─────────────────┐
                    │   Market CLI    │
                    └────────┬────────┘
                             │ HTTP
                             ▼
┌──────────────────────────────────────────────────────┐
│                    Kubernetes                         │
│  ┌─────────────────────────────────────────────────┐ │
│  │              NGINX Gateway Fabric                │ │
│  │         exchange.local  agents.local             │ │
│  └──────────────┬─────────────────┬────────────────┘ │
│                 │                 │                   │
│                 ▼                 ▼                   │
│  ┌─────────────────┐   ┌─────────────────┐          │
│  │    Exchange     │◀──│  Agent Platform │          │
│  │   (namespace)   │   │   (namespace)   │          │
│  └────────┬────────┘   └────────┬────────┘          │
│           │                     │                    │
│           │ OTLP                │ OTLP               │
│           ▼                     ▼                    │
│  ┌─────────────────────────────────────────────────┐ │
│  │                    Alloy                         │ │
│  │             (observability namespace)            │ │
│  └──────────────────────┬──────────────────────────┘ │
└─────────────────────────┼────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │    Grafana Cloud      │
              │  (metrics & logs)     │
              └───────────────────────┘

External:
  - PostgreSQL on host (host.docker.internal:5432)
  - Grafana Cloud for dashboards
```

## Kubernetes Structure

```
k8s/
├── namespaces.yaml           # exchange, agents, observability namespaces
├── gateway/
│   ├── crds.yaml             # Gateway API CRDs (official)
│   ├── nginx-crds.yaml       # NGINX Gateway Fabric CRDs
│   ├── nginx-gateway-fabric.yaml  # NGINX controller
│   └── gateway.yaml          # Gateway resource
├── exchange/
│   ├── deployment.yaml       # Exchange API
│   ├── service.yaml
│   ├── httproute.yaml        # Routes exchange.local
│   └── referencegrant.yaml
├── agents/
│   ├── deployment.yaml       # Agent Platform
│   ├── service.yaml
│   ├── httproute.yaml        # Routes agents.local
│   └── referencegrant.yaml
└── observability/
    ├── configmap.yaml        # Alloy config for Grafana Cloud
    ├── deployment.yaml
    └── service.yaml
```

Secrets are managed imperatively (not in git):
- `exchange-db` - PostgreSQL connection for exchange
- `agents-db` - PostgreSQL connection for agents
- `grafana-cloud` - Grafana Cloud API credentials (optional)

## Market CLI

The `market` CLI provides unified access to all operations:

```bash
python -m market.cli [OPTIONS] <resource> <verb> [ARGS]
```

### Global Options

| Option | Description |
|--------|-------------|
| `-e, --exchange-url` | Exchange API URL (default: http://exchange.local) |
| `-a, --agents-url` | Agent Platform URL (default: http://agents.local) |
| `-o, --output` | Output format: table, json, yaml |

### Commands

```bash
# Service status
python -m market.cli status

# Companies
python -m market.cli company list
python -m market.cli company create TECH "TechCorp" --total-shares 1000000 --float-shares 1000 --ipo-price 100

# Accounts
python -m market.cli account list
python -m market.cli account create alice --cash 50000

# Orders (requires API key)
python -m market.cli order create --api-key sk_xxx --ticker TECH --side BUY --type LIMIT --quantity 10 --price 99.50

# Order book & trades
python -m market.cli orderbook show TECH --depth 10
python -m market.cli trade list TECH --limit 20

# Agents
python -m market.cli agent list
python -m market.cli agent create "My Bot" --api-key sk_xxx --strategy random --interval 5
python -m market.cli agent start <agent-id>
python -m market.cli agent stop <agent-id>

# Scenarios
python -m market.cli scenario list
python -m market.cli scenario load scenario/scenarios/basic_market.yaml
python -m market.cli scenario status

# Reset databases
python -m market.cli reset all
```

## Scenarios

Scenarios define a complete trading environment in YAML:

```yaml
name: "Basic Market"
description: "Simple market with two companies and one trader"

exchange:
  url: "http://exchange.local"

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
  url: "http://agents.local"

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

## API Documentation

- **Exchange**: http://exchange.local/docs
- **Agent Platform**: http://agents.local/docs

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

## Development

### Running Tests

```bash
pytest exchange/tests/
pytest agents/tests/
```

## Documentation

- [Agent Creation Guide](agents/docs/AGENT_CREATION.md)
- [Agent Platform README](agents/README.md)
- [Exchange API Documentation](exchange/docs/)
