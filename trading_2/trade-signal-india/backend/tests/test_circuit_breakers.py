import pytest
from app.risk.circuit_breakers import CircuitBreakerEngine


def test_circuit_breaker_loss_limit():
    cb = CircuitBreakerEngine(max_daily_loss=3000.0, max_consecutive_losses=3)
    
    can_trade, msg = cb.can_generate_signal("10:00", 10)
    assert can_trade is True
    
    # Record a ₹3500 loss
    cb.record_trade_result(-3500.0)
    assert cb.is_circuit_tripped is True
    
    can_trade, msg = cb.can_generate_signal("10:30", 20)
    assert can_trade is False
    assert "CIRCUIT_BREAKER_ACTIVE" in msg


def test_consecutive_losses_lockout():
    cb = CircuitBreakerEngine(max_daily_loss=10000.0, max_consecutive_losses=3)
    
    cb.record_trade_result(-500.0)
    assert cb.is_circuit_tripped is False
    cb.record_trade_result(-400.0)
    assert cb.is_circuit_tripped is False
    cb.record_trade_result(-300.0)
    # 3rd consecutive loss trips the breaker
    assert cb.is_circuit_tripped is True
    
    can_trade, msg = cb.can_generate_signal("11:00", 25)
    assert can_trade is False
    assert "MAX_CONSECUTIVE_LOSSES" in msg


def test_time_in_force_cutoff():
    cb = CircuitBreakerEngine(cutoff_time_str="15:15")
    
    can_trade, msg = cb.can_generate_signal("14:30", 10)
    assert can_trade is True
    
    # 15:20 is after 15:15 intraday square-off cutoff
    can_trade, msg = cb.can_generate_signal("15:20", 30)
    assert can_trade is False
    assert "TIME_IN_FORCE_EXPIRED" in msg
