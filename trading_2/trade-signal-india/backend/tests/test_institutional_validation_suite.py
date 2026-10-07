"""
Comprehensive Institutional Validation & Risk Test Suite:
Tests MetadataProvider, Historical Option Chain Replay, Portfolio Greeks & 4-Tier Kill Switch,
Walk Forward Efficiency (WFE), and Slippage/Spread Stress Testing.
"""

import pytest
from app.data.metadata_provider import MetadataProvider
from app.validation.option_chain_replay import HistoricalOptionChainReplayEngine, OptionQuote
from app.risk.portfolio_risk import PortfolioRiskManager
from app.evaluation.walk_forward import QuantitativeEdgeValidator


def test_metadata_provider_lot_sizes_and_weights():
    """Validates dynamic lot sizing and constituent weightings."""
    assert MetadataProvider.get_lot_size("NIFTY") == 65
    assert MetadataProvider.get_lot_size("BANKNIFTY") == 30
    assert MetadataProvider.get_lot_size("FINNIFTY") == 60

    weights = MetadataProvider.get_constituent_weights()
    assert "HDFCBANK" in weights
    assert "RELIANCE" in weights
    assert weights["HDFCBANK"] > weights["RELIANCE"]


def test_ivr_and_ivp_calculation():
    """Validates IV Rank and IV Percentile calculations."""
    iv_history = [12.0, 13.5, 14.0, 15.0, 16.5, 18.0, 20.0]
    res = HistoricalOptionChainReplayEngine.calculate_ivr_ivp(current_iv=16.0, iv_history_52w=iv_history)

    assert 0.0 <= res["ivr"] <= 100.0
    assert 0.0 <= res["ivp"] <= 100.0
    assert res["52w_low_iv"] == 12.0
    assert res["52w_high_iv"] == 20.0


def test_option_chain_replay_execution_simulation():
    """Validates realistic fill and implementation shortfall simulation."""
    engine = HistoricalOptionChainReplayEngine(symbol="NIFTY", base_slippage_factor=0.25)
    quote = OptionQuote(
        timestamp="2026-10-05T09:30:00Z",
        symbol="NIFTY26OCT25000CE",
        strike=25000.0,
        option_type="CE",
        expiry="2026-10-29",
        ltp=120.0,
        bid=119.5,
        ask=120.5,
        spread_pct=0.83,
        volume=5000,
        oi=50000,
        oi_change=1200,
        iv=14.5,
        delta=0.52,
        gamma=0.0012,
        theta=-8.5,
        vega=6.2
    )

    sim = engine.simulate_order_execution(
        direction="BUY",
        option_quote=quote,
        order_quantity=65,
        urgency="AGGRESSIVE_CHASE",
        stress_slippage_multiplier=1.0
    )

    assert sim.fill_status == "FILLED"
    assert sim.fill_price >= quote.bid
    assert sim.spread_points == 1.0
    assert sim.implementation_shortfall_points > 0


def test_portfolio_greeks_and_4_tier_kill_switch():
    """Validates portfolio risk aggregation and 4-tier kill switch state transitions."""
    manager = PortfolioRiskManager(max_daily_loss_rupees=5000.0)

    # 1. Test Portfolio Greeks aggregation
    positions = [
        {"symbol": "NIFTY26OCT25000CE", "quantity": 65, "direction": "BUY", "delta": 0.50, "gamma": 0.001, "theta_day": -10.0, "vega": 5.0},
        {"symbol": "BANKNIFTY26OCT52000CE", "quantity": 30, "direction": "BUY", "delta": 0.48, "gamma": 0.0008, "theta_day": -15.0, "vega": 8.0}
    ]
    greeks = manager.calculate_portfolio_greeks(positions)
    assert greeks.net_delta > 0
    assert greeks.concurrent_positions_count == 2

    # 2. Test GREEN state
    status_green = manager.evaluate_kill_switch(
        current_daily_loss_rupees=500.0,
        open_unrealized_loss_rupees=0.0,
        consecutive_losses=0,
        data_feed_healthy=True
    )
    assert status_green.level == "GREEN"
    assert status_green.size_multiplier == 1.0
    assert status_green.allow_new_entries is True

    # 3. Test YELLOW state (consecutive loss warning)
    status_yellow = manager.evaluate_kill_switch(
        current_daily_loss_rupees=1500.0,
        open_unrealized_loss_rupees=0.0,
        consecutive_losses=2,
        data_feed_healthy=True
    )
    assert status_yellow.level == "YELLOW"
    assert status_yellow.size_multiplier == 0.5

    # 4. Test ORANGE state (3 consecutive losses / 75% max loss)
    status_orange = manager.evaluate_kill_switch(
        current_daily_loss_rupees=3800.0,
        open_unrealized_loss_rupees=0.0,
        consecutive_losses=3,
        data_feed_healthy=True
    )
    assert status_orange.level == "ORANGE"
    assert status_orange.allow_new_entries is False

    # 5. Test RED state (Max loss exceeded -> Emergency Flatten)
    status_red = manager.evaluate_kill_switch(
        current_daily_loss_rupees=5200.0,
        open_unrealized_loss_rupees=0.0,
        consecutive_losses=3,
        data_feed_healthy=True
    )
    assert status_red.level == "RED"
    assert status_red.requires_emergency_flatten is True


def test_walk_forward_efficiency_and_stress_matrix():
    """Validates WFE calculation and multi-parameter stress tests."""
    # Test WFE ratio
    wfe_robust = QuantitativeEdgeValidator.calculate_wfe(train_pf=2.0, test_pf=1.6)
    assert wfe_robust["wfe_ratio"] == 0.8
    assert wfe_robust["is_robust"] is True

    wfe_fragile = QuantitativeEdgeValidator.calculate_wfe(train_pf=3.0, test_pf=1.1)
    assert wfe_fragile["wfe_ratio"] < 0.5
    assert wfe_fragile["is_robust"] is False

    # Test Stress Testing Matrix
    mock_trades = [
        {"net_pnl_after_costs": 1200.0, "statutory_costs": 70.0},
        {"net_pnl_after_costs": -400.0, "statutory_costs": 60.0},
        {"net_pnl_after_costs": 900.0, "statutory_costs": 65.0}
    ] * 5
    matrix = QuantitativeEdgeValidator.run_stress_test_matrix(mock_trades)
    assert len(matrix) == 9 # 3 slippage x 3 spread variations
    assert "stressed_profit_factor" in matrix[0]
