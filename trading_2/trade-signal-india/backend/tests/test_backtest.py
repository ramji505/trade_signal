import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_candles_api_endpoint():
    response = client.get("/market/candles?timeframe=5m&count=50")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "NIFTY"
    assert data["timeframe"] == "5m"
    assert len(data["candles"]) > 0
    assert "open" in data["candles"][0]
    assert "high" in data["candles"][0]
    assert "low" in data["candles"][0]
    assert "close" in data["candles"][0]
    assert "time" in data["candles"][0]
    assert len(data["ema_9"]) > 0
    assert len(data["vwap"]) > 0


def test_backtest_run_endpoint():
    response = client.post("/backtest/run?candles_count=100&score_threshold=70")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "NIFTY"
    assert "win_rate_pct" in data
    assert "profit_factor" in data
    assert "expectancy_points" in data
    assert "max_drawdown_points" in data
    assert "time_of_day_stats" in data
    assert isinstance(data["trade_log"], list)


def test_backtest_latest_endpoint():
    response = client.get("/backtest/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "NIFTY"
    assert "total_trades" in data
