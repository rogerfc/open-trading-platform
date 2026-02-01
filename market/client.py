"""HTTP clients for Exchange and Agent Platform APIs."""

from typing import Any

import httpx


class APIError(Exception):
    """API request error."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class ExchangeClient:
    """Client for the Exchange API."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        api_key: str | None = None,
        **kwargs,
    ) -> Any:
        """Make an HTTP request."""
        headers = kwargs.pop("headers", {})
        if api_key:
            headers["X-API-Key"] = api_key

        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.request(method, path, headers=headers, **kwargs)

        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise APIError(response.status_code, detail)

        if response.status_code == 204:
            return None
        return response.json()

    def health(self) -> dict:
        """Check health status."""
        return self._request("GET", "/health")

    # Company endpoints
    def list_companies(self) -> list[dict]:
        """List all companies."""
        response = self._request("GET", "/api/v1/companies")
        # Handle wrapped response format
        if isinstance(response, dict) and "companies" in response:
            return response["companies"]
        return response

    def get_company(self, ticker: str) -> dict:
        """Get company details."""
        return self._request("GET", f"/api/v1/companies/{ticker}")

    def create_company(
        self,
        ticker: str,
        name: str,
        total_shares: int,
        float_shares: int,
        ipo_price: float = 100.0,
    ) -> dict:
        """Create a new company."""
        return self._request(
            "POST",
            "/admin/companies",
            json={
                "ticker": ticker,
                "name": name,
                "total_shares": total_shares,
                "float_shares": float_shares,
                "ipo_price": ipo_price,
            },
        )

    # Account endpoints
    def list_accounts(self) -> list[dict]:
        """List all accounts."""
        return self._request("GET", "/admin/accounts")

    def get_account(self, api_key: str) -> dict:
        """Get account details for the authenticated user."""
        return self._request("GET", "/api/v1/account", api_key=api_key)

    def create_account(self, account_id: str, initial_cash: float = 0.0) -> dict:
        """Create a new account."""
        return self._request(
            "POST",
            "/admin/accounts",
            json={"account_id": account_id, "initial_cash": initial_cash},
        )

    # Holdings endpoints
    def get_holdings(self, api_key: str) -> list[dict]:
        """Get holdings for the authenticated user."""
        return self._request("GET", "/api/v1/holdings", api_key=api_key)

    # Order endpoints
    def list_orders(self, api_key: str, status: str | None = None) -> list[dict]:
        """List orders for the authenticated user."""
        params = {}
        if status:
            params["status"] = status
        return self._request("GET", "/api/v1/orders", api_key=api_key, params=params)

    def get_order(self, order_id: str, api_key: str) -> dict:
        """Get order details."""
        return self._request("GET", f"/api/v1/orders/{order_id}", api_key=api_key)

    def create_order(
        self,
        api_key: str,
        ticker: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float | None = None,
    ) -> dict:
        """Place a new order."""
        data = {
            "ticker": ticker,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
        }
        if price is not None:
            data["price"] = price
        return self._request("POST", "/api/v1/orders", api_key=api_key, json=data)

    def cancel_order(self, order_id: str, api_key: str) -> dict:
        """Cancel an order."""
        return self._request("DELETE", f"/api/v1/orders/{order_id}", api_key=api_key)

    # Order book endpoints
    def get_orderbook(self, ticker: str, depth: int = 10) -> dict:
        """Get order book for a ticker."""
        return self._request("GET", f"/api/v1/orderbook/{ticker}", params={"depth": depth})

    # Trade endpoints
    def list_trades(self, ticker: str, limit: int = 20) -> list[dict]:
        """List recent trades for a ticker."""
        return self._request("GET", f"/api/v1/trades/{ticker}", params={"limit": limit})

    # Portfolio endpoints
    def get_portfolio_summary(self, api_key: str) -> dict:
        """Get portfolio summary (total value, P/L, etc.)."""
        return self._request("GET", "/api/v1/portfolio/summary", api_key=api_key)

    def get_portfolio_holdings(self, api_key: str) -> dict:
        """Get portfolio holdings with P/L for each position."""
        return self._request("GET", "/api/v1/portfolio/holdings", api_key=api_key)

    # Admin endpoints
    def reset(self) -> dict:
        """Reset the exchange database."""
        return self._request("POST", "/admin/reset")


class AgentPlatformClient:
    """Client for the Agent Platform API."""

    def __init__(self, base_url: str = "http://localhost:8001", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make an HTTP request."""
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.request(method, path, **kwargs)

        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise APIError(response.status_code, detail)

        if response.status_code == 204:
            return None
        return response.json()

    def health(self) -> dict:
        """Check health status."""
        return self._request("GET", "/health")

    # Strategy endpoints
    def list_strategies(self) -> list[dict]:
        """List available strategies."""
        return self._request("GET", "/strategies")

    def get_strategy(self, strategy_id: str) -> dict:
        """Get strategy details."""
        return self._request("GET", f"/strategies/{strategy_id}")

    def validate_strategy(
        self,
        strategy_type: str,
        strategy_params: dict | None = None,
        strategy_source: str | None = None,
    ) -> dict:
        """Validate a strategy configuration."""
        data = {"strategy_type": strategy_type}
        if strategy_params:
            data["strategy_params"] = strategy_params
        if strategy_source:
            data["strategy_source"] = strategy_source
        return self._request("POST", "/strategies/validate", json=data)

    # Agent endpoints
    def list_agents(self, status: str | None = None) -> list[dict]:
        """List all agents."""
        params = {}
        if status:
            params["status_filter"] = status
        response = self._request("GET", "/agents", params=params)
        return response.get("agents", [])

    def get_agent(self, agent_id: str) -> dict:
        """Get agent details."""
        return self._request("GET", f"/agents/{agent_id}")

    def create_agent(
        self,
        name: str,
        api_key: str,
        strategy_type: str,
        exchange_url: str = "http://localhost:8000",
        strategy_params: dict | None = None,
        strategy_source: str | None = None,
        interval_seconds: float = 5.0,
    ) -> dict:
        """Create a new agent."""
        data = {
            "name": name,
            "api_key": api_key,
            "exchange_url": exchange_url,
            "strategy_type": strategy_type,
            "strategy_params": strategy_params or {},
            "interval_seconds": interval_seconds,
        }
        if strategy_source:
            data["strategy_source"] = strategy_source
        return self._request("POST", "/agents", json=data)

    def start_agent(self, agent_id: str) -> dict:
        """Start an agent."""
        return self._request("POST", f"/agents/{agent_id}/start")

    def stop_agent(self, agent_id: str) -> dict:
        """Stop an agent."""
        return self._request("POST", f"/agents/{agent_id}/stop")

    def delete_agent(self, agent_id: str) -> None:
        """Delete an agent."""
        return self._request("DELETE", f"/agents/{agent_id}")

    # Admin endpoints
    def reset(self) -> dict:
        """Reset the agent platform database."""
        return self._request("POST", "/admin/reset")
