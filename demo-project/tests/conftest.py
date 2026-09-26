import pytest
from fastapi.testclient import TestClient

from app.database import db
from app.main import app


@pytest.fixture(autouse=True)
def reset_demo_data():
    db.reset()
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
