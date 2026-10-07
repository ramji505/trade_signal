import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

from app.indicators.technical import TechnicalIndicators
from app.indicators.volume_analysis import VolumeAnalysis
from app.data.candle_builder import CandleBuilder
from app.strategy.market_structure import MarketStructure
from app.risk.risk_engine import RiskEngine
from app.evaluation.signal_evaluator import SignalEvaluator


def create_sample_ohlcv(count=60, start_price=25000.0, trend="UP"):
    timestamps = [datetime.now(timezone.utc) - timedelta(minutes=count - i) for i in range(count)]
    rows = []
    p = start_price
    for i, ts in enumerate(timestamps):
        drift = 5.0 if trend == "UP" else (-5.0 if trend == "DOWN" else 0.0)
        p += drift + np.random.uniform(-2.0, 2.0)
        high = p + 4.0
        low = p - 4.0
        rows.append({
            "timestamp": ts,
            "open": p - 1.0,
            "high": high,
            "low": low,
            "close": p,
            "volume": 5000 + i * 50
        })
    df = pd.DataFrame(rows).set_index("timestamp")
    return df


def test_technical_indicators_calculation():
    df = create_sample_ohlcv(50)
    enriched = TechnicalIndicators.compute_all(df)
    
    assert "ema_9" in enriched.columns
    assert "ema_21" in enriched.columns
    assert "ema_50" in enriched.columns
    assert "rsi_14" in enriched.columns
    assert "vwap" in enriched.columns
    assert "atr_14" in enriched.columns

    # Verify RSI is within bounds
    assert (enriched['rsi_14'] >= 0.0).all()
    assert (enriched['rsi_14'] <= 100.0).all()


def test_volume_analysis():
    df = create_sample_ohlcv(50)
    vol_df = VolumeAnalysis.analyze(df)
    
    assert "rvol" in vol_df.columns
    assert "volume_expansion" in vol_df.columns
    assert (vol_df['rvol'] > 0).all()


def test_candle_builder_resampling():
    df_1m = create_sample_ohlcv(30)
    df_5m = CandleBuilder.resample_candles(df_1m, "5m")
    
    assert len(df_5m) == 6
    assert "open" in df_5m.columns
    assert "high" in df_5m.columns
    assert "low" in df_5m.columns
    assert "close" in df_5m.columns
    assert "volume" in df_5m.columns


def test_risk_engine_atr_calculation():
    engine = RiskEngine(atr_multiplier=1.5, min_rr=1.5)
    params = engine.calculate_levels(
        direction="BUY",
        current_price=25000.0,
        atr_value=20.0
    )
    
    # 20 * 1.5 = 30 points risk
    assert params.risk_points == 30.0
    assert params.stop_loss == 24970.0
    assert params.target_1 == 25045.0  # 1:1.5 -> +45 pts
    assert params.target_2 == 25060.0  # 1:2.0 -> +60 pts
    assert params.risk_reward_ratio >= 1.5
    assert params.is_valid_risk is True


def test_signal_evaluation_sl_hit_first_is_loss():
    """
    CRITICAL TEST: If price hits Stop Loss first and later rallies to Target,
    the trade result MUST be classified as STOP_HIT (LOSS), not WIN.
    """
    # Create future path where price drops to hit SL, then rallies to target
    entry = 25000.0
    sl = 24970.0
    tgt = 25050.0

    future_candles = [
        {"high": 25005, "low": 24985, "close": 24990}, # +1 min
        {"high": 24995, "low": 24965, "close": 24972}, # +2 min: LOW 24965 hits SL (24970)
        {"high": 25060, "low": 24980, "close": 25055}, # +3 min: reaches target 25050
    ]
    df_future = pd.DataFrame(future_candles)

    report = SignalEvaluator.evaluate_path(
        signal_id="TEST-001",
        symbol="NIFTY",
        direction="BUY",
        entry_price=entry,
        stop_loss=sl,
        target_1=tgt,
        target_2=tgt + 20,
        df_1m_future=df_future
    )

    # Result at horizon 3m and final must be STOP_HIT
    res_3m = [h for h in report.horizon_evaluations if h.horizon_minutes == 3][0]
    assert res_3m.result == "STOP_HIT"
    assert report.final_result == "STOP_HIT"
    assert res_3m.points_pnl < 0


def test_signal_evaluation_target_hit_first_is_win():
    """
    CRITICAL TEST: If price hits Target first, the trade result MUST be TARGET_HIT (WIN).
    """
    entry = 25000.0
    sl = 24970.0
    tgt = 25050.0

    future_candles = [
        {"high": 25020, "low": 24995, "close": 25015}, # +1 min
        {"high": 25055, "low": 25010, "close": 25050}, # +2 min: HIGH 25055 hits Target (25050)
        {"high": 25060, "low": 24960, "close": 24965}, # +3 min: drops
    ]
    df_future = pd.DataFrame(future_candles)

    report = SignalEvaluator.evaluate_path(
        signal_id="TEST-002",
        symbol="NIFTY",
        direction="BUY",
        entry_price=entry,
        stop_loss=sl,
        target_1=tgt,
        target_2=tgt + 20,
        df_1m_future=df_future
    )

    res_3m = [h for h in report.horizon_evaluations if h.horizon_minutes == 3][0]
    assert res_3m.result == "TARGET_HIT"
    assert report.final_result == "TARGET_HIT"
    assert res_3m.points_pnl > 0


def test_horizon_isolation_no_state_contamination():
    """
    Verifies that early horizon status does NOT bleed or contaminate later horizons.
    For example: if at +1m, price is in TIMEOUT/NO_DECISIVE_MOVE, and at +3m reaches TARGET_HIT,
    the +1m horizon remains TIMEOUT while +3m is independently TARGET_HIT.
    """
    entry = 25000.0
    sl = 24970.0
    tgt = 25050.0

    future_candles = [
        {"high": 25002, "low": 24998, "close": 25001}, # +1 min: no move
        {"high": 25005, "low": 24995, "close": 25003}, # +2 min: small move
        {"high": 25055, "low": 25000, "close": 25052}, # +3 min: reaches target 25050
    ]
    df_future = pd.DataFrame(future_candles)

    report = SignalEvaluator.evaluate_path(
        signal_id="TEST-003",
        symbol="NIFTY",
        direction="BUY",
        entry_price=entry,
        stop_loss=sl,
        target_1=tgt,
        target_2=tgt + 20,
        df_1m_future=df_future
    )

    res_1m = [h for h in report.horizon_evaluations if h.horizon_minutes == 1][0]
    res_3m = [h for h in report.horizon_evaluations if h.horizon_minutes == 3][0]

    assert res_1m.result == "NO_DECISIVE_MOVE"
    assert res_3m.result == "TARGET_HIT"
    assert report.final_result == "TARGET_HIT"

