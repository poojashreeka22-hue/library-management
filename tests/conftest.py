"""Pytest configuration and fixtures."""
import pytest
from fastapi.testclient import TestClient

from app.crud import repo
from app.main import app


@pytest.fixture(autouse=True)
def reset_database():
    """Ensure repository state is reset before each individual test runs."""
    repo.reset()
    yield
    repo.reset()


@pytest.fixture
def client():
    """Provide a TestClient instance for sending requests to the app."""
    return TestClient(app)
