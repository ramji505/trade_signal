import pytest
from app.costs.statutory_charges import calculate_option_trade_costs


def test_statutory_charges_calculation():
    # Buy at ₹100, Sell at ₹130, current NIFTY lot = 65
    # Quantity = 65
    # Buy Turnover = 6500, Sell Turnover = 8450, Total = 14950
    # Gross PnL = 30 * 65 = ₹1950
    res = calculate_option_trade_costs(
        entry_premium=100.0,
        exit_premium=130.0,
        lot_size=65,
        lots=1,
        brokerage_per_order=20.0
    )
    
    assert res["quantity"] == 65
    assert res["gross_pnl"] == 1950.0
    assert res["brokerage"] == 40.0
    # STT: 0.15% of 8450 = 12.675 -> 12.68
    assert abs(res["stt"] - 12.68) < 0.1
    # Stamp duty: 0.003% of 6500 = 0.195 -> 0.20
    assert abs(res["stamp_duty"] - 0.23) < 0.1
    # GST: 18% of (40 + exchange + sebi)
    assert res["gst"] > 0
    assert res["total_costs"] > 55.0
    assert res["net_pnl"] == round(res["gross_pnl"] - res["total_costs"], 2)
    assert res["net_pnl"] > 1800.0


def test_losing_trade_costs():
    # Buy at ₹100, Sell at ₹70
    res = calculate_option_trade_costs(
        entry_premium=100.0,
        exit_premium=70.0,
        lot_size=65,
        lots=1
    )
    assert res["gross_pnl"] == -1950.0
    # Net PnL must be strictly worse than gross PnL due to statutory costs
    assert res["net_pnl"] < -1950.0
