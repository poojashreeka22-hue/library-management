"""Tests for main application endpoints."""
from fastapi import status


def test_root_endpoint(client):
    """Test the GET / root endpoint returns 200 OK and expected welcome payload."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["message"] == "Welcome to the FastAPI Service!"
    assert data["status"] == "online"
    assert "docs_url" in data


def test_health_check_endpoint(client):
    """Test the GET /health endpoint returns healthy status and version."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"
    assert data["service"] == "Item Catalog Service"
