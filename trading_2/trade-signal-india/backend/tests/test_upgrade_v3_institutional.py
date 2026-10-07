"""
Institutional V3 Regression Test Suite:
Validates Order Flow CVD, IV Skew, Position Sizing, Execution Lifecycle, Timezone Standards,
Hard Live Data Veto, and Monte Carlo Calibration.
"""

import pytest
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

from app.core.config import settings
from app.risk.risk_engine import RiskEngine
from app.data.data_quality import DataQualityEngine
from app.indicators.volume_analysis import VolumeAnalysis
from app.options.greeks import calculate_iv_skew, calculate_oi_velocity
from app.broker.execution_adapter import SmartExecutionAdapter, ExecutionLatencyAuditor
from app.strategy.signal_engine import SignalEngine
from app.backtest.monte_carlo import MonteCarloEngine
from app.paper.paper_trader import PaperTradingEngine, PaperPosition


def test_fixed_fractional_position_sizing():
    """Validates that risk engine rejects trades where 1 lot exceeds allowed risk budget."""
    # Account capital: 100,000, Risk %: 1% (₹1,000 max risk)
    # Stop distance: 20 points, Lot size: 65 -> Risk per lot = ₹1,300 (Exceeds ₹1,000 budget!)
    res_rejected = RiskEngine.calculate_position_size(
        account_equity=100000.0,
        risk_pct_per_trade=0.01,
        entry_price=25000.0,
        stop_loss=24980.0,
        lot_size=65
    )
    assert not res_rejected.allowed
    assert res_rejected.lots == 0
    assert "exceeds allowed risk budget" in res_rejected.reason

    # Account capital: 500,000, Risk %: 1% (₹5,000 max risk)
    # Stop distance: 20 points, Lot size: 65 -> Risk per lot = ₹1,300 -> 3 lots (₹3,900 risk)
    res_accepted = RiskEngine.calculate_position_size(
        account_equity=500000.0,
        risk_pct_per_trade=0.01,
        entry_price=25000.0,
        stop_loss=24980.0,
        lot_size=65
    )
    assert res_accepted.allowed
    assert res_accepted.lots == 3
    assert res_accepted.quantity == 195
    assert res_accepted.actual_risk_rupees == 3900.0


def test_trailing_stop_loss_to_breakeven():
    """Validates stop-loss trails to entry price upon achieving Target 1."""
    entry = 25000.0
    sl = 24970.0
    t1 = 25045.0

    # Below target 1 -> keep SL
    new_sl = RiskEngine.update_trailing_stop("BUY", entry, 25030.0, sl, t1)
    assert new_sl == sl

    # Hit target 1 -> trail SL to Entry (25000.0)
    new_sl_trailed = RiskEngine.update_trailing_stop("BUY", entry, 25050.0, sl, t1)
    assert new_sl_trailed == entry


def test_data_quality_microstructure_checks():
    """Validates future timestamps, out-of-order ticks, and staleness."""
    dq = DataQualityEngine(max_allowed_staleness_seconds=5, max_latency_threshold_ms=300.0)
    now = datetime.now(timezone.utc)

    # Fresh tick
    res_fresh = dq.check_freshness(now)
    assert res_fresh.is_healthy
    assert res_fresh.status in {"HEALTHY", "HIGH_LATENCY_WARNING"}

    # Future timestamp (clock skew > 2s)
    future_time = now + timedelta(seconds=10)
    res_future = dq.check_freshness(future_time)
    assert not res_future.is_healthy
    assert res_future.status == "DATA_FUTURE_TIMESTAMP"

    # Stale tick (> 5s)
    past_time = now - timedelta(seconds=10)
    res_stale = dq.check_freshness(past_time)
    assert not res_stale.is_healthy
    assert res_stale.status == "DATA_STALE"


def test_volume_delta_and_cvd():
    """Validates Cumulative Volume Delta calculation and order flow alignment."""
    data = {
        "open": [25000, 25010, 25020, 25030],
        "high": [25015, 25025, 25035, 25045],
        "low": [24995, 25005, 25015, 25025],
        "close": [25010, 25020, 25030, 25040],
        "volume": [1000, 1200, 1500, 2000]
    }
    df = pd.DataFrame(data)
    analyzed = VolumeAnalysis.analyze(df)

    assert "volume_delta" in analyzed.columns
    assert "cum_volume_delta" in analyzed.columns
    assert "cvd_aligned_buy" in analyzed.columns
    assert analyzed["cum_volume_delta"].iloc[-1] > 0
    assert bool(analyzed["cvd_aligned_buy"].iloc[-1]) is True


