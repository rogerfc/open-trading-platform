# Container Setup

## Prerequisites

### Container Runtime (macOS)
This project uses [Colima](https://github.com/abiosoft/colima) with containerd and Kubernetes:

```bash
# Install Colima
brew install colima

# Start Colima with Kubernetes
colima start --kubernetes --network-address

# nerdctl is included with Colima
nerdctl version

# Verify cluster
kubectl cluster-info
```

### Container Runtime (Linux)
Install containerd and nerdctl directly, or use Podman as an alternative.

## Build Images

```bash
# Build exchange image
nerdctl build -t stockexchange/exchange:latest ./exchange

# Build agents image
nerdctl build -t stockexchange/agents:latest ./agents
```

## Deploy to Kubernetes

See the main [README](../../README.md) for full deployment instructions.

Quick reference:

```bash
# Create namespaces
kubectl apply -f k8s/namespaces.yaml

# Create secrets (not stored in git)
kubectl create secret generic exchange-db -n exchange \
  --from-literal=url='postgresql+asyncpg://exchange_user:PASSWORD@host.docker.internal:5432/exchange'

# Deploy applications
kubectl apply -f k8s/exchange/
```

## Observability

Observability is handled by Grafana Cloud. The Alloy collector runs in Kubernetes and forwards metrics and logs to Grafana Cloud.

### Grafana Cloud Setup

1. Create a Grafana Cloud account at https://grafana.com/
2. Get your Prometheus and Loki endpoints from the Cloud Portal
3. Create an API key with metrics and logs write permissions

### Configure K8s Secret

Create the `grafana-cloud` secret in the observability namespace:

```bash
kubectl create secret generic grafana-cloud -n observability \
  --from-literal=api-key='YOUR_GRAFANA_CLOUD_API_KEY' \
  --from-literal=prometheus-url='https://prometheus-xxx.grafana.net/api/prom/push' \
  --from-literal=prometheus-user='YOUR_PROMETHEUS_USER_ID' \
  --from-literal=loki-url='https://logs-xxx.grafana.net/loki/api/v1/push' \
  --from-literal=loki-user='YOUR_LOKI_USER_ID'
```

### Deploy Alloy

```bash
kubectl apply -f k8s/observability/
```

### View in Grafana Cloud

1. Log in to your Grafana Cloud instance
2. Explore metrics with Prometheus queries:
   - `exchange_orders_total` - Order counts
   - `exchange_order_book_depth` - Order book depth
3. Explore logs with Loki queries:
   - `{service_name="stock-exchange"}` - Exchange logs
   - `{service_name="agent-platform"}` - Agent logs

## Test Basic Functionality

```bash
# Health check
curl http://exchange.local/health

# Create a company with IPO (admin)
curl -X POST http://exchange.local/admin/companies \
  -H "Content-Type: application/json" \
  -d '{"ticker": "TEST", "name": "Test Corp", "total_shares": 10000, "float_shares": 1000, "ipo_price": 50}'

# Create a trader account (admin) - save the api_key from response
curl -X POST http://exchange.local/admin/accounts \
  -H "Content-Type: application/json" \
  -d '{"account_id": "alice", "initial_cash": 10000}'

# Place an order (use api_key from account creation)
curl -X POST http://exchange.local/orders \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-api-key>" \
  -d '{"ticker": "TEST", "side": "BUY", "order_type": "LIMIT", "quantity": 10, "price": 50}'
```

## Verification

```bash
# Ensure Colima is running with Kubernetes
colima status

# Check cluster
kubectl cluster-info

# Verify exchange pod
kubectl get pods -n exchange

# Check logs
kubectl logs -n exchange -l app=exchange --tail=50
```
