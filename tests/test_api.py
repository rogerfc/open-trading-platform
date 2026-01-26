"""
Tests for FastAPI endpoints.
"""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    """Test that /health returns status ok."""
    response = await test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
