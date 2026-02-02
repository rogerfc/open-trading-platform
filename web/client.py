"""Web client for Exchange API.

Wraps the ExchangeClient from market.client for use in the web application.
"""

import os

from lib.client import ExchangeClient, APIError

# Configuration from environment
EXCHANGE_URL = os.getenv("EXCHANGE_URL", "http://localhost:8000")

# Global client instance
_client: ExchangeClient | None = None


def get_client() -> ExchangeClient:
    """Get the ExchangeClient instance."""
    global _client
    if _client is None:
        _client = ExchangeClient(base_url=EXCHANGE_URL)
    return _client


__all__ = ["get_client", "ExchangeClient", "APIError", "EXCHANGE_URL"]