def test_iv_skew_and_oi_velocity():
    """Validates options skew and OI velocity metrics."""
    chain = [
        {"strike": 24750, "ce_iv": 14.0, "pe_iv": 17.5}, # OTM Put (~1% below 25000)
        {"strike": 25000, "ce_iv": 14.5, "pe_iv": 14.5}, # ATM
        {"strike": 25250, "ce_iv": 13.0, "pe_iv": 14.0}, # OTM Call (~1% above 25000)
    ]
    skew_res = calculate_iv_skew(chain, spot_price=25000.0)
    assert skew_res["iv_skew"] > 0 # Put IV higher than Call IV (Hedging demand)
    assert skew_res["skew_sentiment"] == "BEARISH_HEDGING"

    # OI Velocity
    vel = calculate_oi_velocity(current_oi=50000, prev_oi=40000, dt_seconds=60, volume=10000)
    assert vel > 0
    assert vel == round((10000 / 60) * (10000 / 1000.0), 2)


def test_live_data_hard_veto_on_missing_options():
    """Validates that SignalEngine issues a HARD VETO in LIVE_DATA mode when option data is unavailable."""
    engine = SignalEngine(score_threshold=70)
    engine.require_live_data = True # Simulate live mode guard

    # Create synthetic candles
    dates = pd.date_range("2026-10-05 09:15:00", periods=30, freq="5min")
    df_5m = pd.DataFrame({
        "open": np.linspace(25000, 25100, 30),
        "high": np.linspace(25010, 25110, 30),
        "low": np.linspace(24990, 25090, 30),
        "close": np.linspace(25005, 25105, 30),
        "volume": [1000] * 30,
        "vwap": np.linspace(25000, 25100, 30)
    }, index=dates)

    candles = {"5m": df_5m, "15m": df_5m, "10m": df_5m, "3m": df_5m, "1m": df_5m}

    # Pass option_snapshot=None while require_live_data=True
    sig = engine.process(symbol="NIFTY", tf_candles=candles, is_market_open=True, is_data_healthy=True, option_snapshot=None)
    assert sig.direction == "WAIT"
    assert any("HARD_VETO: Live option chain unavailable" in r for r in sig.reasons)


def test_smart_execution_adapter_simulated():
    """Validates limit order creation with latency auditing."""
    adapter = SmartExecutionAdapter(broker=None)
    now = datetime.now(timezone.utc)
    order = pytest.importorskip("asyncio").run(
        adapter.execute_smart_order(
            symbol="NIFTY26OCT25000CE",
            direction="BUY",
            limit_price=120.50,
            quantity=65,
            signal_timestamp=now
        )
    )
    assert order["status"] == "FILLED"
    assert order["mode"] == "SIMULATED"
    assert "latency_audit" in order
    assert order["latency_audit"]["status"] == "PASS"


def test_monte_carlo_resampling():
    """Validates Monte Carlo simulation engine and score calibration."""
    sample_pnls = [500.0, 1200.0, -400.0, 800.0, -350.0, 1500.0, 600.0, -300.0] * 10
    mc_res = MonteCarloEngine.run_monte_carlo(sample_pnls, iterations=200, slippage_penalty_rupees_per_trade=50.0)

    assert mc_res.iterations == 200
    assert mc_res.positive_runs_pct > 80.0
    assert mc_res.p50_net_pnl_rupees > 0

    # Calibration test
    mock_trades = [
        {"score": 92, "net_pnl_after_costs": 1500.0, "pnl_points": 25.0},
        {"score": 85, "net_pnl_after_costs": 800.0, "pnl_points": 12.0},
        {"score": 75, "net_pnl_after_costs": -400.0, "pnl_points": -6.0},
        {"score": 65, "net_pnl_after_costs": -600.0, "pnl_points": -10.0}
    ]
    cal = MonteCarloEngine.calibrate_score_buckets(mock_trades)
    assert len(cal) == 5
    bucket_90_100 = next(b for b in cal if b.bucket_label == "90-100")
    assert bucket_90_100.total_trades == 1
    assert bucket_90_100.win_rate_pct == 100.0
