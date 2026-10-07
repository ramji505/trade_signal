import pytest
from app.risk.circuit_breakers import CircuitBreakerEngine
from app.ml.anomaly_auditor import AnomalyAuditor
import pandas as pd


def test_stale_tick_veto():
    cb = CircuitBreakerEngine(max_stale_seconds=5.0)
    
    # Fresh tick (2 seconds old)
    can_trade, reason = cb.can_generate_signal("10:00", 1, tick_age_seconds=2.0)
    assert can_trade is True
    assert reason == "OK"
    
    # Stale tick (8 seconds old)
    can_trade, reason = cb.can_generate_signal("10:00", 2, tick_age_seconds=8.0)
    assert can_trade is False
    assert "STALE_TICK_VETO" in reason


def test_spread_veto():
    cb = CircuitBreakerEngine(max_spread_pct=0.10)
    
    # Normal spread (0.02%)
    can_trade, reason = cb.can_generate_signal("10:00", 1, bid_ask_spread=5.0, spot_price=25000.0)
    assert can_trade is True
    
    # Abnormal spread (0.20% -> 50 pts on 25000)
    can_trade, reason = cb.can_generate_signal("10:00", 2, bid_ask_spread=50.0, spot_price=25000.0)
    assert can_trade is False
    assert "SPREAD_VETO" in reason


def test_daily_signal_cap():
    cb = CircuitBreakerEngine(max_daily_signals=3, cooldown_bars=0)
    
    for i in range(3):
        can_trade, _ = cb.can_generate_signal("10:00", i)
        assert can_trade is True
        cb.mark_signal_issued(i)
        
    # 4th signal exceeds cap
    can_trade, reason = cb.can_generate_signal("10:30", 4)
    assert can_trade is False
    assert "DAILY_SIGNAL_CAP_EXCEEDED" in reason


def test_anomaly_auditor_detection():
    df = pd.DataFrame([{"close": 25000.0}])
    
    # Clean setup
    clean_audit = AnomalyAuditor.audit_signal(
        direction="BUY",
        df_5m=df,
        pcr_value=1.1,
        rvol=1.5,
        nearest_resistance_dist=80.0
    )
    assert clean_audit["audit_verdict"] == "CLEAN"
    assert clean_audit["is_trap_likely"] is False
    
    # Low volume trap with bearish PCR divergence
    trap_audit = AnomalyAuditor.audit_signal(
        direction="BUY",
        df_5m=df,
        pcr_value=0.55,
        rvol=0.6,
        nearest_resistance_dist=5.0
    )
    assert trap_audit["is_trap_likely"] is True
    assert "LOW_VOLUME_BREAKOUT" in trap_audit["anomaly_flags"]
