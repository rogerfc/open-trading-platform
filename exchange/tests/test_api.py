"""
Tests for FastAPI endpoints.
"""

import pytest

from app._version import VERSION


@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    """Test that /health returns status ok."""
    response = await test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_version_endpoint(test_client):
    """Test that /api/version returns version information."""
    response = await test_client.get("/api/version")

    assert response.status_code == 200
    data = response.json()
    assert data["version"] == VERSION
    assert data["api_version"] == "v1"
    assert data["min_client_version"] == "0.2.0"
