import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
    assert data["app"] == "TradeSignal India"
    assert data["mode"] == "SIGNAL_ONLY"


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["order_execution"] is False
    assert "disclaimer" in data


def test_market_status_endpoint():
    response = client.get("/market/status")
    assert response.status_code == 200
    data = response.json()
    assert data["instrument"] == "NIFTY"
    assert data["status"] == "OPEN"
    assert data["data_quality"] == "HEALTHY"


def test_current_signal_endpoint():
    response = client.get("/signals/current")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "NIFTY"
    assert data["direction"] in ["BUY", "SELL", "WAIT"]


def test_performance_endpoint():
    response = client.get("/performance")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "INSUFFICIENT DATA"
    assert "15m" in data["horizons"]
    assert "20m" in data["horizons"]
