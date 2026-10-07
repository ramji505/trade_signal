import pytest
from app.options.greeks import black_scholes_price, calculate_greeks, implied_volatility
from app.options.oi_walls import calculate_max_pain, detect_oi_walls, classify_buildup
from app.options.pcr import calculate_pcr
from app.options.strike_selection import select_optimal_strike, translate_spot_to_option_levels
from app.options.option_chain import generate_synthetic_option_chain


def test_black_scholes_pricing():
    # Spot 25000, Strike 25000 (ATM), 1 day (1/365), r=6.5%, IV=15%
    ce_price = black_scholes_price(25000, 25000, 1/365, 0.065, 0.15, "CE")
    pe_price = black_scholes_price(25000, 25000, 1/365, 0.065, 0.15, "PE")
    
    assert ce_price > 0
    assert pe_price > 0
    # At ATM with short expiry, Call and Put are very close
    assert abs(ce_price - pe_price) < 5.0


def test_greeks_properties():
    greeks_ce = calculate_greeks(25000, 25000, 2/365, 0.065, 0.14, "CE")
    greeks_pe = calculate_greeks(25000, 25000, 2/365, 0.065, 0.14, "PE")
    
    # CE Delta ~ 0.50, PE Delta ~ -0.50
    assert 0.45 <= greeks_ce["delta"] <= 0.60
    assert -0.60 <= greeks_pe["delta"] <= -0.45
    # Gamma should be positive and equal
    assert greeks_ce["gamma"] > 0
    assert greeks_ce["gamma"] == greeks_pe["gamma"]
    # Theta should be negative (time decay)
    assert greeks_ce["theta_day"] < 0
    assert greeks_pe["theta_day"] < 0


def test_iv_solver():
    market_price = 85.0
    iv = implied_volatility(market_price, 25000, 25000, 2/365, 0.065, "CE")
    assert 0.05 < iv < 0.50
    recalc_price = black_scholes_price(25000, 25000, 2/365, 0.065, iv, "CE")
    assert abs(recalc_price - market_price) < 0.5


def test_max_pain_and_walls():
    strikes = [24800, 24900, 25000, 25100, 25200]
    ce_oi = [10000, 20000, 150000, 80000, 50000]
    pe_oi = [60000, 120000, 90000, 15000, 5000]
    
    max_pain = calculate_max_pain(strikes, ce_oi, pe_oi)
    assert max_pain in strikes
    
    chain_rows = [
        {"strike": s, "ce_oi": c, "pe_oi": p, "ce_volume": 1000, "pe_volume": 1000}
        for s, c, p in zip(strikes, ce_oi, pe_oi)
    ]
    walls = detect_oi_walls(chain_rows)
    assert walls["call_wall_strike"] == 25000
    assert walls["put_wall_strike"] == 24900


def test_pcr_calculation():
    chain_rows = [
        {"strike": 25000, "ce_oi": 100000, "pe_oi": 150000, "ce_volume": 50000, "pe_volume": 60000},
        {"strike": 25100, "ce_oi": 100000, "pe_oi": 50000, "ce_volume": 40000, "pe_volume": 20000},
    ]
    pcr = calculate_pcr(chain_rows)
    assert pcr["oi_pcr"] == 1.0
    assert pcr["sentiment"] == "NEUTRAL"


def test_strike_selection_and_translation():
    strike_info = select_optimal_strike(spot_price=25000.0, signal_type="BUY")
    assert strike_info["option_type"] == "CE"
    assert strike_info["strike"] in [25000.0, 24950.0]
    assert strike_info["entry_premium"] > 0
    
    levels = translate_spot_to_option_levels(
        spot_entry=25000.0,
        spot_sl=24950.0,
        spot_target=25100.0,
        option_strike_info=strike_info
    )
    assert levels["option_entry"] == strike_info["entry_premium"]
    assert levels["option_sl"] < levels["option_entry"]
    assert levels["option_target"] > levels["option_entry"]
